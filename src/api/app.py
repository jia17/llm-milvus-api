from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import tempfile
import os
import json
import time
from pathlib import Path
import asyncio

from loguru import logger

from src.graph.workflow import RAGWorkflow
from src.utils.helpers import get_config, PerformanceTimer
from src.conversation.models import ChatMessage, ConversationSession, SessionSummary
from src.conversation.session_manager import SessionManager
from src.vector_store.milvus_store import MilvusVectorStore
from src.retrieval.retriever import HybridRetriever
from src.generation.generator import RAGGenerator


# Pydantic模型定义
class QueryRequest(BaseModel):
    question: str = Field(..., description="用户问题", min_length=1, max_length=1000)
    top_k: int = Field(5, description="检索文档数量", ge=1, le=20)
    method: str = Field("hybrid", description="检索方法", pattern="^(dense|sparse|hybrid)$")
    stream: bool = Field(False, description="是否流式返回")


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    retrieval_time: float
    generation_time: float
    total_time: float
    method: str


class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题", min_length=1, max_length=1000)
    history: List[Dict[str, str]] = Field([], description="聊天历史")
    stream: bool = Field(False, description="是否流式返回")


class ConversationRequest(BaseModel):
    question: str = Field(..., description="用户问题", min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    user_id: str = Field("anonymous", description="用户ID")
    stream: bool = Field(True, description="是否流式返回")
    title: Optional[str] = Field(None, description="对话标题")


class ConversationResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    mode: str  # "rag" or "chat"
    intent: str
    confidence: float
    sources: List[Dict[str, Any]]
    retrieval_time: float
    generation_time: float
    rag_used: bool
    chunks_retrieved: int
    chunks_filtered: int


class DocumentInfo(BaseModel):
    filename: str
    file_size: int
    file_type: str
    chunk_count: int
    doc_id: str
    upload_time: str


class UploadResponse(BaseModel):
    success: bool
    message: str
    document: Optional[DocumentInfo] = None
    chunk_count: int = 0


class HealthResponse(BaseModel):
    status: str
    components: Dict[str, Any]
    timestamp: str


class StatsResponse(BaseModel):
    milvus_stats: Dict[str, Any]
    retriever_stats: Dict[str, Any]
    generator_stats: Dict[str, Any]
    session_stats: Dict[str, Any] = {}


class SessionCreateRequest(BaseModel):
    user_id: str = Field("anonymous", description="用户ID")
    title: Optional[str] = Field(None, description="对话标题")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str
    compressed: bool = False


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    metadata: Dict[str, Any] = {}


# 全局变量
workflow_instance = None
session_manager_instance = None


def get_workflow() -> RAGWorkflow:
    """获取RAG工作流实例"""
    global workflow_instance
    if workflow_instance is None:
        workflow_instance = RAGWorkflow()
        if not workflow_instance.initialize_services():
            raise HTTPException(status_code=500, detail="工作流初始化失败")
    return workflow_instance


def get_vector_store() -> MilvusVectorStore:
    """获取向量存储实例"""
    workflow = get_workflow()
    return workflow.vector_store


def get_retriever() -> HybridRetriever:
    """获取检索器实例"""
    workflow = get_workflow()
    return workflow.hybrid_retriever


def get_generator() -> RAGGenerator:
    """获取生成器实例"""
    workflow = get_workflow()
    return workflow.rag_generator


def get_session_manager() -> SessionManager:
    """获取会话管理器实例"""
    global session_manager_instance
    if session_manager_instance is None:
        session_manager_instance = SessionManager()
    return session_manager_instance


# FastAPI应用初始化
def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app_config = get_config("api", {})
    
    app = FastAPI(
        title=app_config.get("title", "LLM RAG API"),
        description=app_config.get("description", "智能问答系统API"),
        version=app_config.get("version", "1.0.0"),
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    try:
        logger.info("API服务启动中...")
        
        # 初始化工作流组件
        workflow = get_workflow()
        
        logger.info("API服务启动完成")
        
    except Exception as e:
        logger.error(f"API服务启动失败: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    try:
        global workflow_instance
        if workflow_instance and workflow_instance.vector_store:
            workflow_instance.vector_store.disconnect()
        logger.info("API服务已关闭")
    except Exception as e:
        logger.error(f"API服务关闭时出错: {str(e)}")


@app.get("/", response_model=Dict[str, str])
async def root():
    """根路径"""
    return {
        "message": "LLM RAG API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check(workflow: RAGWorkflow = Depends(get_workflow)):
    """健康检查"""
    from datetime import datetime
    
    try:
        stats = workflow.get_stats()
        status = "healthy" if stats["workflow_ready"] else "unhealthy"
        
        components = {
            "workflow": {"status": "ok" if stats["workflow_ready"] else "error"},
            "milvus": {"status": "ok" if stats["workflow_ready"] else "not_connected"},
            "embedding": {"model": stats.get("embedding_model", {})},
            "retrieval": stats.get("retrieval_config", {}),
            "generation": stats.get("generation_config", {})
        }
        
    except Exception as e:
        status = "unhealthy"
        components = {"error": str(e)}
    
    return HealthResponse(
        status=status,
        components=components,
        timestamp=datetime.now().isoformat()
    )


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    workflow: RAGWorkflow = Depends(get_workflow)
):
    """上传文档"""
    try:
        # 检查文件大小
        max_size = get_config("document.max_file_size", 10485760)  # 10MB
        
        # 检查文件类型
        file_ext = Path(file.filename).suffix.lower()
        supported_formats = get_config("document.supported_formats", [".pdf", ".txt", ".md"])
        
        if file_ext not in supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {file_ext}. 支持的格式: {supported_formats}"
            )
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            
            if len(content) > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件大小超限: {len(content)} bytes > {max_size} bytes"
                )
            
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # 使用LangGraph工作流处理文档
            result = workflow.upload_document(tmp_file_path)
            
            if result.get("error"):
                raise HTTPException(status_code=500, detail=result["error"])
            
            # 构建响应
            doc_info = DocumentInfo(
                filename=file.filename,
                file_size=len(content),
                file_type=file_ext,
                chunk_count=0,  # TODO: 从workflow result获取
                doc_id="",  # TODO: 从workflow result获取
                upload_time=str(time.time())
            )
            
            return UploadResponse(
                success=True,
                message=result.get("answer", f"文档上传成功: {file.filename}"),
                document=doc_info,
                chunk_count=0
            )
            
        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_file_path)
            except:
                pass
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档上传失败: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    workflow: RAGWorkflow = Depends(get_workflow)
):
    """智能问答 - 使用LangGraph工作流"""
    try:
        # 使用LangGraph工作流处理查询
        result = workflow.query_documents(request.question)
        
        # 构建响应
        sources = []
        for hit in result.get("sources", []):
            sources.append({
                "id": hit.id,
                "content": hit.content,
                "score": hit.score,
                "metadata": hit.metadata,
                "doc_id": hit.doc_id,
                "chunk_index": hit.chunk_index
            })
        
        return QueryResponse(
            question=request.question,
            answer=result.get("answer", ""),
            sources=sources,
            retrieval_time=result.get("retrieval_time", 0.0),
            generation_time=result.get("generation_time", 0.0),
            total_time=result.get("total_time", 0.0),
            method=request.method
        )
            
    except Exception as e:
        logger.error(f"智能问答失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"智能问答失败: {str(e)}")


@app.post("/chat")
async def chat(
    request: ChatRequest,
    workflow: RAGWorkflow = Depends(get_workflow)
):
    """聊天对话 - 使用LangGraph工作流自动判断RAG需求"""
    try:
        # 使用工作流处理聊天，自动判断是否需要RAG
        result = workflow.process_query(request.question)
        
        # 返回简化的聊天响应
        return {
            "question": request.question,
            "answer": result.get("answer", ""),
            "intent_type": result.get("intent_type", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "used_rag": result.get("intent_type") == "knowledge_query"
        }
        
    except Exception as e:
        logger.error(f"简单聊天失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"简单聊天失败: {str(e)}")


@app.post("/conversation", response_model=ConversationResponse)
async def smart_conversation(
    request: ConversationRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: RAGGenerator = Depends(get_generator)
):
    """智能多轮对话 - 自动判断是否使用RAG"""
    try:
        # 转换对话历史
        chat_history = []
        for msg in request.history:
            chat_history.append(ChatMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", "")
            ))
        
        # 定义检索函数
        def retrieval_func(query: str):
            return retriever.search(
                query=query,
                top_k=5,
                method="hybrid"
            )
        
        # 智能对话
        result = generator.smart_conversation(
            question=request.question,
            chat_history=chat_history,
            retrieval_func=retrieval_func,
            stream=request.stream
        )
        
        # 增强sources信息，确保包含完整的chunk内容
        enhanced_sources = []
        for source in result["sources"]:
            enhanced_sources.append({
                "content": source["content"],
                "score": source["score"],
                "metadata": source["metadata"],
                "doc_id": source.get("doc_id", ""),
                "chunk_index": source.get("chunk_index", 0)
            })
        
        return ConversationResponse(
            question=request.question,
            answer=result["answer"],
            mode=result["mode"],
            intent=result["intent"],
            confidence=result["confidence"],
            sources=enhanced_sources,
            retrieval_time=result["retrieval_time"],
            generation_time=result["generation_time"],
            rag_used=result["mode"] == "rag",
            chunks_retrieved=result.get("chunks_retrieved", len(enhanced_sources)),
            chunks_filtered=len(enhanced_sources)
        )
        
    except Exception as e:
        logger.error(f"智能对话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"智能对话失败: {str(e)}")


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    vector_store: MilvusVectorStore = Depends(get_vector_store)
):
    """删除文档"""
    try:
        success = vector_store.delete_by_doc_id(doc_id)
        
        if success:
            return {"message": f"文档删除成功: {doc_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"文档不存在或删除失败: {doc_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_stats(
    vector_store: MilvusVectorStore = Depends(get_vector_store),
    retriever: HybridRetriever = Depends(get_retriever),
    generator: RAGGenerator = Depends(get_generator),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取系统统计信息"""
    try:
        return StatsResponse(
            milvus_stats=vector_store.get_collection_stats(),
            retriever_stats=retriever.get_stats(),
            generator_stats=generator.get_stats(),
            session_stats=session_manager.get_stats()
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


# 知识库管理API
@app.get("/knowledge/documents")
async def list_documents(
    vector_store: MilvusVectorStore = Depends(get_vector_store)
):
    """获取文档列表"""
    try:
        # 查询所有文档的doc_id和基础信息
        if not vector_store.collection:
            raise HTTPException(status_code=500, detail="集合未初始化")
        
        # 使用聚合查询获取文档列表
        docs = []
        seen_docs = set()
        
        # 简单查询所有记录，然后去重
        search_results = vector_store.collection.query(
            expr="doc_id != ''",
            output_fields=["doc_id", "content", "metadata", "chunk_index"],
            limit=10000
        )
        
        for result in search_results:
            doc_id = result.get('doc_id')
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                
                # 解析metadata
                import json
                try:
                    metadata = json.loads(result.get('metadata', '{}'))
                except:
                    metadata = {}
                
                docs.append({
                    "doc_id": doc_id,
                    "filename": metadata.get('filename', '未知文件'),
                    "file_type": metadata.get('file_type', 'unknown'),
                    "file_size": metadata.get('file_size', 0),
                    "created_time": metadata.get('created_time', 0),
                    "modified_time": metadata.get('modified_time', 0),
                    "preview": result.get('content', '')[:200] + '...' if len(result.get('content', '')) > 200 else result.get('content', '')
                })
        
        return {"documents": docs, "total": len(docs)}
        
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@app.get("/knowledge/documents/{doc_id}")
async def get_document_detail(
    doc_id: str,
    vector_store: MilvusVectorStore = Depends(get_vector_store)
):
    """获取文档详细信息"""
    try:
        if not vector_store.collection:
            raise HTTPException(status_code=500, detail="集合未初始化")
        
        # 查询该文档的所有块
        chunks = vector_store.collection.query(
            expr=f'doc_id == "{doc_id}"',
            output_fields=["id", "content", "metadata", "chunk_index"],
            limit=1000
        )
        
        if not chunks:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
        
        # 按chunk_index排序
        chunks.sort(key=lambda x: x.get('chunk_index', 0))
        
        # 解析第一个块的metadata作为文档metadata
        import json
        try:
            doc_metadata = json.loads(chunks[0].get('metadata', '{}'))
        except:
            doc_metadata = {}
        
        # 构建响应
        doc_info = {
            "doc_id": doc_id,
            "filename": doc_metadata.get('filename', '未知文件'),
            "file_type": doc_metadata.get('file_type', 'unknown'),
            "file_size": doc_metadata.get('file_size', 0),
            "created_time": doc_metadata.get('created_time', 0),
            "modified_time": doc_metadata.get('modified_time', 0),
            "chunk_count": len(chunks),
            "chunks": []
        }
        
        for chunk in chunks:
            try:
                chunk_metadata = json.loads(chunk.get('metadata', '{}'))
            except:
                chunk_metadata = {}
                
            doc_info["chunks"].append({
                "id": chunk.get('id'),
                "content": chunk.get('content', ''),
                "chunk_index": chunk.get('chunk_index', 0),
                "chunk_length": chunk_metadata.get('chunk_length', 0)
            })
        
        return doc_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档详情失败: {str(e)}")


@app.get("/knowledge/search")
async def search_documents(
    q: str,
    limit: int = 10,
    vector_store: MilvusVectorStore = Depends(get_vector_store)
):
    """搜索文档内容"""
    try:
        if not vector_store.collection:
            raise HTTPException(status_code=500, detail="集合未初始化")
        
        # 简单的文本匹配搜索
        results = vector_store.collection.query(
            expr=f'content like "%{q}%"',
            output_fields=["id", "doc_id", "content", "metadata", "chunk_index"],
            limit=limit
        )
        
        search_results = []
        for result in results:
            try:
                import json
                metadata = json.loads(result.get('metadata', '{}'))
                
                search_results.append({
                    "id": result.get('id'),
                    "doc_id": result.get('doc_id'),
                    "filename": metadata.get('filename', '未知文件'),
                    "content": result.get('content', ''),
                    "chunk_index": result.get('chunk_index', 0),
                    "highlight": result.get('content', '').replace(q, f"**{q}**")
                })
            except:
                continue
        
        return {"results": search_results, "total": len(search_results), "query": q}
        
    except Exception as e:
        logger.error(f"搜索文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索文档失败: {str(e)}")


@app.get("/knowledge/stats")
async def get_knowledge_stats(
    vector_store: MilvusVectorStore = Depends(get_vector_store)
):
    """获取知识库统计信息"""
    try:
        if not vector_store.collection:
            raise HTTPException(status_code=500, detail="集合未初始化")
        
        # 获取基础统计
        collection_stats = vector_store.get_collection_stats()
        
        # 获取文档数量统计
        all_chunks = vector_store.collection.query(
            expr="doc_id != ''",
            output_fields=["doc_id", "metadata"],
            limit=10000
        )
        
        doc_count = len(set(chunk.get('doc_id') for chunk in all_chunks))
        
        # 文件类型统计
        file_types = {}
        for chunk in all_chunks:
            try:
                import json
                metadata = json.loads(chunk.get('metadata', '{}'))
                file_type = metadata.get('file_type', 'unknown')
                file_types[file_type] = file_types.get(file_type, 0) + 1
            except:
                continue
        
        return {
            "total_documents": doc_count,
            "total_chunks": collection_stats.get("entity_count", 0),
            "file_types": file_types,
            "collection_name": collection_stats.get("collection_name"),
            "dimension": collection_stats.get("dimension"),
            "index_type": collection_stats.get("index_type")
        }
        
    except Exception as e:
        logger.error(f"获取知识库统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识库统计失败: {str(e)}")




# 流式智能问答
@app.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: RAGGenerator = Depends(get_generator)
):
    """流式智能问答 - 专注RAG文档查询"""
    async def generate_stream():
        try:
            # 检索相关文档
            retrieval_result = retriever.search(
                query=request.question,
                top_k=request.top_k,
                method=request.method
            )
            
            # 发送检索结果元信息
            yield f"data: {json.dumps({'type': 'metadata', 'sources_count': len(retrieval_result.hits), 'method': request.method})}\n\n"
            
            # 流式生成回答
            for chunk in generator.generate_answer_stream(
                question=request.question,
                retrieval_result=retrieval_result
            ):
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            
            # 发送源信息
            sources = [{
                "content": hit.content[:200] + "..." if len(hit.content) > 200 else hit.content,
                "score": hit.score,
                "metadata": hit.metadata
            } for hit in retrieval_result.hits if hit.score >= generator.min_similarity_score]
            
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"流式问答失败: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )


# 会话管理API
@app.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """创建新会话"""
    try:
        session = session_manager.create_session(
            title=request.title,
            metadata={**request.metadata, "user_id": request.user_id}
        )
        
        return SessionResponse(
            session_id=session.session_id,
            user_id=request.user_id,
            title=session.title,
            message_count=len(session.messages),
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            compressed=session.compressed
        )
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@app.get("/sessions")
async def list_sessions(
    user_id: str = "anonymous",
    limit: int = 50,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取用户会话列表"""
    try:
        sessions = session_manager.list_sessions(limit=limit)
        
        # 过滤用户会话
        user_sessions = [
            s for s in sessions 
            if s.get("metadata", {}).get("user_id", "anonymous") == user_id
        ]
        
        return {
            "sessions": [
                {
                    "session_id": s["session_id"],
                    "title": s["title"],
                    "message_count": s["message_count"],
                    "created_at": s["created_at"],
                    "updated_at": s["updated_at"],
                    "compressed": s.get("compressed", False)
                }
                for s in user_sessions
            ],
            "total": len(user_sessions)
        }
    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@app.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    user_id: str = "anonymous",
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取会话详情"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 验证用户权限
        session_user_id = session.metadata.get("user_id", "anonymous")
        if session_user_id != user_id and user_id != "admin":
            raise HTTPException(status_code=403, detail="无权访问此会话")
        
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else "",
                "metadata": msg.metadata
            }
            for msg in session.messages
        ]
        
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages),
            "compressed": session.compressed,
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    user_id: str = "anonymous",
    limit: Optional[int] = None,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取会话消息历史"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 验证用户权限
        session_user_id = session.metadata.get("user_id", "anonymous")
        if session_user_id != user_id and user_id != "admin":
            raise HTTPException(status_code=403, detail="无权访问此会话")
        
        messages = session_manager.get_messages(session_id, limit=limit)
        
        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else "",
                    "metadata": msg.metadata
                }
                for msg in messages
            ],
            "total": len(messages),
            "compressed": session.compressed
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话消息失败: {str(e)}")


