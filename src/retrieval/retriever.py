from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
import jieba
import jieba.analyse
import numpy as np
import re

from loguru import logger

from src.vector_store.milvus_store import MilvusVectorStore, SearchHit
from src.embedding.embedder import EmbeddingManager
from src.utils.helpers import get_config, PerformanceTimer


@dataclass
class RetrievalResult:
    """检索结果数据结构"""
    query: str
    hits: List[SearchHit]
    dense_hits: List[SearchHit]
    sparse_hits: List[SearchHit]
    total_hits: int
    retrieval_time: float
    method: str = "hybrid"


@dataclass
class KeywordMatch:
    """关键词匹配结果"""
    chunk_id: str
    score: float
    matched_keywords: List[str]
    content: str
    metadata: Dict[str, Any]


class KeywordExtractor:
    """关键词提取器"""
    
    def __init__(self):
        # 设置jieba分词
        jieba.setLogLevel('WARNING')  # 减少jieba日志输出
        
        # 停用词列表
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
            '会', '着', '没有', '看', '好', '自己', '这', '那', '它', '他',
            '她', '我们', '你们', '他们', '什么', '怎么', '为什么', '哪里',
            '什么时候', '怎样', '多少', '几', '第一', '第二'
        }
        
        logger.info("关键词提取器初始化完成")
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """提取关键词"""
        try:
            # 使用TF-IDF提取关键词
            keywords = jieba.analyse.extract_tags(
                text,
                topK=top_k,
                withWeight=False,
                allowPOS=('n', 'nz', 'v', 'vd', 'vn', 'l', 'a', 'd')
            )
            
            # 过滤停用词和短词
            filtered_keywords = [
                kw for kw in keywords 
                if kw not in self.stop_words and len(kw) > 1
            ]
            
            return filtered_keywords[:top_k]
            
        except Exception as e:
            logger.warning(f"关键词提取失败: {str(e)}")
            return []
    
    def extract_entities(self, text: str) -> List[str]:
        """提取命名实体（简化版）"""
        try:
            # 使用正则表达式提取一些常见实体
            entities = []
            
            # 提取数字
            numbers = re.findall(r'\d+(?:\.\d+)?', text)
            entities.extend(numbers)
            
            # 提取英文单词
            english_words = re.findall(r'[A-Za-z]+', text)
            entities.extend([w for w in english_words if len(w) > 2])
            
            return list(set(entities))
            
        except Exception as e:
            logger.warning(f"实体提取失败: {str(e)}")
            return []


class BM25Calculator:
    """BM25算法实现"""
    
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
    
    def calculate_bm25(self, query_terms: List[str], doc_terms: List[str], 
                      corpus_stats: Dict[str, Any]) -> float:
        """计算BM25分数"""
        if not query_terms or not doc_terms:
            return 0.0
        
        score = 0.0
        doc_len = len(doc_terms)
        avg_doc_len = corpus_stats.get('avg_doc_len', doc_len)
        
        # 计算每个查询词的BM25分数
        for term in query_terms:
            if term not in doc_terms:
                continue
            
            # 词频
            tf = doc_terms.count(term)
            # 文档频率
            df = corpus_stats.get('term_doc_freq', {}).get(term, 1)
            # 总文档数
            total_docs = corpus_stats.get('total_docs', 1)
            
            # IDF计算
            idf = np.log((total_docs - df + 0.5) / (df + 0.5))
            
            # BM25公式
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / avg_doc_len))
            
            score += idf * (numerator / denominator)
        
        return score


