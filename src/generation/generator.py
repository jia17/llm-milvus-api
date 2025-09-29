from typing import List, Dict, Any, Optional, Iterator, AsyncIterator
from dataclasses import dataclass
from abc import ABC, abstractmethod
import httpx
import asyncio
import json
import time
import re

from loguru import logger
from src.utils.helpers import get_config, retry_on_failure
from src.retrieval.retriever import RetrievalResult
from src.vector_store.milvus_store import SearchHit


@dataclass
class GenerationResult:
    """生成结果数据结构"""
    question: str
    answer: str
    sources: List[SearchHit]
    retrieval_result: Optional[RetrievalResult] = None
    generation_time: float = 0.0
    total_time: float = 0.0
    model: str = ""
    token_usage: Optional[Dict[str, int]] = None


@dataclass
class ChatMessage:
    """聊天消息数据结构"""
    role: str  # system, user, assistant
    content: str


@dataclass
class IntentResult:
    """意图识别结果"""
    needs_rag: bool
    confidence: float
    intent_type: str
    reasoning: str


class BaseLLMClient(ABC):
    """LLM客户端基类"""

    @abstractmethod
    def generate(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        **kwargs
    ) -> str:
        """生成文本回复"""
        pass

    @abstractmethod
    def generate_stream(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> Iterator[str]:
        """流式生成文本"""
        pass

    @abstractmethod
    async def generate_async(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> str:
        """异步生成文本"""
        pass


class KimiLLMClient(BaseLLMClient):
    """Kimi (月之暗面) LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "moonshot-v1-8k",
        api_base: str = "https://api.moonshot.cn/v1",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_retries: int = 3,
        timeout: int = 60
    ):
        self.api_key = api_key or get_config("api_keys.kimi_api_key")
        self.model = model or get_config("llm.model", "moonshot-v1-8k")
        self.api_base = api_base.rstrip('/')
        self.max_tokens = max_tokens or get_config("llm.max_tokens", 4096)
        self.temperature = temperature or get_config("llm.temperature", 0.7)
        self.max_retries = max_retries or get_config("llm.max_retries", 3)
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError("Kimi API密钥未设置")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        logger.info(f"Kimi LLM客户端初始化: model={self.model}")
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def generate(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        **kwargs
    ) -> str:
        """生成文本回复"""
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "stream": stream
            }
            
            # 移除None值
            payload = {k: v for k, v in payload.items() if v is not None}
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
                else:
                    raise ValueError("API返回格式异常")
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"Kimi API HTTP错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LLM API调用失败: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Kimi API请求错误: {str(e)}")
            raise Exception(f"LLM API请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"LLM生成错误: {str(e)}")
            raise
    
    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Iterator[str]:
        """流式生成文本"""
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "stream": True
            }
            
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"流式生成失败: {str(e)}")
            raise
    
    async def generate_async(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> str:
        """异步生成文本"""
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "stream": False
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
                else:
                    raise ValueError("API返回格式异常")
                    
        except Exception as e:
            logger.error(f"异步生成失败: {str(e)}")
            raise


class IntentRecognizer:
    """意图识别器 - 判断是否需要RAG检索"""
    
    def __init__(self):
        # 需要RAG的关键词模式
        self.rag_keywords = {
            '文档', '资料', '内容', '信息', '数据', '记录', '报告', '说明',
            '什么是', '如何', '怎么', '为什么', '介绍', '解释', '定义',
            '具体', '详细', '举例', '案例', '实例', '方法', '步骤',
            '规则', '标准', '要求', '流程', '程序', '操作'
        }
        
        # 不需要RAG的关键词模式
        self.chat_keywords = {
            '你好', '谢谢', '再见', '不客气', '好的', '明白', '收到',
            '聊天', '闲聊', '天气', '心情', '感觉', '想法', '意见',
            '喜欢', '不喜欢', '开心', '难过', '高兴', '生气'
        }
        
        # 问句模式（通常需要RAG）
        self.question_patterns = [
            r'.*什么.*\?',
            r'.*如何.*\?', 
            r'.*怎么.*\?',
            r'.*为什么.*\?',
            r'.*哪.*\?',
            r'.*能.*介绍.*\?',
            r'.*解释.*\?'
        ]
        
        logger.info("意图识别器初始化完成")
    
    def recognize_intent(
        self, 
        question: str, 
        chat_history: List[ChatMessage] = None
    ) -> IntentResult:
        """识别用户意图，判断是否需要RAG"""
        try:
            # 文本预处理
            question_clean = question.strip().lower()
            
            # 1. 关键词匹配检查
            rag_score = sum(1 for kw in self.rag_keywords if kw in question_clean)
            chat_score = sum(1 for kw in self.chat_keywords if kw in question_clean)
            
            # 2. 问句模式检查
            question_pattern_score = sum(
                1 for pattern in self.question_patterns 
                if re.search(pattern, question_clean)
            )
            
            # 3. 历史上下文分析
            context_rag_score = 0
            if chat_history:
                recent_messages = chat_history[-3:]  # 只看最近3轮
                for msg in recent_messages:
                    if msg.role == 'assistant' and any(kw in msg.content for kw in ['根据文档', '基于资料', '文档显示']):
                        context_rag_score += 1
            
            # 4. 长度和复杂度检查
            length_score = 1 if len(question_clean) > 10 else 0
            
            # 综合评分
            total_rag_score = rag_score + question_pattern_score * 2 + context_rag_score + length_score
            total_chat_score = chat_score
            
            # 决策逻辑
            if total_rag_score > total_chat_score and total_rag_score >= 2:
                return IntentResult(
                    needs_rag=True,
                    confidence=min(0.9, 0.5 + total_rag_score * 0.1),
                    intent_type="knowledge_query",
                    reasoning=f"RAG评分: {total_rag_score}, 聊天评分: {total_chat_score}, 判定为知识查询"
                )
            elif total_chat_score > total_rag_score:
                return IntentResult(
                    needs_rag=False,
                    confidence=min(0.8, 0.5 + total_chat_score * 0.1),
                    intent_type="casual_chat",
                    reasoning=f"RAG评分: {total_rag_score}, 聊天评分: {total_chat_score}, 判定为闲聊"
                )
            else:
                # 默认使用RAG，但置信度较低
                return IntentResult(
                    needs_rag=True,
                    confidence=0.3,
                    intent_type="uncertain",
                    reasoning="意图不明确，默认使用RAG检索"
                )
                
        except Exception as e:
            logger.error(f"意图识别失败: {str(e)}")
            # 出错时默认使用RAG
            return IntentResult(
                needs_rag=True,
                confidence=0.5,
                intent_type="error_fallback",
                reasoning=f"意图识别出错，默认使用RAG: {str(e)}"
            )


class PromptTemplate:
    """提示词模板管理器"""
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一个专业的AI助手，能够基于提供的文档内容回答用户问题。

请遵循以下原则：
1. 仅基于提供的文档内容进行回答，不要编造信息
2. 如果文档中没有相关信息，请明确说明
3. 回答要准确、简洁、有条理
4. 适当引用文档中的关键信息
5. 使用中文回答

请根据以下文档内容回答用户的问题。"""

    # RAG回答模板
    RAG_TEMPLATE = """基于以下文档内容，请回答用户的问题：

文档内容：
{context}

用户问题：{question}

请基于上述文档内容进行回答："""
    
    # 无相关文档模板
    NO_CONTEXT_TEMPLATE = """很抱歉，我没有找到与您的问题相关的文档内容。

您的问题：{question}

建议：
1. 尝试使用不同的关键词重新提问
2. 确认问题是否在已上传的文档范围内
3. 检查问题的表述是否清晰

如果您需要上传新的文档，请使用文档上传功能。"""
    
    @classmethod
    def build_rag_prompt(cls, question: str, context_chunks: List[SearchHit]) -> List[ChatMessage]:
        """构建RAG提示词"""
        if not context_chunks:
            # 没有相关文档
            content = cls.NO_CONTEXT_TEMPLATE.format(question=question)
            return [
                ChatMessage(role="system", content=cls.SYSTEM_PROMPT),
                ChatMessage(role="user", content=content)
            ]
        
        # 构建上下文
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            source_info = f"[文档{i}]"
            if chunk.metadata.get("filename"):
                source_info += f" 来源：{chunk.metadata['filename']}"
            
            context_parts.append(f"{source_info}\n{chunk.content}")
        
        context = "\n\n".join(context_parts)
        
        # 构建完整提示词
        user_content = cls.RAG_TEMPLATE.format(
            context=context,
            question=question
        )
        
        return [
            ChatMessage(role="system", content=cls.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content)
        ]
    
    @classmethod
    def build_chat_prompt(cls, question: str, chat_history: List[ChatMessage] = None) -> List[ChatMessage]:
        """构建聊天提示词"""
        messages = [ChatMessage(role="system", content=cls.SYSTEM_PROMPT)]
        
        # 添加聊天历史
        if chat_history:
            messages.extend(chat_history)
        
        # 添加当前问题
        messages.append(ChatMessage(role="user", content=question))
        
        return messages


class RAGGenerator:
    """RAG生成器 - 结合检索和生成"""
    
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        max_context_length: int = 8000,
        min_similarity_score: float = 0.3
    ):
        self.llm_client = llm_client or LLMClientFactory.create_client()
        self.max_context_length = max_context_length
        self.min_similarity_score = min_similarity_score
        self.intent_recognizer = IntentRecognizer()
        
        logger.info("RAG生成器初始化完成")
    
    def generate_answer(
        self,
        question: str,
        retrieval_result: RetrievalResult,
        stream: bool = False,
        **kwargs
    ) -> GenerationResult:
        """生成RAG回答"""
        start_time = time.time()
        
        try:
            # 过滤低质量检索结果 - 详细日志
            logger.debug(f"=== 生成阶段过滤分析 ===")
            logger.debug(f"原始搜索结果: {len(retrieval_result.hits)} 个")
            for i, hit in enumerate(retrieval_result.hits):
                logger.debug(f"  结果{i+1}: score={hit.score:.4f}, content='{hit.content[:50]}...'")
            
            relevant_chunks = [
                hit for hit in retrieval_result.hits
                if hit.score >= self.min_similarity_score
            ]
            
            logger.debug(f"阈值: {self.min_similarity_score}")
            logger.debug(f"通过过滤: {len(relevant_chunks)} 个")
            for i, hit in enumerate(relevant_chunks):
                logger.debug(f"  保留{i+1}: score={hit.score:.4f}")
            
            logger.info(f"开始生成回答: 问题='{question}', 相关文档={len(relevant_chunks)}个")
            
            # 限制上下文长度
            filtered_chunks = self._filter_chunks_by_length(relevant_chunks)
            
            # 构建提示词
            messages = PromptTemplate.build_rag_prompt(question, filtered_chunks)
            
            generation_start = time.time()
            
            if stream:
                # 流式生成（这里简化处理，实际使用时需要特殊处理）
                answer_parts = []
                for chunk in self.llm_client.generate_stream(messages, **kwargs):
                    answer_parts.append(chunk)
                answer = "".join(answer_parts)
            else:
                # 标准生成
                answer = self.llm_client.generate(messages, **kwargs)
            
            generation_time = time.time() - generation_start
            total_time = time.time() - start_time
            
            result = GenerationResult(
                question=question,
                answer=answer,
                sources=filtered_chunks,
                retrieval_result=retrieval_result,
                generation_time=generation_time,
                total_time=total_time,
                model=self.llm_client.model
            )
            
            logger.info(f"回答生成完成: 生成耗时={generation_time:.2f}s, 总耗时={total_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            # 返回错误结果
            return GenerationResult(
                question=question,
                answer=f"抱歉，生成回答时出现错误: {str(e)}",
                sources=[],
                retrieval_result=retrieval_result,
                generation_time=0.0,
                total_time=time.time() - start_time,
                model=self.llm_client.model
            )
    
    def _filter_chunks_by_length(self, chunks: List[SearchHit]) -> List[SearchHit]:
        """根据长度限制过滤文档块"""
        filtered_chunks = []
        total_length = 0
        
        for chunk in chunks:
            chunk_length = len(chunk.content)
            
            if total_length + chunk_length <= self.max_context_length:
                filtered_chunks.append(chunk)
                total_length += chunk_length
            else:
                # 如果还有空间，截断当前块
                remaining_space = self.max_context_length - total_length
                if remaining_space > 100:  # 至少保留100字符
                    truncated_content = chunk.content[:remaining_space-3] + "..."
                    truncated_chunk = SearchHit(
                        id=chunk.id,
                        score=chunk.score,
                        content=truncated_content,
                        metadata=chunk.metadata,
                        doc_id=chunk.doc_id,
                        chunk_index=chunk.chunk_index
                    )
                    filtered_chunks.append(truncated_chunk)
                break
        
        logger.debug(f"=== 长度过滤 ===")
        logger.debug(f"长度过滤前: {len(chunks)} 个块")
        logger.debug(f"长度过滤后: {len(filtered_chunks)} 个块")
        logger.debug(f"总长度: {total_length} 字符")
        return filtered_chunks
    
    async def generate_answer_async(
        self,
        question: str,
        retrieval_result: RetrievalResult,
        **kwargs
    ) -> GenerationResult:
        """异步生成RAG回答"""
        start_time = time.time()
        
        try:
            # 过滤和准备上下文
            relevant_chunks = [
                hit for hit in retrieval_result.hits
                if hit.score >= self.min_similarity_score
            ]
            
            filtered_chunks = self._filter_chunks_by_length(relevant_chunks)
            messages = PromptTemplate.build_rag_prompt(question, filtered_chunks)
            
            generation_start = time.time()
            answer = await self.llm_client.generate_async(messages, **kwargs)
            generation_time = time.time() - generation_start
            
            return GenerationResult(
                question=question,
                answer=answer,
                sources=filtered_chunks,
                retrieval_result=retrieval_result,
                generation_time=generation_time,
                total_time=time.time() - start_time,
                model=self.llm_client.model
            )
            
        except Exception as e:
            logger.error(f"异步生成回答失败: {str(e)}")
            return GenerationResult(
                question=question,
                answer=f"抱歉，生成回答时出现错误: {str(e)}",
                sources=[],
                retrieval_result=retrieval_result,
                generation_time=0.0,
                total_time=time.time() - start_time,
                model=self.llm_client.model
            )
    
    def chat(
        self,
        question: str,
        chat_history: List[ChatMessage] = None,
        **kwargs
    ) -> str:
        """简单聊天（不使用RAG）"""
        try:
            # 使用简化的对话系统提示
            messages = []
            messages.append(ChatMessage(
                role="system", 
                content="你是一个友好的AI助手。保持对话的连贯性，用中文回答。"
            ))
            
            # 添加聊天历史
            if chat_history:
                messages.extend(chat_history)
            
            # 添加当前问题
            messages.append(ChatMessage(role="user", content=question))
            
            return self.llm_client.generate(messages, **kwargs)
        except Exception as e:
            logger.error(f"聊天生成失败: {str(e)}")
            return f"抱歉，聊天时出现错误: {str(e)}"
    
    def smart_conversation(
        self,
        question: str,
        chat_history: List[ChatMessage] = None,
        retrieval_func = None,
        stream: bool = False,
        enable_self_rag: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """智能多轮对话 - 自动判断是否需要RAG"""
        try:
            # 意图识别
            intent = self.intent_recognizer.recognize_intent(question, chat_history)

            logger.info(f"意图识别结果: {intent.intent_type}, 需要RAG: {intent.needs_rag}, 置信度: {intent.confidence:.2f}")
            logger.debug(f"推理过程: {intent.reasoning}")

            if intent.needs_rag and retrieval_func:
                # 检查是否启用Self-RAG
                if enable_self_rag and get_config("self_rag.enabled", True):
                    # 使用Self-RAG模式
                    try:
                        from src.evaluation.self_rag import SelfRAGController
                        from src.evaluation.retrieval_evaluator import RetrievalEvaluator
                        from src.evaluation.generation_evaluator import GenerationEvaluator

                        # 创建Self-RAG控制器
                        # 需要retriever对象，通过retrieval_func获取
                        retrieval_result = retrieval_func(question)

                        # 简化Self-RAG集成：直接评估当前检索和生成结果
                        retrieval_evaluator = RetrievalEvaluator(
                            min_relevance_threshold=get_config("self_rag.evaluation.retrieval.min_relevance_threshold", 0.5)
                        )
                        generation_evaluator = GenerationEvaluator(self.llm_client)

                        # 评估检索质量
                        retrieval_quality = retrieval_evaluator.evaluate_retrieval(question, retrieval_result)

                        generation_result = self.generate_multi_turn_answer(
                            question=question,
                            retrieval_result=retrieval_result,
                            chat_history=chat_history,
                            stream=stream,
                            **kwargs
                        )

                        # 评估生成质量
                        generation_quality = generation_evaluator.evaluate_generation(
                            question, generation_result.answer, generation_result.sources
                        )

                        # 计算综合置信度
                        confidence = (retrieval_quality.confidence + generation_quality.confidence) / 2

                        # 统计检索信息
                        chunks_retrieved = len(retrieval_result.hits) if retrieval_result else 0
                        chunks_filtered = len(generation_result.sources)

                        return {
                            "answer": generation_result.answer,
                            "mode": "self_rag",
                            "intent": intent.intent_type,
                            "confidence": confidence,
                            "sources": [{
                                "content": hit.content,
                                "score": hit.score,
                                "metadata": hit.metadata,
                                "doc_id": hit.doc_id,
                                "chunk_index": hit.chunk_index
                            } for hit in generation_result.sources],
                            "retrieval_time": generation_result.retrieval_result.retrieval_time if generation_result.retrieval_result else 0,
                            "generation_time": generation_result.generation_time,
                            "chunks_retrieved": chunks_retrieved,
                            "chunks_filtered": chunks_filtered,
                            "retrieval_quality": retrieval_evaluator.get_quality_summary(retrieval_quality),
                            "generation_quality": generation_evaluator.get_quality_summary(generation_quality),
                            "self_rag_enabled": True
                        }

                    except Exception as e:
                        logger.warning(f"Self-RAG模式失败，降级为普通RAG: {str(e)}")
                        # 降级为普通RAG模式
                        pass

                # 使用普通RAG模式
                try:
                    retrieval_result = retrieval_func(question)
                    generation_result = self.generate_multi_turn_answer(
                        question=question,
                        retrieval_result=retrieval_result,
                        chat_history=chat_history,
                        stream=stream,
                        **kwargs
                    )
                    
                    # 统计检索信息
                    chunks_retrieved = len(retrieval_result.hits) if retrieval_result else 0
                    chunks_filtered = len(generation_result.sources)
                    
                    return {
                        "answer": generation_result.answer,
                        "mode": "rag",
                        "intent": intent.intent_type,
                        "confidence": intent.confidence,
                        "sources": [{
                            "content": hit.content,
                            "score": hit.score,
                            "metadata": hit.metadata,
                            "doc_id": hit.doc_id,
                            "chunk_index": hit.chunk_index
                        } for hit in generation_result.sources],
                        "retrieval_time": generation_result.retrieval_result.retrieval_time if generation_result.retrieval_result else 0,
                        "generation_time": generation_result.generation_time,
                        "chunks_retrieved": chunks_retrieved,
                        "chunks_filtered": chunks_filtered,
                        "self_rag_enabled": False
                    }
                    
                except Exception as e:
                    logger.warning(f"RAG模式失败，降级为聊天模式: {str(e)}")
                    # 降级为聊天模式
                    intent.needs_rag = False
            
            if not intent.needs_rag:
                # 普通聊天模式
                answer = self.chat(question, chat_history, **kwargs)
                
                return {
                    "answer": answer,
                    "mode": "chat",
                    "intent": intent.intent_type,
                    "confidence": intent.confidence,
                    "sources": [],
                    "retrieval_time": 0,
                    "generation_time": 0,
                    "chunks_retrieved": 0,
                    "chunks_filtered": 0,
                    "self_rag_enabled": False
                }
            
        except Exception as e:
            logger.error(f"智能对话失败: {str(e)}")
            return {
                "answer": f"抱歉，对话处理时出现错误: {str(e)}",
                "mode": "error",
                "intent": "error",
                "confidence": 0,
                "sources": [],
                "retrieval_time": 0,
                "generation_time": 0,
                "chunks_retrieved": 0,
                "chunks_filtered": 0,
                "self_rag_enabled": False
            }
    
    def generate_multi_turn_answer(
        self,
        question: str,
        retrieval_result,
        chat_history: List[ChatMessage] = None,
        stream: bool = False,
        **kwargs
    ) -> GenerationResult:
        """生成多轮对话RAG回答"""
        start_time = time.time()
        
        try:
            # 过滤低质量检索结果
            relevant_chunks = [
                hit for hit in retrieval_result.hits
                if hit.score >= self.min_similarity_score
            ]
            
            logger.debug(f"多轮对话RAG: 过滤后相关文档 {len(relevant_chunks)} 个")
            
            # 限制上下文长度
            filtered_chunks = self._filter_chunks_by_length(relevant_chunks)
            
            # 构建多轮对话RAG提示词
            messages = self._build_multi_turn_rag_prompt(
                question, 
                filtered_chunks, 
                chat_history
            )
            
            generation_start = time.time()
            
            if stream:
                # 流式生成
                answer_parts = []
                for chunk in self.llm_client.generate_stream(messages, **kwargs):
                    answer_parts.append(chunk)
                answer = "".join(answer_parts)
            else:
                # 标准生成
                answer = self.llm_client.generate(messages, **kwargs)
            
            generation_time = time.time() - generation_start
            total_time = time.time() - start_time
            
            return GenerationResult(
                question=question,
                answer=answer,
                sources=filtered_chunks,
                retrieval_result=retrieval_result,
                generation_time=generation_time,
                total_time=total_time,
                model=self.llm_client.model
            )
            
        except Exception as e:
            logger.error(f"生成多轮对话RAG回答失败: {str(e)}")
            return GenerationResult(
                question=question,
                answer=f"抱歉，生成回答时出现错误: {str(e)}",
                sources=[],
                retrieval_result=retrieval_result,
                generation_time=0.0,
                total_time=time.time() - start_time,
                model=self.llm_client.model
            )
    
    def _build_multi_turn_rag_prompt(
        self, 
        question: str, 
        context_chunks: List, 
        chat_history: List[ChatMessage] = None
    ) -> List[ChatMessage]:
        """构建多轮对话RAG提示词"""
        messages = []
        
        if not context_chunks:
            # 没有相关文档，使用普通聊天模式
            system_prompt = "你是一个智能的AI助手，正在与用户进行多轮对话。\n\n注意：当前没有找到相关文档，请基于你的知识回答，并提醒用户这不是基于文档的回答。"
            messages.append(ChatMessage(role="system", content=system_prompt))
        else:
            # 构建包含文档内容的系统提示
            context_parts = []
            for i, chunk in enumerate(context_chunks, 1):
                source_info = f"[文档{i}]"
                if hasattr(chunk, 'metadata') and chunk.metadata and chunk.metadata.get("filename"):
                    source_info += f" 来源：{chunk.metadata['filename']}"
                context_parts.append(f"{source_info}\n{chunk.content}")
            
            context = "\n\n".join(context_parts)
            system_with_context = f"你正在进行一个多轮对话，需要基于提供的文档内容回答用户的问题。\n\n相关文档内容：\n{context}\n\n请结合文档内容和对话历史，准确回答用户的最新问题。如果当前问题涉及之前对话的内容，请保持上下文的一致性。"
            messages.append(ChatMessage(role="system", content=system_with_context))
        
        # 添加聊天历史
        if chat_history:
            messages.extend(chat_history)
        
        # 添加当前问题
        messages.append(ChatMessage(role="user", content=question))
        
        return messages
    
    def generate_answer_stream(self, question: str, retrieval_result, **kwargs) -> Iterator[str]:
        """流式生成RAG回答"""
        try:
            # 过滤和处理上下文
            relevant_chunks = [
                hit for hit in retrieval_result.hits
                if hit.score >= self.min_similarity_score
            ]
            
            filtered_chunks = self._filter_chunks_by_length(relevant_chunks)
            messages = PromptTemplate.build_rag_prompt(question, filtered_chunks)
            
            # 流式生成
            for chunk in self.llm_client.generate_stream(messages, **kwargs):
                yield chunk
                
        except Exception as e:
            logger.error(f"流式问答失败: {str(e)}")
            yield f"[ERROR: {str(e)}]"
    
    def update_config(
        self,
        max_context_length: Optional[int] = None,
        min_similarity_score: Optional[float] = None
    ):
        """更新配置"""
        if max_context_length is not None:
            self.max_context_length = max_context_length
        if min_similarity_score is not None:
            self.min_similarity_score = min_similarity_score
        
        logger.info(f"生成器配置已更新: max_context={self.max_context_length}, min_score={self.min_similarity_score}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取生成器统计信息"""
        return {
            "model": self.llm_client.model,
            "max_context_length": self.max_context_length,
            "min_similarity_score": self.min_similarity_score,
            "max_tokens": self.llm_client.max_tokens,
            "temperature": self.llm_client.temperature,
            "has_intent_recognizer": True
        }
    
    def generate_from_state(self, query: str, retrieval_results: List[SearchHit], chat_history: List[ChatMessage] = None) -> str:
        """直接从状态数据生成答案，无需构建RetrievalResult对象"""
        try:
            # 过滤低质量检索结果
            relevant_chunks = [
                hit for hit in retrieval_results
                if hit.score >= self.min_similarity_score
            ]
            
            logger.debug(f"LangGraph生成: 过滤后相关文档 {len(relevant_chunks)} 个")
            
            if not relevant_chunks:
                return "抱歉，没有找到足够相关的文档内容来回答您的问题。"
            
            # 限制上下文长度
            filtered_chunks = self._filter_chunks_by_length(relevant_chunks)
            
            # 构建提示词
            if chat_history:
                messages = self._build_multi_turn_rag_prompt(query, filtered_chunks, chat_history)
            else:
                messages = PromptTemplate.build_rag_prompt(query, filtered_chunks)
            
            # 生成答案
            response = self.llm_client.generate(messages)
            return response.strip()
            
        except Exception as e:
            logger.error(f"LangGraph生成失败: {str(e)}")
            return f"生成回答时出错: {str(e)}"
    
    def chat_from_state(self, query: str, chat_history: List[ChatMessage] = None) -> str:
        """直接从状态进行聊天，无需构建额外对象"""
        try:
            # 简单聊天模式
            messages = self._build_chat_messages(query, chat_history or [])
            response = self.llm_client.generate(messages)
            return response.strip()

        except Exception as e:
            logger.error(f"LangGraph聊天失败: {str(e)}")
            return f"聊天回答时出错: {str(e)}"

    def _build_chat_messages(self, query: str, chat_history: List[ChatMessage]) -> List[ChatMessage]:
        """构建聊天消息列表"""
        messages = [
            ChatMessage(role="system", content="你是一个智能的AI助手，用中文回答用户问题。")
        ]

        # 添加历史对话
        messages.extend(chat_history)

        # 添加当前问题
        messages.append(ChatMessage(role="user", content=query))

        return messages

    @staticmethod
    def create_self_rag_generator(
        retriever,
        llm_client: Optional[BaseLLMClient] = None,
        **config_overrides
    ):
        """工厂方法：创建带Self-RAG功能的生成器"""
        try:
            from src.evaluation.self_rag import SelfRAGController
            from src.evaluation.retrieval_evaluator import RetrievalEvaluator
            from src.evaluation.generation_evaluator import GenerationEvaluator

            # 基础生成器
            generator = RAGGenerator(llm_client)

            # Self-RAG组件
            retrieval_evaluator = RetrievalEvaluator(
                min_relevance_threshold=config_overrides.get(
                    'min_relevance_threshold',
                    get_config("self_rag.evaluation.retrieval.min_relevance_threshold", 0.5)
                )
            )

            generation_evaluator = GenerationEvaluator(
                llm_client=generator.llm_client
            )

            self_rag_controller = SelfRAGController(
                retriever=retriever,
                generator=generator,
                retrieval_evaluator=retrieval_evaluator,
                generation_evaluator=generation_evaluator,
                max_iterations=config_overrides.get(
                    'max_iterations',
                    get_config("self_rag.iteration.max_iterations", 3)
                ),
                min_retrieval_quality=config_overrides.get(
                    'min_retrieval_quality',
                    get_config("self_rag.quality_thresholds.min_retrieval_quality", 0.5)
                ),
                min_generation_quality=config_overrides.get(
                    'min_generation_quality',
                    get_config("self_rag.quality_thresholds.min_generation_quality", 0.6)
                )
            )

            return generator, self_rag_controller

        except Exception as e:
            logger.error(f"Self-RAG生成器创建失败: {str(e)}")
            return RAGGenerator(llm_client), None


class QwenLLMClient(BaseLLMClient):
    """Qwen (通义千问) LLM客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen-plus",
        api_base: str = "https://dashscope.aliyuncs.com/api/v1",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_retries: int = 3,
        timeout: int = 60
    ):
        self.api_key = api_key or get_config("api_keys.qwen_api_key")
        self.model = model or get_config("llm.qwen.model", "qwen-plus")
        self.api_base = api_base.rstrip('/')
        self.max_tokens = max_tokens or get_config("llm.qwen.max_tokens", 4096)
        self.temperature = temperature or get_config("llm.qwen.temperature", 0.7)
        self.max_retries = max_retries or get_config("llm.qwen.max_retries", 3)
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("Qwen API密钥未设置")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"Qwen LLM客户端初始化: model={self.model}")

    @retry_on_failure(max_retries=3, delay=1.0)
    def generate(
        self,
        messages: List[ChatMessage],
        stream: bool = False,
        **kwargs
    ) -> str:
        """生成文本回复"""
        try:
            payload = {
                "model": self.model,
                "input": {
                    "messages": [{"role": msg.role, "content": msg.content} for msg in messages]
                },
                "parameters": {
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "stream": stream
                }
            }

            # 移除None值
            payload = {k: v for k, v in payload.items() if v is not None}

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()

                if "output" in data and "text" in data["output"]:
                    content = data["output"]["text"]
                    return content.strip()
                else:
                    raise ValueError("Qwen API返回格式异常")

        except httpx.HTTPStatusError as e:
            logger.error(f"Qwen API HTTP错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LLM API调用失败: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Qwen API请求错误: {str(e)}")
            raise Exception(f"LLM API请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"Qwen LLM生成错误: {str(e)}")
            raise

    def generate_stream(self, messages: List[ChatMessage], **kwargs) -> Iterator[str]:
        """流式生成文本"""
        try:
            payload = {
                "model": self.model,
                "input": {
                    "messages": [{"role": msg.role, "content": msg.content} for msg in messages]
                },
                "parameters": {
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "stream": True,
                    "incremental_output": True
                }
            }

            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=self.headers,
                    json=payload
                ) as response:
                    response.raise_for_status()

                    for line in response.iter_lines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str and data_str != "[DONE]":
                                try:
                                    data = json.loads(data_str)
                                    if "output" in data and "text" in data["output"]:
                                        yield data["output"]["text"]
                                except json.JSONDecodeError:
                                    continue

        except Exception as e:
            logger.error(f"Qwen流式生成失败: {str(e)}")
            raise

    async def generate_async(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> str:
        """异步生成文本"""
        try:
            payload = {
                "model": self.model,
                "input": {
                    "messages": [{"role": msg.role, "content": msg.content} for msg in messages]
                },
                "parameters": {
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "stream": False
                }
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()

                if "output" in data and "text" in data["output"]:
                    content = data["output"]["text"]
                    return content.strip()
                else:
                    raise ValueError("Qwen API返回格式异常")

        except Exception as e:
            logger.error(f"Qwen异步生成失败: {str(e)}")
            raise


class LLMClientFactory:
    """LLM客户端工厂"""

    @staticmethod
    def create_client(provider: str = None, **kwargs) -> BaseLLMClient:
        """创建LLM客户端"""
        provider = provider or get_config("llm.provider", "kimi")

        if provider.lower() == "kimi":
            return KimiLLMClient(**kwargs)
        elif provider.lower() == "qwen":
            return QwenLLMClient(**kwargs)
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")

    @staticmethod
    def get_available_providers() -> List[str]:
        """获取可用的提供商列表"""
        return ["kimi", "qwen"]