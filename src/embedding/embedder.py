import asyncio
import httpx
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import time

from loguru import logger
from src.utils.helpers import get_config, retry_on_failure


@dataclass
class EmbeddingResult:
    """嵌入结果数据结构"""
    embeddings: List[List[float]]
    texts: List[str]
    model: str
    dimension: int
    token_count: Optional[int] = None


class SiliconFlowEmbedder:
    """SiliconFlow嵌入服务客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "BAAI/bge-large-zh-v1.5",
        api_base: str = "https://api.siliconflow.cn/v1",
        batch_size: int = 32,
        max_retries: int = 3,
        timeout: int = 30
    ):
        self.api_key = api_key or get_config("api_keys.siliconflow_api_key")
        self.model = model
        self.api_base = api_base.rstrip('/')
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError("SiliconFlow API密钥未设置")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # 获取模型维度
        self.dimension = get_config("embedding.dimension", 1024)
        
        logger.info(f"SiliconFlow嵌入器初始化: model={self.model}, dimension={self.dimension}")
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """嵌入文本列表"""
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                texts=[],
                model=self.model,
                dimension=self.dimension
            )
        
        logger.info(f"开始嵌入 {len(texts)} 个文本")
        
        # 分批处理
        all_embeddings = []
        all_texts = []
        total_tokens = 0
        
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_result = self._embed_batch(batch_texts)
            
            all_embeddings.extend(batch_result.embeddings)
            all_texts.extend(batch_result.texts)
            if batch_result.token_count:
                total_tokens += batch_result.token_count
            
            logger.debug(f"批次 {i//self.batch_size + 1} 完成: {len(batch_texts)} 个文本")
        
        result = EmbeddingResult(
            embeddings=all_embeddings,
            texts=all_texts,
            model=self.model,
            dimension=self.dimension,
            token_count=total_tokens if total_tokens > 0 else None
        )
        
        logger.info(f"嵌入完成: {len(all_embeddings)} 个向量, 维度: {self.dimension}")
        return result
    
    def _embed_batch(self, texts: List[str]) -> EmbeddingResult:
        """嵌入单个批次"""
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_base}/embeddings",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                # 提取嵌入向量
                embeddings = []
                for item in data["data"]:
                    embeddings.append(item["embedding"])
                
                # 获取token使用量
                token_count = data.get("usage", {}).get("total_tokens")
                
                return EmbeddingResult(
                    embeddings=embeddings,
                    texts=texts,
                    model=self.model,
                    dimension=len(embeddings[0]) if embeddings else self.dimension,
                    token_count=token_count
                )
                
        except httpx.HTTPStatusError as e:
            logger.error(f"SiliconFlow API HTTP错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"嵌入API调用失败: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"SiliconFlow API请求错误: {str(e)}")
            raise Exception(f"嵌入API请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"嵌入处理错误: {str(e)}")
            raise
    
    def embed_single_text(self, text: str) -> List[float]:
        """嵌入单个文本"""
        logger.info(f"embed_single_text: text='{text[:100]}...', length={len(text)}")
        result = self.embed_texts([text])
        embedding = result.embeddings[0] if result.embeddings else []
        logger.info(f"embed_single_text 结果: embedding维度={len(embedding)}")
        return embedding
    
    async def embed_texts_async(self, texts: List[str]) -> EmbeddingResult:
        """异步嵌入文本列表"""
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                texts=[],
                model=self.model,
                dimension=self.dimension
            )
        
        logger.info(f"开始异步嵌入 {len(texts)} 个文本")
        
        # 分批处理
        all_embeddings = []
        all_texts = []
        total_tokens = 0
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = []
            
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                task = self._embed_batch_async(client, batch_texts)
                tasks.append(task)
            
            # 并发执行所有批次
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"批次 {i} 处理失败: {str(result)}")
                    raise result
                
                all_embeddings.extend(result.embeddings)
                all_texts.extend(result.texts)
                if result.token_count:
                    total_tokens += result.token_count
        
        result = EmbeddingResult(
            embeddings=all_embeddings,
            texts=all_texts,
            model=self.model,
            dimension=self.dimension,
            token_count=total_tokens if total_tokens > 0 else None
        )
        
        logger.info(f"异步嵌入完成: {len(all_embeddings)} 个向量")
        return result
    
    async def _embed_batch_async(self, client: httpx.AsyncClient, texts: List[str]) -> EmbeddingResult:
        """异步嵌入单个批次"""
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }
        
        try:
            response = await client.post(
                f"{self.api_base}/embeddings",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 提取嵌入向量
            embeddings = []
            for item in data["data"]:
                embeddings.append(item["embedding"])
            
            # 获取token使用量
            token_count = data.get("usage", {}).get("total_tokens")
            
            return EmbeddingResult(
                embeddings=embeddings,
                texts=texts,
                model=self.model,
                dimension=len(embeddings[0]) if embeddings else self.dimension,
                token_count=token_count
            )
            
        except Exception as e:
            logger.error(f"异步嵌入批次失败: {str(e)}")
            raise


class TextProcessor:
    """文本预处理器"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本"""
        import re
        
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        # 移除控制字符
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        return text.strip()
    
    @staticmethod
    def split_long_text(text: str, max_length: int = 8000) -> List[str]:
        """分割过长文本"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_length
            
            # 尝试在句号处分割
            if end < len(text):
                for i in range(end, max(start + max_length // 2, end - 200), -1):
                    if text[i] in '。！？\n':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end
        
        return chunks


class EmbeddingManager:
    """嵌入管理器 - 统一接口"""
    
    def __init__(self, provider: str = "siliconflow", **kwargs):
        self.provider = provider
        
        if provider == "siliconflow":
            self.embedder = SiliconFlowEmbedder(**kwargs)
        else:
            raise ValueError(f"不支持的嵌入提供商: {provider}")
        
        self.text_processor = TextProcessor()
        logger.info(f"嵌入管理器初始化: provider={provider}")
    
    def embed_documents(self, documents: List[str]) -> EmbeddingResult:
        """嵌入文档列表"""
        # 预处理文本
        processed_texts = []
        for text in documents:
            cleaned = self.text_processor.clean_text(text)
            # 分割过长文本
            chunks = self.text_processor.split_long_text(cleaned)
            processed_texts.extend(chunks)
        
        logger.info(f"文档预处理完成: {len(documents)} -> {len(processed_texts)} 个文本块")
        
        return self.embedder.embed_texts(processed_texts)
    
    def embed_query(self, query: str) -> List[float]:
        """嵌入查询文本"""
        cleaned_query = self.text_processor.clean_text(query)
        return self.embedder.embed_single_text(cleaned_query)
    
    async def embed_documents_async(self, documents: List[str]) -> EmbeddingResult:
        """异步嵌入文档列表"""
        processed_texts = []
        for text in documents:
            cleaned = self.text_processor.clean_text(text)
            chunks = self.text_processor.split_long_text(cleaned)
            processed_texts.extend(chunks)
        
        return await self.embedder.embed_texts_async(processed_texts)
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """计算余弦相似度"""
        arr1 = np.array(embedding1)
        arr2 = np.array(embedding2)
        
        # 计算余弦相似度
        dot_product = np.dot(arr1, arr2)
        norm_a = np.linalg.norm(arr1)
        norm_b = np.linalg.norm(arr2)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    @property
    def dimension(self) -> int:
        """获取嵌入维度"""
        return self.embedder.dimension
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.provider,
            "model": self.embedder.model,
            "dimension": self.dimension,
            "api_base": getattr(self.embedder, 'api_base', 'unknown')
        }