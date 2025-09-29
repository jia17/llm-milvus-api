from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import time
from loguru import logger

from src.vector_store.milvus_store import SearchHit
from src.retrieval.retriever import RetrievalResult, HybridRetriever
from src.generation.generator import GenerationResult, RAGGenerator, ChatMessage
from src.evaluation.retrieval_evaluator import RetrievalEvaluator, RetrievalQuality
from src.evaluation.generation_evaluator import GenerationEvaluator, GenerationQuality


class SelfRAGAction(Enum):
    """Self-RAG 行动决策"""
    CONTINUE = "continue"           # 继续生成答案
    RETRIEVE = "retrieve"           # 重新检索
    CLARIFY = "clarify"            # 需要澄清问题
    REJECT = "reject"              # 拒绝回答
    IMPROVE = "improve"            # 改进答案


@dataclass
class SelfRAGResult:
    """Self-RAG 完整结果"""
    query: str
    final_answer: str
    actions_taken: List[SelfRAGAction]
    retrieval_quality: Optional[RetrievalQuality]
    generation_quality: Optional[GenerationQuality]
    iteration_count: int
    total_time: float
    confidence: float
    sources: List[SearchHit]
    metadata: Dict[str, Any]


class SelfRAGController:
    """Self-RAG 控制器 - 自我反思的检索增强生成"""

    def __init__(
        self,
        retriever: HybridRetriever,
        generator: RAGGenerator,
        retrieval_evaluator: Optional[RetrievalEvaluator] = None,
        generation_evaluator: Optional[GenerationEvaluator] = None,
        max_iterations: int = 3,
        min_retrieval_quality: float = 0.5,
        min_generation_quality: float = 0.6
    ):
        self.retriever = retriever
        self.generator = generator
        self.retrieval_evaluator = retrieval_evaluator or RetrievalEvaluator()
        self.generation_evaluator = generation_evaluator or GenerationEvaluator()

        self.max_iterations = max_iterations
        self.min_retrieval_quality = min_retrieval_quality
        self.min_generation_quality = min_generation_quality

        logger.info(f"Self-RAG控制器初始化: max_iter={max_iterations}, "
                   f"min_retrieval={min_retrieval_quality}, min_generation={min_generation_quality}")

    def generate_with_self_rag(
        self,
        query: str,
        chat_history: Optional[List[ChatMessage]] = None,
        retrieval_params: Optional[Dict[str, Any]] = None,
        generation_params: Optional[Dict[str, Any]] = None
    ) -> SelfRAGResult:
        """带自我反思的生成流程"""
        start_time = time.time()
        actions_taken = []
        iteration_count = 0

        retrieval_quality = None
        generation_quality = None
        final_answer = ""
        sources = []

        try:
            logger.info(f"Self-RAG开始: query='{query}'")

            # 主循环 - 最多迭代 max_iterations 次
            while iteration_count < self.max_iterations:
                iteration_count += 1
                logger.info(f"=== Self-RAG 第 {iteration_count} 轮 ===")

                # 1. 检索阶段
                retrieval_result = self._perform_retrieval(query, retrieval_params)

                # 2. 检索质量评估
                retrieval_quality = self.retrieval_evaluator.evaluate_retrieval(
                    query, retrieval_result
                )

                logger.info(f"检索质量评估: score={retrieval_quality.relevance_score:.3f}, "
                           f"sufficient={retrieval_quality.is_sufficient}")

                # 3. 检索质量决策
                retrieval_action = self._decide_retrieval_action(retrieval_quality)
                actions_taken.append(retrieval_action)

                if retrieval_action == SelfRAGAction.REJECT:
                    final_answer = "抱歉，没有找到足够相关的信息来回答您的问题。"
                    break
                elif retrieval_action == SelfRAGAction.CLARIFY:
                    final_answer = "您的问题需要更多具体信息。请尝试提供更详细的描述或重新表述问题。"
                    break
                elif retrieval_action == SelfRAGAction.RETRIEVE and iteration_count < self.max_iterations:
                    # 调整检索策略后重试
                    retrieval_params = self._adjust_retrieval_params(retrieval_params, retrieval_quality)
                    continue

                # 4. 生成阶段
                generation_result = self._perform_generation(
                    query, retrieval_result, chat_history, generation_params
                )

                # 5. 生成质量评估
                generation_quality = self.generation_evaluator.evaluate_generation(
                    query, generation_result.answer, generation_result.sources
                )

                logger.info(f"生成质量评估: score={generation_quality.overall_score:.3f}, "
                           f"reliable={generation_quality.is_reliable}")

                # 6. 生成质量决策
                generation_action = self._decide_generation_action(generation_quality)
                actions_taken.append(generation_action)

                if generation_action == SelfRAGAction.CONTINUE:
                    final_answer = generation_result.answer
                    sources = generation_result.sources
                    break
                elif generation_action == SelfRAGAction.IMPROVE and iteration_count < self.max_iterations:
                    # 调整生成参数后重试
                    generation_params = self._adjust_generation_params(generation_params, generation_quality)
                    continue
                else:
                    # 最后一轮或其他情况，使用当前答案
                    final_answer = generation_result.answer
                    sources = generation_result.sources
                    break

            # 计算总体置信度
            confidence = self._calculate_overall_confidence(retrieval_quality, generation_quality)

            # 构建结果
            result = SelfRAGResult(
                query=query,
                final_answer=final_answer,
                actions_taken=actions_taken,
                retrieval_quality=retrieval_quality,
                generation_quality=generation_quality,
                iteration_count=iteration_count,
                total_time=time.time() - start_time,
                confidence=confidence,
                sources=sources,
                metadata={
                    "retrieval_params": retrieval_params,
                    "generation_params": generation_params,
                    "max_iterations_reached": iteration_count >= self.max_iterations
                }
            )

            logger.info(f"Self-RAG完成: 迭代{iteration_count}轮, 置信度={confidence:.3f}, "
                       f"耗时={result.total_time:.2f}s")

            return result

        except Exception as e:
            logger.error(f"Self-RAG失败: {str(e)}")
            return SelfRAGResult(
                query=query,
                final_answer=f"生成回答时出现错误: {str(e)}",
                actions_taken=actions_taken,
                retrieval_quality=retrieval_quality,
                generation_quality=generation_quality,
                iteration_count=iteration_count,
                total_time=time.time() - start_time,
                confidence=0.0,
                sources=[],
                metadata={"error": str(e)}
            )

    def _perform_retrieval(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """执行检索"""
        try:
            # 使用参数或默认值
            top_k = params.get('top_k', 5) if params else 5
            method = params.get('method', 'hybrid') if params else 'hybrid'

            return self.retriever.search(query, top_k=top_k, method=method)

        except Exception as e:
            logger.error(f"检索执行失败: {str(e)}")
            # 返回空结果
            return RetrievalResult(
                query=query,
                hits=[],
                dense_hits=[],
                sparse_hits=[],
                total_hits=0,
                retrieval_time=0.0,
                method="error"
            )

    def _perform_generation(
        self,
        query: str,
        retrieval_result: RetrievalResult,
        chat_history: Optional[List[ChatMessage]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> GenerationResult:
        """执行生成"""
        try:
            if chat_history:
                # 多轮对话生成
                return self.generator.generate_multi_turn_answer(
                    query, retrieval_result, chat_history, **(params or {})
                )
            else:
                # 单轮生成
                return self.generator.generate_answer(
                    query, retrieval_result, **(params or {})
                )

        except Exception as e:
            logger.error(f"生成执行失败: {str(e)}")
            # 返回错误结果
            return GenerationResult(
                question=query,
                answer=f"生成回答时出错: {str(e)}",
                sources=[],
                retrieval_result=retrieval_result,
                generation_time=0.0,
                total_time=0.0,
                model=""
            )

    def _decide_retrieval_action(self, quality: RetrievalQuality) -> SelfRAGAction:
        """决定检索后的行动"""
        try:
            # 检索质量足够好
            if quality.relevance_score >= self.min_retrieval_quality and quality.is_sufficient:
                return SelfRAGAction.CONTINUE

            # 质量太差，无法挽救
            if quality.relevance_score < 0.2:
                return SelfRAGAction.REJECT

            # 中等质量，可能需要澄清
            if quality.relevance_score < 0.4:
                return SelfRAGAction.CLARIFY

            # 质量不够但可以改进
            return SelfRAGAction.RETRIEVE

        except Exception as e:
            logger.warning(f"检索决策失败: {str(e)}")
            return SelfRAGAction.CONTINUE

    def _decide_generation_action(self, quality: GenerationQuality) -> SelfRAGAction:
        """决定生成后的行动"""
        try:
            # 生成质量足够好
            if quality.overall_score >= self.min_generation_quality and quality.is_reliable:
                return SelfRAGAction.CONTINUE

            # 忠实度太低，可能有幻觉
            if quality.faithfulness_score < 0.3:
                return SelfRAGAction.RETRIEVE  # 重新检索

            # 其他质量问题，尝试改进生成
            if quality.overall_score < self.min_generation_quality:
                return SelfRAGAction.IMPROVE

            return SelfRAGAction.CONTINUE

        except Exception as e:
            logger.warning(f"生成决策失败: {str(e)}")
            return SelfRAGAction.CONTINUE

    def _adjust_retrieval_params(
        self,
        current_params: Optional[Dict[str, Any]],
        quality: RetrievalQuality
    ) -> Dict[str, Any]:
        """调整检索参数"""
        params = current_params.copy() if current_params else {}

        try:
            # 根据质量问题调整参数
            if "缺乏文档多样性" in quality.quality_issues:
                params['top_k'] = params.get('top_k', 5) + 3

            if "检索结果中存在重复内容" in quality.quality_issues:
                params['method'] = 'dense'  # 更依赖向量检索

            if "大部分检索结果相关性较低" in quality.quality_issues:
                params['method'] = 'hybrid'  # 使用混合检索
                params['top_k'] = min(params.get('top_k', 5) + 2, 10)

            logger.info(f"调整检索参数: {params}")
            return params

        except Exception as e:
            logger.warning(f"检索参数调整失败: {str(e)}")
            return params

    def _adjust_generation_params(
        self,
        current_params: Optional[Dict[str, Any]],
        quality: GenerationQuality
    ) -> Dict[str, Any]:
        """调整生成参数"""
        params = current_params.copy() if current_params else {}

        try:
            # 根据质量问题调整参数
            if quality.faithfulness_score < 0.5:
                # 降低温度，提高确定性
                params['temperature'] = 0.3

            if quality.completeness_score < 0.5:
                # 增加最大token数
                params['max_tokens'] = params.get('max_tokens', 4096) + 1000

            if "不确定表述过多" in quality.quality_issues:
                # 降低温度
                params['temperature'] = 0.1

            logger.info(f"调整生成参数: {params}")
            return params

        except Exception as e:
            logger.warning(f"生成参数调整失败: {str(e)}")
            return params

    def _calculate_overall_confidence(
        self,
        retrieval_quality: Optional[RetrievalQuality],
        generation_quality: Optional[GenerationQuality]
    ) -> float:
        """计算总体置信度"""
        try:
            if not retrieval_quality or not generation_quality:
                return 0.0

            # 综合评估
            retrieval_score = retrieval_quality.relevance_score * retrieval_quality.confidence
            generation_score = generation_quality.overall_score * generation_quality.confidence

            # 加权平均
            overall_confidence = retrieval_score * 0.4 + generation_score * 0.6

            return min(overall_confidence, 1.0)

        except Exception as e:
            logger.warning(f"置信度计算失败: {str(e)}")
            return 0.0

    def quick_generate(
        self,
        query: str,
        enable_self_evaluation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """快速生成（简化版Self-RAG）"""
        try:
            if not enable_self_evaluation:
                # 直接使用原有流程
                retrieval_result = self.retriever.search(query)
                generation_result = self.generator.generate_answer(query, retrieval_result)

                return {
                    "answer": generation_result.answer,
                    "sources": generation_result.sources,
                    "confidence": 0.5,  # 默认置信度
                    "self_rag_enabled": False
                }

            # 执行完整的Self-RAG
            result = self.generate_with_self_rag(query, **kwargs)

            return {
                "answer": result.final_answer,
                "sources": result.sources,
                "confidence": result.confidence,
                "actions_taken": [action.value for action in result.actions_taken],
                "iteration_count": result.iteration_count,
                "retrieval_quality": (
                    self.retrieval_evaluator.get_quality_summary(result.retrieval_quality)
                    if result.retrieval_quality else None
                ),
                "generation_quality": (
                    self.generation_evaluator.get_quality_summary(result.generation_quality)
                    if result.generation_quality else None
                ),
                "self_rag_enabled": True
            }

        except Exception as e:
            logger.error(f"快速生成失败: {str(e)}")
            return {
                "answer": f"生成回答时出错: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "self_rag_enabled": enable_self_evaluation,
                "error": str(e)
            }

    def update_thresholds(
        self,
        min_retrieval_quality: Optional[float] = None,
        min_generation_quality: Optional[float] = None
    ):
        """更新质量阈值"""
        if min_retrieval_quality is not None:
            self.min_retrieval_quality = min_retrieval_quality
        if min_generation_quality is not None:
            self.min_generation_quality = min_generation_quality

        logger.info(f"质量阈值已更新: retrieval={self.min_retrieval_quality}, "
                   f"generation={self.min_generation_quality}")

    def get_stats(self) -> Dict[str, Any]:
        """获取控制器统计信息"""
        return {
            "max_iterations": self.max_iterations,
            "min_retrieval_quality": self.min_retrieval_quality,
            "min_generation_quality": self.min_generation_quality,
            "retrieval_evaluator": type(self.retrieval_evaluator).__name__,
            "generation_evaluator": type(self.generation_evaluator).__name__
        }