class SparseRetriever:
    """稀疏检索器（基于关键词匹配+BM25）"""
    
    def __init__(self):
        self.keyword_extractor = KeywordExtractor()
        self.bm25_calculator = BM25Calculator()
        
        logger.info("稀疏检索器初始化完成")
    
    def search(self, query: str, documents: List[SearchHit], top_k: int = 10) -> List[SearchHit]:
        """基于关键词匹配+BM25的稀疏检索"""
        try:
            logger.info(f"SparseRetriever.search: query='{query}', documents={len(documents)}, top_k={top_k}")
            
            # 提取查询关键词
            query_keywords = self.keyword_extractor.extract_keywords(query, top_k=10)
            logger.info(f"提取到查询关键词: {query_keywords}")
            
            if not query_keywords:
                logger.warning("查询关键词提取失败")
                return []
            
            # 分词查询和文档以计算BM25
            query_terms = list(jieba.cut(query, cut_all=False))
            query_terms = [term for term in query_terms if term not in self.keyword_extractor.stop_words and len(term) > 1]
            
            # 预计算语料库统计信息
            all_doc_terms = []
            doc_terms_list = []
            
            for hit in documents:
                doc_terms = list(jieba.cut(hit.content, cut_all=False))
                doc_terms = [term for term in doc_terms if term not in self.keyword_extractor.stop_words and len(term) > 1]
                doc_terms_list.append(doc_terms)
                all_doc_terms.extend(doc_terms)
            
            # 计算语料库统计信息
            term_doc_freq = {}
            for doc_terms in doc_terms_list:
                unique_terms = set(doc_terms)
                for term in unique_terms:
                    term_doc_freq[term] = term_doc_freq.get(term, 0) + 1
            
            avg_doc_len = sum(len(doc_terms) for doc_terms in doc_terms_list) / len(doc_terms_list) if doc_terms_list else 1
            
            corpus_stats = {
                'term_doc_freq': term_doc_freq,
                'avg_doc_len': avg_doc_len,
                'total_docs': len(documents)
            }
            
            # 计算每个文档的BM25分数
            matches = []
            
            for i, hit in enumerate(documents):
                doc_terms = doc_terms_list[i]
                
                # 检查是否有关键词匹配
                doc_keywords = self.keyword_extractor.extract_keywords(hit.content, top_k=20)
                matched_keywords = set(query_keywords) & set(doc_keywords)
                
                if matched_keywords:
                    # 计算BM25分数
                    bm25_score = self.bm25_calculator.calculate_bm25(query_terms, doc_terms, corpus_stats)
                    
                    # 关键词匹配加权
                    keyword_boost = len(matched_keywords) / len(query_keywords)
                    final_score = bm25_score * (1 + keyword_boost)
                    
                    logger.debug(f"匹配文档 {hit.doc_id[:8]}: keywords={list(matched_keywords)}, bm25={bm25_score:.4f}, final={final_score:.4f}")
                    
                    # 创建SearchHit
                    result_hit = SearchHit(
                        id=hit.id,
                        score=final_score,
                        content=hit.content,
                        metadata=hit.metadata,
                        doc_id=hit.doc_id,
                        chunk_index=hit.chunk_index
                    )
                    matches.append(result_hit)
            
            # 按分数排序并返回top-k
            matches.sort(key=lambda x: x.score, reverse=True)
            logger.info(f"稀疏检索结果: {len(matches)} 个匹配，返回前{min(top_k, len(matches))}个")
            return matches[:top_k]
        
        except Exception as e:
            logger.error(f"BM25检索失败: {str(e)}")
            return []


