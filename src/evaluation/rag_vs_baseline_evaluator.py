"""RAG vs 裸LLM对比评估器

此模块实现RAG增强系统与裸LLM基线的对比评估，
用于证明检索增强的效果。
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import time
import json
from loguru import logger

from src.generation.generator import RAGGenerator, GenerationResult, ChatMessage
from src.retrieval.retriever import HybridRetriever
from src.evaluation.generation_evaluator import GenerationEvaluator, GenerationQuality
from src.evaluation.retrieval_evaluator import RetrievalEvaluator, RetrievalQuality


@dataclass
class EvaluationQuestion:
    """评估问题数据结构"""
    question: str              # 问题内容
    category: str             # 问题类别（事实性、推理性、知识密集型等）
    expected_knowledge: str   # 期望的知识要点
    difficulty: str          # 难度等级（简单、中等、困难）
    ground_truth_answer: Optional[str] = None  # 标准答案（可选）
    ground_truth: Optional[str] = None  # 兼容旧格式


@dataclass
class ComparisonResult:
    """单个问题的对比结果"""
    question: EvaluationQuestion
    rag_answer: str
    baseline_answer: str
    rag_quality: GenerationQuality
    baseline_quality: GenerationQuality
    retrieval_quality: Optional[RetrievalQuality]
    rag_response_time: float
    baseline_response_time: float
    winner: str  # "rag", "baseline", "tie"
    improvement_score: float  # RAG相对基线的改进分数


@dataclass
class OverallEvaluation:
    """整体评估结果"""
    total_questions: int
    rag_wins: int
    baseline_wins: int
    ties: int
    avg_rag_score: float
    avg_baseline_score: float
    avg_improvement: float
    category_performance: Dict[str, Dict[str, float]]
    performance_summary: Dict[str, Any]


class RAGVsBaselineEvaluator:
    """RAG vs 裸LLM对比评估器"""

    def __init__(
        self,
        rag_generator: RAGGenerator,
        retriever: HybridRetriever,
        baseline_generator: Optional[RAGGenerator] = None
    ):
        """初始化评估器

        Args:
            rag_generator: RAG生成器
            retriever: 检索器
            baseline_generator: 基线生成器（不使用检索），如果为None则自动创建
        """
        self.rag_generator = rag_generator
        self.retriever = retriever

        # 创建基线生成器（不使用检索的纯LLM）
        if baseline_generator is None:
            self.baseline_generator = RAGGenerator(
                llm_client=rag_generator.llm_client,
                max_context_length=rag_generator.max_context_length,
                min_similarity_score=rag_generator.min_similarity_score
            )
        else:
            self.baseline_generator = baseline_generator

        # 初始化评估器
        self.generation_evaluator = GenerationEvaluator(rag_generator.llm_client)
        self.retrieval_evaluator = RetrievalEvaluator()

        logger.info("RAG vs 基线评估器初始化完成")

    def create_default_test_questions(self) -> List[EvaluationQuestion]:
        """创建默认测试问题集"""
        questions = [
            # 事实性问题
            EvaluationQuestion(
                question="什么是机器学习？",
                category="事实性",
                expected_knowledge="机器学习定义、基本概念",
                difficulty="简单"
            ),
            EvaluationQuestion(
                question="深度学习和机器学习有什么区别？",
                category="事实性",
                expected_knowledge="深度学习与机器学习的关系和区别",
                difficulty="中等"
            ),

            # 知识密集型问题
            EvaluationQuestion(
                question="如何实现一个简单的神经网络？",
                category="知识密集型",
                expected_knowledge="神经网络实现步骤、代码示例",
                difficulty="困难"
            ),
            EvaluationQuestion(
                question="Python中如何处理大数据？",
                category="知识密集型",
                expected_knowledge="Python大数据处理方法和工具",
                difficulty="中等"
            ),

            # 推理性问题
            EvaluationQuestion(
                question="为什么卷积神经网络适合图像处理？",
                category="推理性",
                expected_knowledge="CNN的特性和图像处理的匹配性",
                difficulty="中等"
            ),
            EvaluationQuestion(
                question="在什么情况下应该选择RNN而不是Transformer？",
                category="推理性",
                expected_knowledge="RNN和Transformer的优劣对比",
                difficulty="困难"
            ),

            # 应用性问题
            EvaluationQuestion(
                question="如何优化深度学习模型的训练速度？",
                category="应用性",
                expected_knowledge="模型训练优化技巧",
                difficulty="中等"
            ),
            EvaluationQuestion(
                question="NLP项目中如何选择合适的预训练模型？",
                category="应用性",
                expected_knowledge="预训练模型选择策略",
                difficulty="困难"
            )
        ]

        return questions

    def evaluate_single_question(
        self,
        question: EvaluationQuestion,
        enable_detailed_logging: bool = True
    ) -> ComparisonResult:
        """评估单个问题"""
        try:
            if enable_detailed_logging:
                logger.info(f"评估问题: {question.question}")

            # 1. RAG回答
            rag_start_time = time.time()

            # 检索相关文档
            retrieval_result = self.retriever.search(
                query=question.question,
                top_k=5
            )

            # 生成RAG答案
            rag_result = self.rag_generator.generate_answer(
                question=question.question,
                retrieval_result=retrieval_result
            )

            rag_response_time = time.time() - rag_start_time

            # 2. 基线回答（不使用检索）
            baseline_start_time = time.time()

            # 创建空的检索结果
            from src.retrieval.retriever import RetrievalResult
            empty_retrieval = RetrievalResult(
                query=question.question,
                hits=[],
                dense_hits=[],
                sparse_hits=[],
                total_hits=0,
                retrieval_time=0.0,
                method="none"
            )

            baseline_result = self.baseline_generator.generate_answer(
                question=question.question,
                retrieval_result=empty_retrieval
            )

            baseline_response_time = time.time() - baseline_start_time

            # 3. 评估RAG质量
            rag_quality = self.generation_evaluator.evaluate_generation(
                query=question.question,
                answer=rag_result.answer,
                source_chunks=rag_result.sources,
                use_llm_evaluation=False  # 为了速度，不使用LLM评估
            )

            # 4. 评估基线质量
            baseline_quality = self.generation_evaluator.evaluate_generation(
                query=question.question,
                answer=baseline_result.answer,
                source_chunks=[],  # 基线没有源文档
                use_llm_evaluation=False
            )

            # 5. 评估检索质量
            retrieval_quality = self.retrieval_evaluator.evaluate_retrieval(
                query=question.question,
                retrieval_result=retrieval_result
            )

            # 6. 确定获胜者
            winner = self._determine_winner(rag_quality, baseline_quality)

            # 7. 计算改进分数
            improvement_score = self._calculate_improvement(rag_quality, baseline_quality)

            result = ComparisonResult(
                question=question,
                rag_answer=rag_result.answer,
                baseline_answer=baseline_result.answer,
                rag_quality=rag_quality,
                baseline_quality=baseline_quality,
                retrieval_quality=retrieval_quality,
                rag_response_time=rag_response_time,
                baseline_response_time=baseline_response_time,
                winner=winner,
                improvement_score=improvement_score
            )

            if enable_detailed_logging:
                logger.info(f"问题评估完成: 获胜者={winner}, 改进分数={improvement_score:.3f}")

            return result

        except Exception as e:
            logger.error(f"单问题评估失败: {str(e)}")
            raise

    def evaluate_question_set(
        self,
        questions: List[EvaluationQuestion],
        save_results: bool = True,
        results_file: Optional[str] = None
    ) -> Tuple[List[ComparisonResult], OverallEvaluation]:
        """评估问题集"""
        logger.info(f"开始评估 {len(questions)} 个问题")

        results = []

        for i, question in enumerate(questions, 1):
            logger.info(f"评估进度: {i}/{len(questions)}")

            try:
                result = self.evaluate_single_question(question)
                results.append(result)

            except Exception as e:
                logger.error(f"问题 {i} 评估失败: {str(e)}")
                continue

        # 计算整体评估
        overall_evaluation = self._calculate_overall_evaluation(results)

        # 保存结果
        if save_results:
            self._save_evaluation_results(results, overall_evaluation, results_file)

        logger.info("评估完成")
        return results, overall_evaluation

    def _determine_winner(
        self,
        rag_quality: GenerationQuality,
        baseline_quality: GenerationQuality
    ) -> str:
        """确定获胜者"""
        rag_score = rag_quality.overall_score
        baseline_score = baseline_quality.overall_score

        # 使用5%的阈值避免微小差异导致的波动
        threshold = 0.05

        if rag_score > baseline_score + threshold:
            return "rag"
        elif baseline_score > rag_score + threshold:
            return "baseline"
        else:
            return "tie"

    def _calculate_improvement(
        self,
        rag_quality: GenerationQuality,
        baseline_quality: GenerationQuality
    ) -> float:
        """计算改进分数（正数表示RAG更好，负数表示基线更好）"""
        if baseline_quality.overall_score == 0:
            return 1.0 if rag_quality.overall_score > 0 else 0.0

        improvement = (
            rag_quality.overall_score - baseline_quality.overall_score
        ) / baseline_quality.overall_score

        return improvement

    def _calculate_overall_evaluation(
        self,
        results: List[ComparisonResult]
    ) -> OverallEvaluation:
        """计算整体评估结果"""
        if not results:
            return OverallEvaluation(
                total_questions=0,
                rag_wins=0,
                baseline_wins=0,
                ties=0,
                avg_rag_score=0.0,
                avg_baseline_score=0.0,
                avg_improvement=0.0,
                category_performance={},
                performance_summary={}
            )

        # 统计获胜情况
        rag_wins = sum(1 for r in results if r.winner == "rag")
        baseline_wins = sum(1 for r in results if r.winner == "baseline")
        ties = sum(1 for r in results if r.winner == "tie")

        # 计算平均分数
        avg_rag_score = sum(r.rag_quality.overall_score for r in results) / len(results)
        avg_baseline_score = sum(r.baseline_quality.overall_score for r in results) / len(results)
        avg_improvement = sum(r.improvement_score for r in results) / len(results)

        # 按类别统计性能
        category_performance = self._calculate_category_performance(results)

        # 生成性能摘要
        performance_summary = {
            "rag_win_rate": rag_wins / len(results),
            "avg_improvement_percentage": avg_improvement * 100,
            "best_category": self._find_best_category(category_performance),
            "worst_category": self._find_worst_category(category_performance),
            "overall_conclusion": self._generate_conclusion(rag_wins, len(results), avg_improvement)
        }

        return OverallEvaluation(
            total_questions=len(results),
            rag_wins=rag_wins,
            baseline_wins=baseline_wins,
            ties=ties,
            avg_rag_score=avg_rag_score,
            avg_baseline_score=avg_baseline_score,
            avg_improvement=avg_improvement,
            category_performance=category_performance,
            performance_summary=performance_summary
        )

    def _calculate_category_performance(
        self,
        results: List[ComparisonResult]
    ) -> Dict[str, Dict[str, float]]:
        """计算各类别的性能"""
        category_stats = {}

        for result in results:
            category = result.question.category

            if category not in category_stats:
                category_stats[category] = {
                    "results": [],
                    "rag_wins": 0,
                    "total": 0
                }

            category_stats[category]["results"].append(result)
            category_stats[category]["total"] += 1

            if result.winner == "rag":
                category_stats[category]["rag_wins"] += 1

        # 计算每个类别的统计数据
        category_performance = {}
        for category, stats in category_stats.items():
            results_list = stats["results"]

            category_performance[category] = {
                "win_rate": stats["rag_wins"] / stats["total"],
                "avg_rag_score": sum(r.rag_quality.overall_score for r in results_list) / len(results_list),
                "avg_baseline_score": sum(r.baseline_quality.overall_score for r in results_list) / len(results_list),
                "avg_improvement": sum(r.improvement_score for r in results_list) / len(results_list),
                "total_questions": stats["total"]
            }

        return category_performance

    def _find_best_category(self, category_performance: Dict[str, Dict[str, float]]) -> str:
        """找到RAG表现最好的类别"""
        if not category_performance:
            return "无"

        best_category = max(
            category_performance.keys(),
            key=lambda cat: category_performance[cat]["win_rate"]
        )
        return best_category

    def _find_worst_category(self, category_performance: Dict[str, Dict[str, float]]) -> str:
        """找到RAG表现最差的类别"""
        if not category_performance:
            return "无"

        worst_category = min(
            category_performance.keys(),
            key=lambda cat: category_performance[cat]["win_rate"]
        )
        return worst_category

    def _generate_conclusion(self, rag_wins: int, total: int, avg_improvement: float) -> str:
        """生成评估结论"""
        win_rate = rag_wins / total if total > 0 else 0
        improvement_pct = avg_improvement * 100

        if win_rate >= 0.7 and improvement_pct > 20:
            return "RAG系统显著优于基线模型"
        elif win_rate >= 0.6 and improvement_pct > 10:
            return "RAG系统明显优于基线模型"
        elif win_rate >= 0.5 and improvement_pct > 5:
            return "RAG系统略优于基线模型"
        elif win_rate >= 0.4:
            return "RAG系统与基线模型性能相当"
        else:
            return "RAG系统表现不如基线模型，需要优化"

    def _save_evaluation_results(
        self,
        results: List[ComparisonResult],
        overall_evaluation: OverallEvaluation,
        results_file: Optional[str] = None
    ):
        """保存评估结果"""
        if results_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            results_file = f"data/evaluation_results_{timestamp}.json"

        try:
            # 准备保存数据
            save_data = {
                "overall_evaluation": asdict(overall_evaluation),
                "detailed_results": []
            }

            for result in results:
                result_dict = {
                    "question": asdict(result.question),
                    "rag_answer": result.rag_answer,
                    "baseline_answer": result.baseline_answer,
                    "rag_quality": asdict(result.rag_quality),
                    "baseline_quality": asdict(result.baseline_quality),
                    "retrieval_quality": asdict(result.retrieval_quality) if result.retrieval_quality else None,
                    "rag_response_time": result.rag_response_time,
                    "baseline_response_time": result.baseline_response_time,
                    "winner": result.winner,
                    "improvement_score": result.improvement_score
                }
                save_data["detailed_results"].append(result_dict)

            # 保存文件
            import os
            os.makedirs(os.path.dirname(results_file), exist_ok=True)

            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            logger.info(f"评估结果已保存到: {results_file}")

        except Exception as e:
            logger.error(f"保存评估结果失败: {str(e)}")

    def print_evaluation_summary(self, overall_evaluation: OverallEvaluation):
        """打印评估摘要"""
        print("\n" + "="*60)
        print("RAG vs 基线模型 评估结果摘要")
        print("="*60)

        print(f"总问题数: {overall_evaluation.total_questions}")
        print(f"RAG获胜: {overall_evaluation.rag_wins} 次")
        print(f"基线获胜: {overall_evaluation.baseline_wins} 次")
        print(f"平局: {overall_evaluation.ties} 次")

        print(f"\n平均质量分数:")
        print(f"  RAG平均分: {overall_evaluation.avg_rag_score:.3f}")
        print(f"  基线平均分: {overall_evaluation.avg_baseline_score:.3f}")
        print(f"  平均改进: {overall_evaluation.avg_improvement:.1%}")

        print(f"\n性能摘要:")
        print(f"  RAG胜率: {overall_evaluation.performance_summary['rag_win_rate']:.1%}")
        print(f"  平均改进百分比: {overall_evaluation.performance_summary['avg_improvement_percentage']:.1f}%")
        print(f"  最佳表现类别: {overall_evaluation.performance_summary['best_category']}")
        print(f"  最差表现类别: {overall_evaluation.performance_summary['worst_category']}")

        print(f"\n结论: {overall_evaluation.performance_summary['overall_conclusion']}")

        print("\n分类别性能:")
        for category, performance in overall_evaluation.category_performance.items():
            print(f"  {category}:")
            print(f"    胜率: {performance['win_rate']:.1%}")
            print(f"    改进: {performance['avg_improvement']:.1%}")
            print(f"    问题数: {performance['total_questions']}")

        print("="*60)


def create_quick_evaluation(
    rag_generator: RAGGenerator,
    retriever: HybridRetriever,
    num_questions: int = 5
) -> Tuple[List[ComparisonResult], OverallEvaluation]:
    """快速评估函数"""
    evaluator = RAGVsBaselineEvaluator(rag_generator, retriever)
    questions = evaluator.create_default_test_questions()[:num_questions]

    results, overall_eval = evaluator.evaluate_question_set(questions)
    evaluator.print_evaluation_summary(overall_eval)

    return results, overall_eval