@app.put("/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    request: dict,
    user_id: str = "anonymous",
    session_manager: SessionManager = Depends(get_session_manager)
):
    """更新会话标题"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 验证用户权限
        session_user_id = session.metadata.get("user_id", "anonymous")
        if session_user_id != user_id and user_id != "admin":
            raise HTTPException(status_code=403, detail="无权修改此会话")
        
        title = request.get("title")
        if not title:
            raise HTTPException(status_code=400, detail="标题不能为空")
        
        success = session_manager.update_session_title(session_id, title)
        if not success:
            raise HTTPException(status_code=500, detail="更新标题失败")
        
        return {"message": "标题更新成功", "title": title}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话标题失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新会话标题失败: {str(e)}")


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = "anonymous",
    session_manager: SessionManager = Depends(get_session_manager)
):
    """删除会话"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 验证用户权限
        session_user_id = session.metadata.get("user_id", "anonymous")
        if session_user_id != user_id and user_id != "admin":
            raise HTTPException(status_code=403, detail="无权删除此会话")
        
        success = session_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除会话失败")
        
        return {"message": "会话删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@app.get("/users/{user_id}/sessions/count")
async def get_user_session_count(
    user_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取用户会话数量"""
    try:
        sessions = session_manager.list_sessions(limit=1000)
        user_sessions = [
            s for s in sessions 
            if s.get("metadata", {}).get("user_id", "anonymous") == user_id
        ]
        
        return {
            "user_id": user_id,
            "session_count": len(user_sessions),
            "total_messages": sum(s["message_count"] for s in user_sessions),
            "compressed_sessions": sum(1 for s in user_sessions if s.get("compressed", False))
        }
    except Exception as e:
        logger.error(f"获取用户会话数量失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取用户会话数量失败: {str(e)}")


# 流式智能对话 - 重构支持会话历史
@app.post("/conversation/stream")
async def conversation_stream(
    request: ConversationRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: RAGGenerator = Depends(get_generator),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """流式智能多轮对话 - 支持会话历史管理"""
    async def generate_stream():
        session_id = None
        try:
            # 获取或创建会话
            if request.session_id:
                session = session_manager.get_session(request.session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="会话不存在")
                session_id = request.session_id
            else:
                # 创建新会话
                session = session_manager.create_session(
                    title=request.title or f"新对话",
                    metadata={"user_id": request.user_id}
                )
                session_id = session.session_id
            
            # 发送会话信息
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            
            # 获取对话历史
            chat_history = session_manager.get_messages(session_id, limit=20)
            
            # 意图识别
            intent = generator.intent_recognizer.recognize_intent(request.question, chat_history)
            
            # 发送意图识别结果
            yield f"data: {json.dumps({'type': 'intent', 'intent': intent.intent_type, 'confidence': intent.confidence, 'needs_rag': intent.needs_rag})}\n\n"
            
            # 添加用户消息到会话
            user_message = ChatMessage(role="user", content=request.question)
            session_manager.add_message(session_id, user_message)
            
            assistant_answer = ""
            sources = []
            
            if intent.needs_rag:
                # RAG模式 - 流式检索和生成
                retrieval_result = retriever.search(
                    query=request.question,
                    top_k=5,
                    method="hybrid"
                )
                
                yield f"data: {json.dumps({'type': 'metadata', 'mode': 'rag', 'sources_count': len(retrieval_result.hits)})}\n\n"
                
                # 流式生成RAG回答
                generation_result = generator.generate_multi_turn_answer(
                    question=request.question,
                    retrieval_result=retrieval_result,
                    chat_history=chat_history,
                    stream=False
                )
                
                assistant_answer = generation_result.answer
                sources = [{
                    "content": hit.content[:200] + "..." if len(hit.content) > 200 else hit.content,
                    "score": hit.score,
                    "metadata": hit.metadata
                } for hit in generation_result.sources]
                
                # 分块发送回答
                words = assistant_answer.split()
                for word in words:
                    yield f"data: {json.dumps({'type': 'content', 'content': word + ' '})}\n\n"
                    await asyncio.sleep(0.05)
                
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            
            else:
                # 聊天模式 - 流式生成
                yield f"data: {json.dumps({'type': 'metadata', 'mode': 'chat'})}\n\n"
                
                assistant_answer = generator.chat(
                    question=request.question,
                    chat_history=chat_history
                )
                
                # 分块发送回答
                words = assistant_answer.split()
                for word in words:
                    yield f"data: {json.dumps({'type': 'content', 'content': word + ' '})}\n\n"
                    await asyncio.sleep(0.05)
            
            # 保存助手消息到会话
            assistant_message = ChatMessage(
                role="assistant", 
                content=assistant_answer,
                metadata={"sources_count": len(sources), "mode": "rag" if intent.needs_rag else "chat"}
            )
            session_manager.add_message(session_id, assistant_message)
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"流式智能对话失败: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'session_id': session_id})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )


if __name__ == "__main__":
    import uvicorn
    
    # 配置日志
    from src.utils.helpers import Logger
    Logger.setup_logger(
        log_level=get_config("logging.level", "INFO"),
        log_format=get_config("logging.format"),
        log_file="logs/api.log"
    )
    
    # 启动服务
    host = get_config("api.host", "0.0.0.0")
    port = get_config("api.port", 8000)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        access_log=True
    )