from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re
import jieba
import numpy as np
from loguru import logger

from src.vector_store.milvus_store import SearchHit
from src.retrieval.retriever import RetrievalResult


@dataclass
class RetrievalQuality:
    """检索质量评估结果"""
    relevance_score: float  # 0-1, 相关性分数
    confidence: float      # 0-1, 评估置信度
    is_sufficient: bool    # 检索结果是否足够
    quality_issues: List[str]  # 质量问题列表
    recommendation: str    # 建议操作


class RetrievalEvaluator:
    """检索质量评估器 - 评估检索结果的相关性和充分性"""

    def __init__(self, min_relevance_threshold: float = 0.5):
        self.min_relevance_threshold = min_relevance_threshold

        # 停用词
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
            '会', '着', '没有', '看', '好', '自己', '这', '那', '它', '他', '她'
        }

        logger.info(f"检索评估器初始化: 相关性阈值={min_relevance_threshold}")

    def evaluate_retrieval(
        self,
        query: str,
        retrieval_result: RetrievalResult
    ) -> RetrievalQuality:
        """评估检索质量"""
        try:
            if not retrieval_result.hits:
                return RetrievalQuality(
                    relevance_score=0.0,
                    confidence=1.0,
                    is_sufficient=False,
                    quality_issues=["没有检索到任何文档"],
                    recommendation="需要扩展查询或检查文档库"
                )

            # 1. 计算查询-文档相关性
            relevance_scores = []
            for hit in retrieval_result.hits:
                relevance = self._calculate_semantic_relevance(query, hit.content)
                relevance_scores.append(relevance)

            # 2. 计算整体相关性分数
            avg_relevance = np.mean(relevance_scores)
            max_relevance = max(relevance_scores) if relevance_scores else 0.0

            # 3. 评估检索充分性
            sufficient_hits = [
                score for score in relevance_scores
                if score >= self.min_relevance_threshold
            ]

            is_sufficient = len(sufficient_hits) >= 1 and max_relevance >= 0.6

            # 4. 识别质量问题
            quality_issues = self._identify_quality_issues(
                query, retrieval_result.hits, relevance_scores
            )

            # 5. 生成建议
            recommendation = self._generate_recommendation(
                avg_relevance, max_relevance, len(sufficient_hits), quality_issues
            )

            # 6. 计算评估置信度
            confidence = self._calculate_confidence(relevance_scores, retrieval_result)

            return RetrievalQuality(
                relevance_score=avg_relevance,
                confidence=confidence,
                is_sufficient=is_sufficient,
                quality_issues=quality_issues,
                recommendation=recommendation
            )

        except Exception as e:
            logger.error(f"检索评估失败: {str(e)}")
            return RetrievalQuality(
                relevance_score=0.0,
                confidence=0.0,
                is_sufficient=False,
                quality_issues=[f"评估过程出错: {str(e)}"],
                recommendation="重新尝试检索"
            )

    def _calculate_semantic_relevance(self, query: str, content: str) -> float:
        """计算语义相关性分数"""
        try:
            # 分词和清理
            query_tokens = self._tokenize_and_clean(query)
            content_tokens = self._tokenize_and_clean(content)

            if not query_tokens or not content_tokens:
                return 0.0

            # 1. 词汇重叠率
            query_set = set(query_tokens)
            content_set = set(content_tokens)
            overlap_ratio = len(query_set & content_set) / len(query_set)

            # 2. 关键词密度检查
            keyword_density = sum(
                content_tokens.count(token) for token in query_tokens
            ) / len(content_tokens)

            # 3. 语义接近度（简化版）
            semantic_score = self._calculate_semantic_similarity(query_tokens, content_tokens)

            # 综合评分
            relevance_score = (
                overlap_ratio * 0.4 +
                min(keyword_density * 10, 1.0) * 0.3 +
                semantic_score * 0.3
            )

            return min(relevance_score, 1.0)

        except Exception as e:
            logger.warning(f"相关性计算失败: {str(e)}")
            return 0.0

    def _tokenize_and_clean(self, text: str) -> List[str]:
        """分词和清理"""
        # 分词
        tokens = list(jieba.cut(text.lower()))

        # 过滤停用词和短词
        cleaned_tokens = [
            token for token in tokens
            if (token not in self.stop_words and
                len(token) > 1 and
                not token.isspace())
        ]

        return cleaned_tokens

    def _calculate_semantic_similarity(self, query_tokens: List[str], content_tokens: List[str]) -> float:
        """计算语义相似度（简化版）"""
        try:
            # 检查同义词和相关词（简化处理）
            similarity_map = {
                '什么': ['介绍', '定义', '解释', '说明'],
                '如何': ['方法', '步骤', '流程', '操作'],
                '为什么': ['原因', '因为', '由于', '原理'],
                '哪里': ['位置', '地方', '所在', '地点'],
                '什么时候': ['时间', '时候', '何时', '日期']
            }

            similarity_score = 0.0
            total_checks = 0

            for query_token in query_tokens:
                total_checks += 1
                if query_token in similarity_map:
                    related_words = similarity_map[query_token]
                    if any(word in content_tokens for word in related_words):
                        similarity_score += 1.0
                elif query_token in content_tokens:
                    similarity_score += 1.0

            return similarity_score / total_checks if total_checks > 0 else 0.0

        except Exception as e:
            logger.warning(f"语义相似度计算失败: {str(e)}")
            return 0.0

    def _identify_quality_issues(
        self,
        query: str,
        hits: List[SearchHit],
        relevance_scores: List[float]
    ) -> List[str]:
        """识别质量问题"""
        issues = []

        try:
            # 检查相关性过低
            low_relevance_count = sum(1 for score in relevance_scores if score < 0.3)
            if low_relevance_count > len(relevance_scores) * 0.8:
                issues.append("大部分检索结果相关性较低")

            # 检查内容重复
            contents = [hit.content for hit in hits]
            unique_contents = len(set(contents))
            if unique_contents < len(contents) * 0.7:
                issues.append("检索结果中存在重复内容")

            # 检查文档多样性
            doc_ids = [hit.doc_id for hit in hits]
            unique_docs = len(set(doc_ids))
            if unique_docs < 2 and len(hits) > 3:
                issues.append("检索结果缺乏文档多样性")

            # 检查分数分布
            if relevance_scores:
                score_range = max(relevance_scores) - min(relevance_scores)
                if score_range < 0.1:
                    issues.append("检索结果分数区分度不够")

            return issues

        except Exception as e:
            logger.warning(f"质量问题识别失败: {str(e)}")
            return ["质量评估部分出错"]

    def _generate_recommendation(
        self,
        avg_relevance: float,
        max_relevance: float,
        sufficient_count: int,
        quality_issues: List[str]
    ) -> str:
        """生成改进建议"""
        if max_relevance >= 0.8 and sufficient_count >= 2:
            return "检索质量良好，可以继续生成答案"
        elif max_relevance >= 0.6 and sufficient_count >= 1:
            return "检索质量中等，建议谨慎生成答案并标注不确定性"
        elif max_relevance >= 0.4:
            return "检索质量较低，建议重新构造查询或扩展检索范围"
        else:
            return "检索质量不足，建议更换查询策略或提示用户补充信息"

    def _calculate_confidence(
        self,
        relevance_scores: List[float],
        retrieval_result: RetrievalResult
    ) -> float:
        """计算评估置信度"""
        try:
            if not relevance_scores:
                return 0.0

            # 基于分数稳定性
            score_std = np.std(relevance_scores)
            stability_factor = max(0, 1 - score_std)

            # 基于检索数量
            count_factor = min(len(relevance_scores) / 5.0, 1.0)

            # 基于检索方法
            method_factor = 0.9 if retrieval_result.method == "hybrid" else 0.7

            confidence = stability_factor * 0.5 + count_factor * 0.3 + method_factor * 0.2

            return min(confidence, 1.0)

        except Exception as e:
            logger.warning(f"置信度计算失败: {str(e)}")
            return 0.5

    def get_quality_summary(self, quality: RetrievalQuality) -> Dict[str, Any]:
        """获取质量评估摘要"""
        return {
            "relevance_score": round(quality.relevance_score, 3),
            "confidence": round(quality.confidence, 3),
            "is_sufficient": quality.is_sufficient,
            "quality_level": self._get_quality_level(quality.relevance_score),
            "issues_count": len(quality.quality_issues),
            "recommendation": quality.recommendation
        }

    def _get_quality_level(self, score: float) -> str:
        """获取质量等级"""
        if score >= 0.8:
            return "优秀"
        elif score >= 0.6:
            return "良好"
        elif score >= 0.4:
            return "中等"
        elif score >= 0.2:
            return "较差"
        else:
            return "很差"