class HybridRetriever:
    """混合检索器 - 结合稠密向量和稀疏检索"""
    
    def __init__(
        self,
        vector_store: MilvusVectorStore,
        embedding_manager: EmbeddingManager,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        similarity_threshold: Optional[float] = None
    ):
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager
        self.dense_weight = dense_weight or get_config("retrieval.dense_weight", 0.7)
        self.sparse_weight = sparse_weight or get_config("retrieval.sparse_weight", 0.3)
        self.similarity_threshold = similarity_threshold or get_config("retrieval.similarity_threshold", 0.3)
        
        self.sparse_retriever = SparseRetriever()
        
        logger.info(f"混合检索器初始化: dense_weight={self.dense_weight}, sparse_weight={self.sparse_weight}")
    
    def dense_search(self, query: str, top_k: int = 10) -> List[SearchHit]:
        """稠密向量检索"""
        try:
            with PerformanceTimer("稠密向量检索"):
                logger.info(f"开始稠密检索: query='{query}', top_k={top_k}, threshold={self.similarity_threshold}")
                
                # 生成查询嵌入
                query_embedding = self.embedding_manager.embed_query(query)
                logger.info(f"查询向量生成成功: 维度={len(query_embedding) if query_embedding else 0}")
                
                if not query_embedding:
                    logger.error("查询向量生成失败")
                    return []
                
                # 向量检索 - 直接获取足够的结果，不预先过滤
                hits = self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=top_k,  # 直接获取所需数量
                    filter_expr=None
                )
                logger.info(f"Milvus检索返回: {len(hits)} 个原始结果")
                
                # 打印前3个结果的分数
                for i, hit in enumerate(hits[:3]):
                    logger.info(f"结果{i+1}: score={hit.score:.4f}, content_preview={hit.content[:50]}...")
                
                # 只保留高于阈值的结果
                filtered_hits = [
                    hit for hit in hits 
                    if hit.score >= self.similarity_threshold
                ]
                
                logger.info(f"稠密检索完成: {len(hits)} 原始 -> {len(filtered_hits)} 过滤后 (阈值={self.similarity_threshold})")
                return filtered_hits
        
        except Exception as e:
            logger.error(f"稠密向量检索失败: {str(e)}")
            return []
    
    def sparse_search(self, query: str, top_k: int = 10) -> List[SearchHit]:
        """稀疏检索 - 基于关键词+BM25"""
        try:
            with PerformanceTimer("稀疏检索"):
                logger.info(f"开始稀疏检索: query='{query}', top_k={top_k}")
                
                # 从向量数据库获取所有文档
                if not self.vector_store.collection:
                    logger.error("向量存储集合未初始化")
                    return []
                
                all_results = self.vector_store.collection.query(
                    expr="doc_id != ''",
                    output_fields=["id", "content", "doc_id", "chunk_index", "metadata"],
                    limit=16384
                )
                logger.info(f"数据库查询返回: {len(all_results)} 个文档块")
                
                if not all_results:
                    logger.warning("没有文档可供检索")
                    return []
                
                # 检查是否有EDA相关内容
                eda_count = sum(1 for r in all_results if 'EDA' in r.get('content', '').upper())
                logger.info(f"数据库中包含EDA的文档块: {eda_count} 个")
                
                # 转换为SearchHit格式
                documents = []
                for result in all_results:
                    try:
                        import json
                        metadata = json.loads(result.get('metadata', '{}'))
                        hit = SearchHit(
                            id=str(result.get('id', '')),
                            score=1.0,
                            content=result.get('content', ''),
                            metadata=metadata,
                            doc_id=result.get('doc_id', ''),
                            chunk_index=int(result.get('chunk_index', 0))
                        )
                        documents.append(hit)
                    except Exception as e:
                        logger.warning(f"转换文档失败: {str(e)}")
                        continue
                
                logger.info(f"成功转换: {len(documents)} 个文档")
                
                # 使用BM25+关键词检索
                hits = self.sparse_retriever.search(query, documents, top_k=top_k)
                
                logger.info(f"稀疏检索完成: 返回 {len(hits)} 个结果")
                return hits
        
        except Exception as e:
            logger.error(f"稀疏检索失败: {str(e)}")
            return []
    
    def hybrid_search(self, query: str, top_k: int = 5) -> RetrievalResult:
        """混合检索 - 结合稠密和稀疏检索"""
        import time
        start_time = time.time()
        
        try:
            logger.info(f"开始混合检索: query='{query}', top_k={top_k}")
            
            # 分别进行稠密和稀疏检索
            dense_hits = self.dense_search(query, top_k=top_k * 2)
            sparse_hits = self.sparse_search(query, top_k=top_k * 2)
            
            # 融合结果
            fused_hits = self._fuse_results(dense_hits, sparse_hits, top_k)
            
            retrieval_time = time.time() - start_time
            
            result = RetrievalResult(
                query=query,
                hits=fused_hits,
                dense_hits=dense_hits,
                sparse_hits=sparse_hits,
                total_hits=len(fused_hits),
                retrieval_time=retrieval_time,
                method="hybrid"
            )
            
            logger.info(f"混合检索完成: 稠密={len(dense_hits)}, 稀疏={len(sparse_hits)}, 融合={len(fused_hits)}, 耗时={retrieval_time:.2f}s")
            return result
        
        except Exception as e:
            logger.error(f"混合检索失败: {str(e)}")
            return RetrievalResult(
                query=query,
                hits=[],
                dense_hits=[],
                sparse_hits=[],
                total_hits=0,
                retrieval_time=time.time() - start_time,
                method="hybrid"
            )
    
    def _fuse_results(self, dense_hits: List[SearchHit], sparse_hits: List[SearchHit], top_k: int) -> List[SearchHit]:
        """融合稠密和稀疏检索结果"""
        try:
            # 使用RRF (Reciprocal Rank Fusion) 算法
            score_map = {}
            
            # 处理稠密检索结果
            for rank, hit in enumerate(dense_hits):
                if hit.id not in score_map:
                    score_map[hit.id] = {
                        'hit': hit,
                        'dense_score': 0.0,
                        'sparse_score': 0.0,
                        'dense_rank': float('inf'),
                        'sparse_rank': float('inf')
                    }
                
                score_map[hit.id]['dense_score'] = hit.score
                score_map[hit.id]['dense_rank'] = rank + 1
            
            # 处理稀疏检索结果
            for rank, hit in enumerate(sparse_hits):
                if hit.id not in score_map:
                    score_map[hit.id] = {
                        'hit': hit,
                        'dense_score': 0.0,
                        'sparse_score': 0.0,
                        'dense_rank': float('inf'),
                        'sparse_rank': float('inf')
                    }
                
                score_map[hit.id]['sparse_score'] = hit.score
                score_map[hit.id]['sparse_rank'] = rank + 1
            
            # 计算融合分数
            fused_results = []
            for data in score_map.values():
                # 使用归一化分数融合
                dense_score = data['dense_score'] if data['dense_score'] != 0.0 else 0.0
                sparse_score = data['sparse_score'] if data['sparse_score'] != 0.0 else 0.0
                
                # 融合分数，保持原始分数范围
                fused_score = (self.dense_weight * dense_score) + (self.sparse_weight * sparse_score)
                
                # 创建新的SearchHit，使用融合分数
                fused_hit = SearchHit(
                    id=data['hit'].id,
                    score=fused_score,
                    content=data['hit'].content,
                    metadata=data['hit'].metadata,
                    doc_id=data['hit'].doc_id,
                    chunk_index=data['hit'].chunk_index
                )
                
                fused_results.append(fused_hit)
            
            # 按融合分数排序
            fused_results.sort(key=lambda x: x.score, reverse=True)
            
            return fused_results[:top_k]
        
        except Exception as e:
            logger.error(f"结果融合失败: {str(e)}")
            # 降级处理：如果融合失败，返回稠密检索结果
            return dense_hits[:top_k]
    
    def search(self, query: str, top_k: int = 5, method: str = "hybrid") -> RetrievalResult:
        """统一检索接口"""
        if method == "dense":
            hits = self.dense_search(query, top_k)
            return RetrievalResult(
                query=query,
                hits=hits,
                dense_hits=hits,
                sparse_hits=[],
                total_hits=len(hits),
                retrieval_time=0.0,
                method="dense"
            )
        elif method == "sparse":
            hits = self.sparse_search(query, top_k)
            return RetrievalResult(
                query=query,
                hits=hits,
                dense_hits=[],
                sparse_hits=hits,
                total_hits=len(hits),
                retrieval_time=0.0,
                method="sparse"
            )
        else:
            return self.hybrid_search(query, top_k)
    
    def update_weights(self, dense_weight: float, sparse_weight: float):
        """更新检索权重"""
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        logger.info(f"检索权重已更新: dense={dense_weight}, sparse={sparse_weight}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取检索器统计信息"""
        return {
            "dense_weight": self.dense_weight,
            "sparse_weight": self.sparse_weight,
            "similarity_threshold": self.similarity_threshold,
            "embedding_dimension": self.embedding_manager.dimension
        }