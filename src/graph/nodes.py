import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from src.graph.state import GraphState, TaskType, IntentType, DocumentInfo
from src.document_loader.loader import DocumentLoader
from src.embedding.embedder import EmbeddingManager
from src.vector_store.milvus_store import MilvusVectorStore, SearchHit
from src.retrieval.retriever import HybridRetriever
from src.generation.generator import RAGGenerator, ChatMessage


class GraphNodes:
    def __init__(
        self,
        document_loader: DocumentLoader,
        embedding_manager: EmbeddingManager,
        vector_store: MilvusVectorStore,
        hybrid_retriever: HybridRetriever,
        rag_generator: RAGGenerator
    ):
        self.document_loader = document_loader
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
        self.hybrid_retriever = hybrid_retriever
        self.rag_generator = rag_generator
        
        logger.info("LangGraph节点初始化完成")
    
    def intent_recognizer(self, state: GraphState) -> GraphState:
        """意图识别节点"""
        query = state["query"]
        
        # 文档上传检测
        if state.get("uploaded_file"):
            state["task_type"] = TaskType.DOCUMENT_UPLOAD
            state["intent_type"] = IntentType.DOCUMENT_UPLOAD
            state["intent_confidence"] = 1.0
            return state
        
        # 简化的意图识别逻辑
        rag_keywords = {'文档', '资料', '内容', '什么是', '如何', '为什么', '介绍', '解释'}
        chat_keywords = {'你好', '谢谢', '聊天', '心情'}
        
        query_lower = query.lower()
        rag_score = sum(1 for kw in rag_keywords if kw in query_lower)
        chat_score = sum(1 for kw in chat_keywords if kw in query_lower)
        
        if rag_score > chat_score and len(query) > 5:
            state["task_type"] = TaskType.QUERY
            state["intent_type"] = IntentType.KNOWLEDGE_QUERY
            state["intent_confidence"] = min(0.9, 0.5 + rag_score * 0.1)
        elif chat_score > 0:
            state["task_type"] = TaskType.CHAT
            state["intent_type"] = IntentType.CASUAL_CHAT
            state["intent_confidence"] = 0.8
        else:
            # 默认RAG
            state["task_type"] = TaskType.QUERY
            state["intent_type"] = IntentType.UNCERTAIN
            state["intent_confidence"] = 0.3
        
        logger.info(f"意图识别: {state['intent_type'].value}, 置信度: {state['intent_confidence']}")
        return state
    
    def document_processor(self, state: GraphState) -> GraphState:
        """文档处理节点"""
        try:
            file_path = state["uploaded_file"]
            if not file_path:
                state["processing_error"] = "没有上传文件"
                return state
            
            # 加载文档
            document = self.document_loader.load_document(file_path)
            
            # 分块
            chunks = self.document_loader.chunk_document(document)
            
            # 生成嵌入
            texts = [chunk.content for chunk in chunks]
            embedding_result = self.embedding_manager.embed_documents(texts)
            
            # 存储到向量数据库
            insert_result = self.vector_store.insert_documents(chunks, embedding_result.embeddings)
            
            if insert_result.success:
                state["document"] = DocumentInfo(
                    file_path=file_path,
                    filename=Path(file_path).name,
                    content=document.content[:500] + "...",
                    doc_id=document.doc_id
                )
                state["answer"] = f"文档处理成功！已将文档分成 {len(chunks)} 个片段并建立索引。"
            else:
                state["processing_error"] = f"文档存储失败: {insert_result.error}"
                
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            state["processing_error"] = str(e)
        
        return state
    
    def hybrid_retriever_node(self, state: GraphState) -> GraphState:
        """混合检索节点"""
        start_time = time.time()
        query = state["query"]
        
        try:
            retrieval_result = self.hybrid_retriever.hybrid_search(query, top_k=5)
            
            state["retrieval_results"] = retrieval_result.hits
            state["dense_results"] = retrieval_result.dense_hits
            state["sparse_results"] = retrieval_result.sparse_hits
            state["retrieval_time"] = retrieval_result.retrieval_time
            
            logger.info(f"检索完成: 找到 {len(retrieval_result.hits)} 个相关结果")
            
        except Exception as e:
            logger.error(f"检索失败: {str(e)}")
            state["retrieval_results"] = []
            state["error"] = f"检索失败: {str(e)}"
        
        state["retrieval_time"] = time.time() - start_time
        return state
    
    def answer_generator_node(self, state: GraphState) -> GraphState:
        """答案生成节点"""
        start_time = time.time()
        query = state["query"]
        
        try:
            if state["intent_type"] == IntentType.CASUAL_CHAT:
                # 聊天模式
                chat_history = self._extract_chat_history(state["messages"])
                answer = self.rag_generator.chat_from_state(query, chat_history)
                state["sources"] = []
                
            else:
                # RAG模式
                if not state.get("retrieval_results"):
                    state["answer"] = "抱歉，没有找到相关文档内容来回答您的问题。"
                    state["sources"] = []
                    return state
                
                # 直接使用状态数据生成答案
                chat_history = self._extract_chat_history(state["messages"])
                answer = self.rag_generator.generate_from_state(
                    query=query,
                    retrieval_results=state["retrieval_results"],
                    chat_history=chat_history if chat_history else None
                )
                state["sources"] = state["retrieval_results"]
            
            state["answer"] = answer
            state["messages"].append(AIMessage(content=answer))
            
        except Exception as e:
            logger.error(f"生成答案失败: {str(e)}")
            state["answer"] = f"生成答案时出现错误: {str(e)}"
            state["error"] = str(e)
        
        state["generation_time"] = time.time() - start_time
        return state
    
    def _extract_chat_history(self, messages: List[BaseMessage]) -> List[ChatMessage]:
        """从LangGraph消息提取聊天历史"""
        chat_history = []
        for msg in messages[:-1]:  # 排除最后一条（当前查询）
            if hasattr(msg, 'type'):
                role = "user" if msg.type == "human" else "assistant"
                chat_history.append(ChatMessage(role=role, content=msg.content))
        return chat_history


def should_process_document(state: GraphState) -> str:
    """路由函数：是否需要处理文档"""
    if state["task_type"] == TaskType.DOCUMENT_UPLOAD:
        return "document_processor"
    return "retriever"


def should_retrieve(state: GraphState) -> str:
    """路由函数：是否需要检索"""
    if state["task_type"] == TaskType.QUERY:
        return "retriever"
    return "generator"


def end_condition(state: GraphState) -> bool:
    """结束条件"""
    return "answer" in state and state["answer"] is not None