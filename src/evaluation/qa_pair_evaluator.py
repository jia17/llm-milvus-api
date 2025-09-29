"""QA对评估器

基于标准答案的问答评估器，用于更精确的RAG效果评估。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import jieba
import numpy as np
from loguru import logger

from src.evaluation.generation_evaluator import GenerationQuality
from src.vector_store.milvus_store import SearchHit


@dataclass
class QAComparisonResult:
    """QA对比结果"""
    question: str
    ground_truth: str
    rag_answer: str
    baseline_answer: str
    rag_similarity: float  # 与标准答案的相似度
    baseline_similarity: float
    rag_completeness: float  # 答案完整性
    baseline_completeness: float
    rag_accuracy: float  # 事实准确性
    baseline_accuracy: float
    winner: str  # "rag", "baseline", "tie"


class QAPairEvaluator:
    """QA对评估器"""

    def __init__(self):
        """初始化评估器"""
        # 停用词
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
            '会', '着', '没有', '看', '好', '自己', '这', '那', '它', '他', '她',
            '我们', '你们', '他们', '什么', '怎么', '为什么', '哪里', '什么时候'
        }

        logger.info("QA对评估器初始化完成")

    def evaluate_qa_pair(
        self,
        question: str,
        ground_truth: str,
        rag_answer: str,
        baseline_answer: str,
        source_chunks: Optional[List[SearchHit]] = None
    ) -> QAComparisonResult:
        """评估QA对"""
        try:
            # 1. 计算与标准答案的相似度
            rag_similarity = self._calculate_text_similarity(ground_truth, rag_answer)
            baseline_similarity = self._calculate_text_similarity(ground_truth, baseline_answer)

            # 2. 计算答案完整性（相对于标准答案的信息覆盖度）
            rag_completeness = self._calculate_completeness(ground_truth, rag_answer)
            baseline_completeness = self._calculate_completeness(ground_truth, baseline_answer)

            # 3. 计算事实准确性（是否包含错误信息）
            rag_accuracy = self._calculate_accuracy(ground_truth, rag_answer, source_chunks)
            baseline_accuracy = self._calculate_accuracy(ground_truth, baseline_answer, None)

            # 4. 确定获胜者
            winner = self._determine_winner_qa(
                rag_similarity, baseline_similarity,
                rag_completeness, baseline_completeness,
                rag_accuracy, baseline_accuracy
            )

            return QAComparisonResult(
                question=question,
                ground_truth=ground_truth,
                rag_answer=rag_answer,
                baseline_answer=baseline_answer,
                rag_similarity=rag_similarity,
                baseline_similarity=baseline_similarity,
                rag_completeness=rag_completeness,
                baseline_completeness=baseline_completeness,
                rag_accuracy=rag_accuracy,
                baseline_accuracy=baseline_accuracy,
                winner=winner
            )

        except Exception as e:
            logger.error(f"QA对评估失败: {str(e)}")
            raise

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        try:
            # 分词和清理
            tokens1 = self._tokenize_and_clean(text1)
            tokens2 = self._tokenize_and_clean(text2)

            if not tokens1 or not tokens2:
                return 0.0

            # 计算词汇重叠度（Jaccard相似度）
            set1 = set(tokens1)
            set2 = set(tokens2)

            intersection = len(set1 & set2)
            union = len(set1 | set2)

            jaccard_sim = intersection / union if union > 0 else 0.0

            # 计算TF相似度
            tf_sim = self._calculate_tf_similarity(tokens1, tokens2)

            # 综合相似度
            similarity = jaccard_sim * 0.6 + tf_sim * 0.4

            return min(similarity, 1.0)

        except Exception as e:
            logger.warning(f"文本相似度计算失败: {str(e)}")
            return 0.0

    def _calculate_tf_similarity(self, tokens1: List[str], tokens2: List[str]) -> float:
        """计算TF相似度"""
        try:
            # 构建词汇表
            vocab = set(tokens1 + tokens2)

            # 计算TF向量
            tf1 = [tokens1.count(word) / len(tokens1) for word in vocab]
            tf2 = [tokens2.count(word) / len(tokens2) for word in vocab]

            # 计算余弦相似度
            dot_product = sum(a * b for a, b in zip(tf1, tf2))
            norm1 = sum(a * a for a in tf1) ** 0.5
            norm2 = sum(b * b for b in tf2) ** 0.5

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)

        except Exception as e:
            logger.warning(f"TF相似度计算失败: {str(e)}")
            return 0.0

    def _calculate_completeness(self, ground_truth: str, answer: str) -> float:
        """计算答案完整性"""
        try:
            # 分析标准答案中的关键信息点
            gt_tokens = self._tokenize_and_clean(ground_truth)
            ans_tokens = self._tokenize_and_clean(answer)

            if not gt_tokens:
                return 1.0

            # 提取关键概念（长度大于1的词汇）
            gt_concepts = [token for token in gt_tokens if len(token) > 1]
            ans_concepts = [token for token in ans_tokens if len(token) > 1]

            if not gt_concepts:
                return 1.0

            # 计算关键概念覆盖率
            covered_concepts = sum(1 for concept in gt_concepts if concept in ans_concepts)
            completeness = covered_concepts / len(gt_concepts)

            # 考虑答案长度因素
            length_factor = min(len(ans_tokens) / len(gt_tokens), 1.0)

            # 综合完整性
            final_completeness = completeness * 0.7 + length_factor * 0.3

            return min(final_completeness, 1.0)

        except Exception as e:
            logger.warning(f"完整性计算失败: {str(e)}")
            return 0.5

    def _calculate_accuracy(
        self,
        ground_truth: str,
        answer: str,
        source_chunks: Optional[List[SearchHit]] = None
    ) -> float:
        """计算事实准确性"""
        try:
            # 检查是否包含与标准答案明显矛盾的信息
            gt_tokens = self._tokenize_and_clean(ground_truth)
            ans_tokens = self._tokenize_and_clean(answer)

            # 基础准确性：检查是否有明显错误的数字、日期等
            accuracy = 1.0

            # 检查数字一致性
            gt_numbers = self._extract_numbers(ground_truth)
            ans_numbers = self._extract_numbers(answer)

            if gt_numbers and ans_numbers:
                # 如果标准答案中有数字，检查回答中的数字是否合理
                number_conflicts = 0
                for ans_num in ans_numbers:
                    if not any(abs(ans_num - gt_num) / max(gt_num, 1) < 0.1 for gt_num in gt_numbers):
                        number_conflicts += 1

                if number_conflicts > 0:
                    accuracy -= number_conflicts * 0.2

            # 检查关键词矛盾
            contradiction_penalty = self._check_contradictions(ground_truth, answer)
            accuracy -= contradiction_penalty

            # 如果有源文档，检查是否基于文档回答
            if source_chunks:
                source_consistency = self._check_source_consistency(answer, source_chunks)
                accuracy = accuracy * 0.8 + source_consistency * 0.2

            return max(accuracy, 0.0)

        except Exception as e:
            logger.warning(f"准确性计算失败: {str(e)}")
            return 0.5

    def _extract_numbers(self, text: str) -> List[float]:
        """提取文本中的数字"""
        import re
        try:
            numbers = []
            # 提取整数和小数
            pattern = r'\d+\.?\d*'
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    numbers.append(float(match))
                except ValueError:
                    continue
            return numbers
        except Exception:
            return []

    def _check_contradictions(self, ground_truth: str, answer: str) -> float:
        """检查矛盾信息"""
        try:
            # 简单的矛盾检测模式
            contradiction_patterns = [
                (['不是', '不能', '不会', '没有'], ['是', '能', '会', '有']),
                (['支持'], ['不支持']),
                (['开源'], ['闭源', '商业']),
                (['免费'], ['收费', '付费']),
            ]

            penalty = 0.0
            gt_lower = ground_truth.lower()
            ans_lower = answer.lower()

            for negative_words, positive_words in contradiction_patterns:
                gt_has_negative = any(word in gt_lower for word in negative_words)
                gt_has_positive = any(word in gt_lower for word in positive_words)
                ans_has_negative = any(word in ans_lower for word in negative_words)
                ans_has_positive = any(word in ans_lower for word in positive_words)

                # 检查是否有明显矛盾
                if (gt_has_negative and ans_has_positive) or (gt_has_positive and ans_has_negative):
                    penalty += 0.3

            return min(penalty, 0.8)

        except Exception as e:
            logger.warning(f"矛盾检测失败: {str(e)}")
            return 0.0

    def _check_source_consistency(self, answer: str, source_chunks: List[SearchHit]) -> float:
        """检查与源文档的一致性"""
        try:
            if not source_chunks:
                return 0.5

            ans_tokens = self._tokenize_and_clean(answer)
            if not ans_tokens:
                return 0.0

            # 计算答案与源文档的重叠度
            source_text = " ".join([chunk.content for chunk in source_chunks])
            source_tokens = self._tokenize_and_clean(source_text)

            if not source_tokens:
                return 0.0

            # 计算重叠比例
            ans_set = set(ans_tokens)
            source_set = set(source_tokens)

            overlap = len(ans_set & source_set)
            consistency = overlap / len(ans_set) if ans_set else 0.0

            return min(consistency, 1.0)

        except Exception as e:
            logger.warning(f"源文档一致性检查失败: {str(e)}")
            return 0.5

    def _tokenize_and_clean(self, text: str) -> List[str]:
        """分词和清理"""
        try:
            # 分词
            tokens = list(jieba.cut(text.lower()))

            # 过滤停用词和短词
            cleaned_tokens = [
                token for token in tokens
                if (token not in self.stop_words and
                    len(token) > 1 and
                    not token.isspace() and
                    token.isalnum())
            ]

            return cleaned_tokens

        except Exception as e:
            logger.warning(f"分词失败: {str(e)}")
            return []

    def _determine_winner_qa(
        self,
        rag_similarity: float,
        baseline_similarity: float,
        rag_completeness: float,
        baseline_completeness: float,
        rag_accuracy: float,
        baseline_accuracy: float
    ) -> str:
        """基于多个指标确定获胜者"""
        # 综合评分：相似度40%，完整性30%，准确性30%
        rag_score = (rag_similarity * 0.4 +
                    rag_completeness * 0.3 +
                    rag_accuracy * 0.3)

        baseline_score = (baseline_similarity * 0.4 +
                         baseline_completeness * 0.3 +
                         baseline_accuracy * 0.3)

        # 5%的阈值避免微小差异
        threshold = 0.05

        if rag_score > baseline_score + threshold:
            return "rag"
        elif baseline_score > rag_score + threshold:
            return "baseline"
        else:
            return "tie"

    def get_qa_summary(self, result: QAComparisonResult) -> Dict[str, Any]:
        """获取QA评估摘要"""
        return {
            "question": result.question,
            "winner": result.winner,
            "rag_similarity": round(result.rag_similarity, 3),
            "baseline_similarity": round(result.baseline_similarity, 3),
            "rag_completeness": round(result.rag_completeness, 3),
            "baseline_completeness": round(result.baseline_completeness, 3),
            "rag_accuracy": round(result.rag_accuracy, 3),
            "baseline_accuracy": round(result.baseline_accuracy, 3),
            "rag_overall": round((result.rag_similarity * 0.4 +
                               result.rag_completeness * 0.3 +
                               result.rag_accuracy * 0.3), 3),
            "baseline_overall": round((result.baseline_similarity * 0.4 +
                                     result.baseline_completeness * 0.3 +
                                     result.baseline_accuracy * 0.3), 3)
        }