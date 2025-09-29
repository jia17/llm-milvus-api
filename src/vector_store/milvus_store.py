from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import time
import uuid

from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, Index, SearchResult
)
from loguru import logger

from src.utils.helpers import get_config, PerformanceTimer
from src.document_loader.loader import DocumentChunk


@dataclass
class SearchHit:
    """搜索结果数据结构"""
    id: str
    score: float
    content: str
    metadata: Dict[str, Any]
    doc_id: str
    chunk_index: int


@dataclass
class InsertResult:
    """插入结果数据结构"""
    ids: List[str]
    insert_count: int
    success: bool
    error: Optional[str] = None


class MilvusVectorStore:
    """Milvus向量存储管理器"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "document_collection",
        dimension: int = 1024,
        index_type: str = "IVF_FLAT",
        metric_type: str = "IP",
        nlist: int = 1024
    ):
        self.host = host or get_config("milvus.host", "localhost")
        self.port = port or get_config("milvus.port", 19530)
        self.collection_name = collection_name or get_config("milvus.collection_name", "document_collection")
        self.dimension = dimension or get_config("embedding.dimension", 1024)
        self.index_type = index_type or get_config("milvus.index_type", "IVF_FLAT")
        self.metric_type = metric_type or get_config("milvus.metric_type", "IP")
        self.nlist = nlist or get_config("milvus.nlist", 1024)
        
        self.collection = None
        self.is_connected = False
        
        logger.info(f"Milvus向量存储初始化: {self.host}:{self.port}")
    
    def connect(self) -> bool:
        """连接到Milvus服务"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            self.is_connected = True
            logger.info(f"Milvus连接成功: {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Milvus连接失败: {str(e)}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开Milvus连接"""
        try:
            connections.disconnect("default")
            self.is_connected = False
            logger.info("Milvus连接已断开")
        except Exception as e:
            logger.warning(f"Milvus断开连接失败: {str(e)}")
    
    def create_collection(self, drop_existing: bool = False) -> bool:
        """创建集合"""
        if not self.is_connected:
            if not self.connect():
                return False
        
        try:
            # 检查集合是否存在
            if utility.has_collection(self.collection_name):
                if drop_existing:
                    utility.drop_collection(self.collection_name)
                    logger.info(f"已删除现有集合: {self.collection_name}")
                else:
                    logger.info(f"集合已存在: {self.collection_name}")
                    self.collection = Collection(self.collection_name)
                    return True
            
            # 定义字段
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.VARCHAR,
                    max_length=255,
                    is_primary=True
                ),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.dimension
                ),
                FieldSchema(
                    name="content",
                    dtype=DataType.VARCHAR,
                    max_length=65535
                ),
                FieldSchema(
                    name="doc_id",
                    dtype=DataType.VARCHAR,
                    max_length=255
                ),
                FieldSchema(
                    name="chunk_index",
                    dtype=DataType.INT64
                ),
                FieldSchema(
                    name="metadata",
                    dtype=DataType.VARCHAR,
                    max_length=65535
                )
            ]
            
            # 创建集合
            schema = CollectionSchema(
                fields=fields,
                description=f"RAG document collection with {self.dimension}D embeddings"
            )
            
            self.collection = Collection(
                name=self.collection_name,
                schema=schema
            )
            
            logger.info(f"集合创建成功: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"创建集合失败: {str(e)}")
            return False
    
    def create_index(self) -> bool:
        """创建索引"""
        if not self.collection:
            logger.error("集合未初始化")
            return False
        
        try:
            # 检查是否已有索引
            indexes = self.collection.indexes
            if indexes:
                logger.info(f"索引已存在: {[idx.field_name for idx in indexes]}")
                return True
            
            # 创建向量索引
            index_params = {
                "metric_type": self.metric_type,
                "index_type": self.index_type,
                "params": {"nlist": self.nlist}
            }
            
            self.collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            
            logger.info(f"索引创建成功: {self.index_type}, metric={self.metric_type}")
            return True
            
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
            return False
    
    def load_collection(self) -> bool:
        """加载集合到内存"""
        if not self.collection:
            logger.error("集合未初始化")
            return False
        
        try:
            self.collection.load()
            logger.info(f"集合加载成功: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"加载集合失败: {str(e)}")
            return False
    
    def insert_documents(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> InsertResult:
        """插入文档块和对应的嵌入向量"""
        if not self.collection:
            return InsertResult([], 0, False, "集合未初始化")
        
        if len(chunks) != len(embeddings):
            return InsertResult([], 0, False, "文档块数量与嵌入向量数量不匹配")
        
        try:
            with PerformanceTimer(f"插入 {len(chunks)} 个文档块"):
                # 准备数据
                ids = []
                contents = []
                doc_ids = []
                chunk_indexes = []
                metadatas = []
                
                for chunk, embedding in zip(chunks, embeddings):
                    # 生成唯一ID
                    chunk_id = chunk.chunk_id or str(uuid.uuid4())
                    ids.append(chunk_id)
                    contents.append(chunk.content)
                    doc_ids.append(chunk.doc_id)
                    chunk_indexes.append(chunk.chunk_index)
                    
                    # 序列化metadata
                    import json
                    metadata_str = json.dumps(chunk.metadata, ensure_ascii=False)
                    metadatas.append(metadata_str)
                
                # 插入数据
                entities = [
                    ids,
                    embeddings,
                    contents,
                    doc_ids,
                    chunk_indexes,
                    metadatas
                ]
                
                insert_result = self.collection.insert(entities)
                
                # 刷新数据（确保数据持久化）
                self.collection.flush()
                
                logger.info(f"文档插入成功: {len(ids)} 个块")
                
                return InsertResult(
                    ids=ids,
                    insert_count=len(ids),
                    success=True
                )
                
        except Exception as e:
            logger.error(f"插入文档失败: {str(e)}")
            return InsertResult([], 0, False, str(e))
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None
    ) -> List[SearchHit]:
        """搜索相似向量"""
        if not self.collection:
            logger.error("集合未初始化")
            return []
        
        try:
            # 搜索参数
            search_params = get_config("milvus.search_params", {"nprobe": 16})
            
            # 输出字段
            if output_fields is None:
                output_fields = ["content", "doc_id", "chunk_index", "metadata"]
            
            with PerformanceTimer("向量搜索"):
                results = self.collection.search(
                    data=[query_embedding],
                    anns_field="embedding",
                    param=search_params,
                    limit=top_k,
                    expr=filter_expr,
                    output_fields=output_fields
                )
            
            # 解析结果
            hits = []
            if results and len(results) > 0:
                for hit in results[0]:
                    try:
                        # 解析metadata
                        import json
                        metadata = json.loads(hit.get("metadata") or "{}")
                        
                        search_hit = SearchHit(
                            id=str(hit.id),
                            score=float(hit.score),
                            content=hit.get("content") or "",
                            metadata=metadata,
                            doc_id=hit.get("doc_id") or "",
                            chunk_index=int(hit.get("chunk_index") or 0)
                        )
                        hits.append(search_hit)
                        
                    except Exception as e:
                        logger.warning(f"解析搜索结果失败: {str(e)}")
                        continue
            
            logger.info(f"搜索完成: 返回 {len(hits)} 个结果")
            return hits
            
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return []
    
    def delete_by_doc_id(self, doc_id: str) -> bool:
        """根据文档ID删除所有相关块"""
        if not self.collection:
            logger.error("集合未初始化")
            return False
        
        try:
            # 首先检查文档是否存在
            expr = f'doc_id == "{doc_id}"'
            existing_results = self.collection.query(
                expr=expr,
                output_fields=["id"],
                limit=1
            )
            
            if not existing_results:
                logger.warning(f"文档不存在: {doc_id}")
                return True  # 文档已经不存在，认为删除成功
            
            # 执行删除操作
            self.collection.delete(expr)
            self.collection.flush()
            
            # 等待删除操作生效并验证
            import time
            max_wait_time = 5  # 最多等待5秒
            wait_interval = 0.5  # 每0.5秒检查一次
            waited_time = 0
            
            while waited_time < max_wait_time:
                time.sleep(wait_interval)
                waited_time += wait_interval
                
                # 验证删除是否成功
                verify_results = self.collection.query(
                    expr=expr,
                    output_fields=["id"],
                    limit=1
                )
                
                if not verify_results:
                    logger.info(f"删除文档成功: {doc_id}")
                    return True
            
            # 如果等待超时，再次检查
            final_check = self.collection.query(
                expr=expr,
                output_fields=["id"],
                limit=1
            )
            
            if not final_check:
                logger.info(f"删除文档成功: {doc_id}")
                # 删除成功后，需要重建稀疏索引以保持数据一致性
                logger.info("文档删除成功，稀疏索引需要重建以保持一致性")
                return True
            else:
                logger.error(f"删除文档可能失败，仍然存在记录: {doc_id}")
                return False
            
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            return False
    
    def delete_by_ids(self, ids: List[str]) -> bool:
        """根据ID列表删除文档块"""
        if not self.collection:
            logger.error("集合未初始化")
            return False
        
        try:
            # 构建删除表达式
            id_list = "', '".join(ids)
            expr = f"id in ['{id_list}']"
            
            self.collection.delete(expr)
            self.collection.flush()
            
            logger.info(f"删除文档块成功: {len(ids)} 个")
            return True
            
        except Exception as e:
            logger.error(f"删除文档块失败: {str(e)}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        if not self.collection:
            return {"error": "集合未初始化"}
        
        try:
            # 使用 num_entities 获取实体数量
            entity_count = self.collection.num_entities
            
            # 获取集合基本信息
            collection_info = {
                "collection_name": self.collection_name,
                "entity_count": entity_count,
                "dimension": self.dimension,
                "index_type": self.index_type,
                "metric_type": self.metric_type
            }
            
            # 尝试获取额外的统计信息
            try:
                # 检查集合是否已加载
                is_loaded = utility.has_collection(self.collection_name) and self.collection.has_index()
                collection_info["is_loaded"] = is_loaded
                
                if is_loaded:
                    # 获取索引信息
                    indexes = self.collection.indexes
                    collection_info["indexes"] = [{"field": idx.field_name, "index_type": idx.params.get("index_type", "unknown")} for idx in indexes]
            except Exception as stats_e:
                logger.warning(f"获取额外统计信息失败: {str(stats_e)}")
            
            return collection_info
            
        except Exception as e:
            logger.error(f"获取集合统计失败: {str(e)}")
            return {"error": str(e)}
    
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        if not self.is_connected:
            if not self.connect():
                return []
        
        try:
            return utility.list_collections()
        except Exception as e:
            logger.error(f"列出集合失败: {str(e)}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = {
            "connected": self.is_connected,
            "collection_exists": False,
            "collection_loaded": False,
            "index_exists": False,
            "entity_count": 0
        }
        
        try:
            if not self.is_connected:
                self.connect()
            
            if utility.has_collection(self.collection_name):
                result["collection_exists"] = True
                
                if not self.collection:
                    self.collection = Collection(self.collection_name)
                
                # 检查是否加载
                result["collection_loaded"] = utility.loading_progress(self.collection_name)["loading_progress"] == "100%"
                
                # 检查索引
                indexes = self.collection.indexes
                result["index_exists"] = len(indexes) > 0
                
                # 实体数量
                result["entity_count"] = self.collection.num_entities
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"健康检查失败: {str(e)}")
        
        return result
    
    def initialize(self, force_recreate: bool = False) -> bool:
        """初始化向量存储（一键设置）"""
        try:
            # 连接
            if not self.connect():
                return False
            
            # 创建集合
            if not self.create_collection(drop_existing=force_recreate):
                return False
            
            # 创建索引
            if not self.create_index():
                return False
            
            # 加载集合
            if not self.load_collection():
                return False
            
            logger.info("Milvus向量存储初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            return False