from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re
import jieba
from loguru import logger

from src.vector_store.milvus_store import SearchHit
from src.generation.generator import ChatMessage, KimiLLMClient


@dataclass
class GenerationQuality:
    """生成质量评估结果"""
    faithfulness_score: float    # 0-1, 忠实度（是否基于文档）
    consistency_score: float     # 0-1, 一致性（答案内在逻辑）
    completeness_score: float    # 0-1, 完整性（是否充分回答）
    overall_score: float         # 0-1, 总体质量分数
    is_reliable: bool           # 答案是否可靠
    quality_issues: List[str]   # 质量问题
    confidence: float           # 评估置信度


class GenerationEvaluator:
    """生成质量评估器 - 评估生成答案的质量和可靠性"""

    def __init__(self, llm_client: Optional[KimiLLMClient] = None):
        self.llm_client = llm_client

        # 质量检查模式
        self.reliability_patterns = {
            'uncertain_phrases': [
                '可能', '也许', '大概', '似乎', '应该', '估计', '不确定',
                '不清楚', '不知道', '没有明确', '无法确定'
            ],
            'confident_phrases': [
                '根据文档', '文档显示', '明确指出', '具体说明',
                '详细介绍', '文档中提到', '资料表明'
            ],
            'hallucination_indicators': [
                '众所周知', '一般来说', '通常情况下', '根据常识',
                '我认为', '个人觉得', '据我了解'
            ]
        }

        logger.info("生成质量评估器初始化完成")

    def evaluate_generation(
        self,
        query: str,
        answer: str,
        source_chunks: List[SearchHit],
        use_llm_evaluation: bool = True
    ) -> GenerationQuality:
        """评估生成质量"""
        try:
            # 1. 忠实度评估 - 答案是否基于提供的文档
            faithfulness_score = self._evaluate_faithfulness(answer, source_chunks)

            # 2. 一致性评估 - 答案内在逻辑是否一致
            consistency_score = self._evaluate_consistency(answer)

            # 3. 完整性评估 - 是否充分回答了问题
            completeness_score = self._evaluate_completeness(query, answer)

            # 4. 综合评分
            overall_score = (
                faithfulness_score * 0.4 +
                consistency_score * 0.3 +
                completeness_score * 0.3
            )

            # 5. 可靠性判断
            is_reliable = self._determine_reliability(
                faithfulness_score, consistency_score, completeness_score, answer
            )

            # 6. 识别质量问题
            quality_issues = self._identify_generation_issues(
                answer, source_chunks, faithfulness_score, consistency_score
            )

            # 7. LLM辅助评估（可选）
            if use_llm_evaluation and self.llm_client and source_chunks:
                llm_assessment = self._llm_assisted_evaluation(query, answer, source_chunks)
                # 融合LLM评估结果
                overall_score = overall_score * 0.7 + llm_assessment.get('score', 0.5) * 0.3

            # 8. 计算置信度
            confidence = self._calculate_evaluation_confidence(
                faithfulness_score, consistency_score, len(source_chunks)
            )

            return GenerationQuality(
                faithfulness_score=faithfulness_score,
                consistency_score=consistency_score,
                completeness_score=completeness_score,
                overall_score=overall_score,
                is_reliable=is_reliable,
                quality_issues=quality_issues,
                confidence=confidence
            )

        except Exception as e:
            logger.error(f"生成质量评估失败: {str(e)}")
            return GenerationQuality(
                faithfulness_score=0.0,
                consistency_score=0.0,
                completeness_score=0.0,
                overall_score=0.0,
                is_reliable=False,
                quality_issues=[f"评估过程出错: {str(e)}"],
                confidence=0.0
            )

    def _evaluate_faithfulness(self, answer: str, source_chunks: List[SearchHit]) -> float:
        """评估忠实度 - 答案是否基于提供的文档"""
        try:
            if not source_chunks:
                # 没有源文档时，检查是否承认了这一点
                if any(phrase in answer for phrase in ['没有找到', '无相关信息', '文档中没有']):
                    return 0.8  # 诚实承认缺乏信息
                else:
                    return 0.1  # 可能产生了幻觉

            # 分词处理
            answer_tokens = set(jieba.cut(answer.lower()))

            # 计算与源文档的内容重叠度
            total_overlap = 0
            total_source_tokens = 0

            for chunk in source_chunks:
                chunk_tokens = set(jieba.cut(chunk.content.lower()))
                overlap = len(answer_tokens & chunk_tokens)
                total_overlap += overlap
                total_source_tokens += len(chunk_tokens)

            # 基础重叠度
            if total_source_tokens > 0:
                overlap_ratio = total_overlap / total_source_tokens
            else:
                overlap_ratio = 0.0

            # 检查引用指示词
            citation_score = 0.0
            for phrase in self.reliability_patterns['confident_phrases']:
                if phrase in answer:
                    citation_score += 0.1

            # 检查幻觉指示词（负面评分）
            hallucination_penalty = 0.0
            for phrase in self.reliability_patterns['hallucination_indicators']:
                if phrase in answer:
                    hallucination_penalty += 0.15

            # 综合评分
            faithfulness = min(
                overlap_ratio * 3 + citation_score - hallucination_penalty,
                1.0
            )

            return max(faithfulness, 0.0)

        except Exception as e:
            logger.warning(f"忠实度评估失败: {str(e)}")
            return 0.5

    def _evaluate_consistency(self, answer: str) -> float:
        """评估一致性 - 答案内在逻辑是否一致"""
        try:
            # 检查矛盾表述
            contradiction_patterns = [
                (r'不是.*是', r'是.*不是'),
                (r'没有.*有', r'有.*没有'),
                (r'不能.*能', r'能.*不能'),
                (r'不会.*会', r'会.*不会')
            ]

            contradiction_count = 0
            for pattern1, pattern2 in contradiction_patterns:
                if re.search(pattern1, answer) and re.search(pattern2, answer):
                    contradiction_count += 1

            # 检查不确定性表述密度
            uncertain_count = sum(
                answer.count(phrase)
                for phrase in self.reliability_patterns['uncertain_phrases']
            )
            uncertain_density = uncertain_count / len(answer.split())

            # 检查逻辑连接词使用
            logical_connectors = ['因此', '所以', '但是', '然而', '另外', '此外', '首先', '其次']
            connector_count = sum(answer.count(connector) for connector in logical_connectors)
            connector_score = min(connector_count / 3, 1.0)  # 适度使用逻辑连接词

            # 综合评分
            consistency = (
                max(0, 1 - contradiction_count * 0.3) * 0.5 +
                max(0, 1 - uncertain_density * 10) * 0.3 +
                connector_score * 0.2
            )

            return min(consistency, 1.0)

        except Exception as e:
            logger.warning(f"一致性评估失败: {str(e)}")
            return 0.5

    def _evaluate_completeness(self, query: str, answer: str) -> float:
        """评估完整性 - 是否充分回答了问题"""
        try:
            # 提取查询中的关键信息需求
            query_lower = query.lower()

            # 问题类型检测
            question_types = {
                '什么': ['定义', '介绍', '解释'],
                '如何': ['方法', '步骤', '流程'],
                '为什么': ['原因', '解释', '分析'],
                '哪里': ['位置', '地点'],
                '什么时候': ['时间', '日期'],
                '多少': ['数量', '价格', '比例']
            }

            # 检查答案是否回应了问题类型
            type_match_score = 0.0
            for q_word, expected_elements in question_types.items():
                if q_word in query_lower:
                    for element in expected_elements:
                        if element in answer or any(syn in answer for syn in self._get_synonyms(element)):
                            type_match_score += 0.3
                            break

            # 答案长度合理性
            answer_length = len(answer.strip())
            length_score = min(answer_length / 100, 1.0)  # 期望至少100字符的答案

            # 检查是否承认信息不足
            if any(phrase in answer for phrase in ['没有找到', '信息不足', '无法回答']):
                return 0.6  # 诚实承认限制

            # 综合评分
            completeness = type_match_score * 0.6 + length_score * 0.4

            return min(completeness, 1.0)

        except Exception as e:
            logger.warning(f"完整性评估失败: {str(e)}")
            return 0.5

    def _determine_reliability(
        self,
        faithfulness: float,
        consistency: float,
        completeness: float,
        answer: str
    ) -> bool:
        """判断答案是否可靠"""
        # 基本门槛检查
        if faithfulness < 0.4 or consistency < 0.4:
            return False

        # 检查明显的质量问题
        if any(phrase in answer for phrase in self.reliability_patterns['hallucination_indicators']):
            return False

        # 综合判断
        average_score = (faithfulness + consistency + completeness) / 3
        return average_score >= 0.6

    def _identify_generation_issues(
        self,
        answer: str,
        source_chunks: List[SearchHit],
        faithfulness: float,
        consistency: float
    ) -> List[str]:
        """识别生成质量问题"""
        issues = []

        try:
            # 忠实度问题
            if faithfulness < 0.5:
                issues.append("答案与提供的文档内容相关性较低")

            # 一致性问题
            if consistency < 0.5:
                issues.append("答案内在逻辑存在矛盾")

            # 幻觉检测
            hallucination_count = sum(
                1 for phrase in self.reliability_patterns['hallucination_indicators']
                if phrase in answer
            )
            if hallucination_count > 0:
                issues.append(f"可能存在幻觉内容（{hallucination_count}处）")

            # 过度不确定性
            uncertain_count = sum(
                answer.count(phrase)
                for phrase in self.reliability_patterns['uncertain_phrases']
            )
            if uncertain_count > 3:
                issues.append("答案中不确定表述过多")

            # 空泛回答
            if len(answer.strip()) < 50:
                issues.append("答案过于简短")

            return issues

        except Exception as e:
            logger.warning(f"问题识别失败: {str(e)}")
            return ["质量问题识别过程出错"]

    def _llm_assisted_evaluation(
        self,
        query: str,
        answer: str,
        source_chunks: List[SearchHit]
    ) -> Dict[str, Any]:
        """LLM辅助质量评估"""
        try:
            # 构建评估提示
            context = "\n".join([chunk.content for chunk in source_chunks[:3]])

            eval_prompt = f"""请评估以下回答的质量：

问题: {query}

提供的文档内容:
{context}

生成的回答:
{answer}

请从以下维度评估（用0-1分数）：
1. 忠实度：回答是否基于提供的文档
2. 相关性：回答是否直接回应了问题
3. 完整性：回答是否充分

只返回JSON格式： {{"faithfulness": 0.8, "relevance": 0.9, "completeness": 0.7, "overall": 0.8}}"""

            messages = [
                ChatMessage(role="system", content="你是一个专业的文本质量评估助手。"),
                ChatMessage(role="user", content=eval_prompt)
            ]

            response = self.llm_client.generate(messages)

            # 简单解析（实际使用中应该更严格）
            import json
            try:
                scores = json.loads(response)
                return scores
            except json.JSONDecodeError:
                return {"score": 0.5}

        except Exception as e:
            logger.warning(f"LLM辅助评估失败: {str(e)}")
            return {"score": 0.5}

    def _calculate_evaluation_confidence(
        self,
        faithfulness: float,
        consistency: float,
        source_count: int
    ) -> float:
        """计算评估置信度"""
        try:
            # 基于评估分数的稳定性
            score_stability = 1 - abs(faithfulness - consistency)

            # 基于源文档数量
            source_factor = min(source_count / 3.0, 1.0)

            # 综合置信度
            confidence = score_stability * 0.6 + source_factor * 0.4

            return min(confidence, 1.0)

        except Exception as e:
            logger.warning(f"置信度计算失败: {str(e)}")
            return 0.5

    def _get_synonyms(self, word: str) -> List[str]:
        """获取同义词（简化版）"""
        synonym_map = {
            '定义': ['含义', '意思', '概念'],
            '方法': ['途径', '方式', '手段'],
            '原因': ['理由', '缘由', '根源'],
            '步骤': ['流程', '过程', '阶段']
        }
        return synonym_map.get(word, [])

    def get_quality_summary(self, quality: GenerationQuality) -> Dict[str, Any]:
        """获取质量评估摘要"""
        return {
            "overall_score": round(quality.overall_score, 3),
            "faithfulness": round(quality.faithfulness_score, 3),
            "consistency": round(quality.consistency_score, 3),
            "completeness": round(quality.completeness_score, 3),
            "is_reliable": quality.is_reliable,
            "quality_level": self._get_quality_level(quality.overall_score),
            "issues_count": len(quality.quality_issues),
            "confidence": round(quality.confidence, 3)
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