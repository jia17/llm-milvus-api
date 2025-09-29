import time
from typing import Dict, Any, Optional, Union
from langchain_core.messages import HumanMessage

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import GraphState, TaskType, IntentType
from src.graph.nodes import GraphNodes
from src.document_loader.loader import DocumentLoader
from src.embedding.embedder import EmbeddingManager
from src.vector_store.milvus_store import MilvusVectorStore
from src.retrieval.retriever import HybridRetriever
from src.generation.generator import RAGGenerator
from src.utils.helpers import get_config

from loguru import logger


class RAGWorkflow:
    """RAG系统的LangGraph工作流"""
    
    def __init__(self):
        # 初始化组件
        self.embedding_manager = EmbeddingManager()
        self.vector_store = MilvusVectorStore()
        self.hybrid_retriever = HybridRetriever(
            vector_store=self.vector_store,
            embedding_manager=self.embedding_manager
        )
        self.rag_generator = RAGGenerator()
        self.document_loader = DocumentLoader()
        
        # 初始化节点
        self.nodes = GraphNodes(
            document_loader=self.document_loader,
            embedding_manager=self.embedding_manager,
            vector_store=self.vector_store,
            hybrid_retriever=self.hybrid_retriever,
            rag_generator=self.rag_generator
        )
        
        # 添加兼容性属性
        self.retriever = self.hybrid_retriever
        
        # 构建工作流图
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=MemorySaver())
        
        logger.info("RAG工作流初始化完成")
    
    def _build_workflow(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(GraphState)
        
        # 添加节点
        workflow.add_node("intent_recognizer", self.nodes.intent_recognizer)
        workflow.add_node("document_processor", self.nodes.document_processor)
        workflow.add_node("retriever", self.nodes.hybrid_retriever_node)
        workflow.add_node("generator", self.nodes.answer_generator_node)
        
        # 设置入口点
        workflow.set_entry_point("intent_recognizer")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "intent_recognizer",
            self._route_after_intent,
            {
                "document_processor": "document_processor",
                "retriever": "retriever", 
                "generator": "generator"
            }
        )
        
        # 文档处理后直接结束
        workflow.add_edge("document_processor", END)
        
        # 检索后生成答案
        workflow.add_edge("retriever", "generator")
        
        # 生成后结束
        workflow.add_edge("generator", END)
        
        return workflow
    
    def _route_after_intent(self, state: GraphState) -> str:
        """意图识别后的路由逻辑"""
        task_type = state.get("task_type", TaskType.QUERY)
        
        if task_type == TaskType.DOCUMENT_UPLOAD:
            return "document_processor"
        elif task_type == TaskType.CHAT:
            return "generator"  # 聊天模式直接生成
        else:
            return "retriever"  # 查询模式先检索
    
    def process_query(
        self, 
        query: str, 
        uploaded_file: Optional[str] = None,
        thread_id: str = "default"
    ) -> Dict[str, Any]:
        """处理查询的主入口"""
        start_time = time.time()
        
        try:
            # 构建初始状态
            initial_state = {
                "messages": [HumanMessage(content=query)],
                "query": query,
                "uploaded_file": uploaded_file,
                "task_type": TaskType.QUERY,
                "intent_type": None,
                "intent_confidence": 0.0,
                "document": None,
                "processing_error": None,
                "retrieval_results": [],
                "dense_results": [],
                "sparse_results": [],
                "retrieval_time": 0.0,
                "answer": "",
                "sources": [],
                "generation_time": 0.0,
                "total_time": 0.0,
                "error": None,
                "metadata": {}
            }
            
            # 执行工作流
            config = {"configurable": {"thread_id": thread_id}}
            result = self.app.invoke(initial_state, config)
            
            # 计算总时间
            total_time = time.time() - start_time
            result["total_time"] = total_time
            
            # 构建返回结果
            return {
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "intent_type": result.get("intent_type").value if result.get("intent_type") else "unknown",
                "confidence": result.get("intent_confidence", 0.0),
                "retrieval_time": result.get("retrieval_time", 0.0),
                "generation_time": result.get("generation_time", 0.0),
                "total_time": total_time,
                "document_processed": result.get("document") is not None,
                "error": result.get("error") or result.get("processing_error")
            }
            
        except Exception as e:
            logger.error(f"工作流执行失败: {str(e)}")
            return {
                "answer": f"处理查询时出现错误: {str(e)}",
                "sources": [],
                "intent_type": "error",
                "confidence": 0.0,
                "retrieval_time": 0.0,
                "generation_time": 0.0,
                "total_time": time.time() - start_time,
                "document_processed": False,
                "error": str(e)
            }
    
    def upload_document(self, file_path: str, thread_id: str = "default") -> Dict[str, Any]:
        """上传文档的便捷方法"""
        return self.process_query(
            query="上传文档",
            uploaded_file=file_path,
            thread_id=thread_id
        )
    
    def query_documents(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        """查询文档的便捷方法"""
        return self.process_query(query=query, thread_id=thread_id)
    
    def get_workflow_state(self, thread_id: str = "default") -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.app.get_state(config)
            return state.values if state else None
        except Exception as e:
            logger.error(f"获取工作流状态失败: {str(e)}")
            return None
    
    def initialize_services(self) -> bool:
        """初始化所有必要的服务"""
        try:
            # 初始化向量数据库
            if not self.vector_store.initialize():
                logger.error("向量数据库初始化失败")
                return False
            
            logger.info("RAG工作流服务初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"服务初始化失败: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工作流统计信息"""
        return {
            "workflow_ready": self.vector_store.is_connected,
            "collection_name": self.vector_store.collection_name,
            "embedding_model": self.embedding_manager.get_model_info(),
            "retrieval_config": self.hybrid_retriever.get_stats(),
            "generation_config": self.rag_generator.get_stats()
        }