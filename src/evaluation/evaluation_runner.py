"""RAG评估运行器

整合所有评估组件，提供简单的评估接口和报告生成功能。
"""

from typing import List, Dict, Any, Optional, Tuple
import time
import json
import os
from datetime import datetime
from loguru import logger

from src.generation.generator import RAGGenerator
from src.retrieval.retriever import HybridRetriever
from src.evaluation.rag_vs_baseline_evaluator import (
    RAGVsBaselineEvaluator, ComparisonResult, OverallEvaluation, EvaluationQuestion
)
from src.evaluation.kubesphere_test_questions import (
    KubeSphereQuestionBank, KubeSphereTestQuestion, get_quick_evaluation_questions
)


class EvaluationRunner:
    """RAG评估运行器"""

    def __init__(
        self,
        rag_generator: RAGGenerator,
        retriever: HybridRetriever,
        output_dir: str = "data/evaluation_results"
    ):
        """初始化评估运行器

        Args:
            rag_generator: RAG生成器
            retriever: 检索器
            output_dir: 结果输出目录
        """
        self.rag_generator = rag_generator
        self.retriever = retriever
        self.output_dir = output_dir

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 初始化评估器
        self.evaluator = RAGVsBaselineEvaluator(rag_generator, retriever)

        logger.info(f"评估运行器初始化完成，结果将保存至: {output_dir}")

    def run_kubesphere_evaluation(
        self,
        question_set: str = "quick",
        save_results: bool = True
    ) -> Tuple[List[ComparisonResult], OverallEvaluation, str]:
        """运行KubeSphere专门评估

        Args:
            question_set: 问题集类型 ("quick", "full", "category:xxx", "difficulty:xxx")
            save_results: 是否保存结果

        Returns:
            (详细结果, 整体评估, 报告文件路径)
        """
        logger.info(f"开始KubeSphere评估，问题集: {question_set}")

        # 获取测试问题
        kubesphere_questions = self._get_kubesphere_questions(question_set)
        logger.info(f"获取到 {len(kubesphere_questions)} 个测试问题")

        # 转换为评估问题格式
        evaluation_questions = [
            EvaluationQuestion(
                question=kq.question,
                category=kq.category,
                expected_knowledge=kq.expected_knowledge,
                difficulty=kq.difficulty,
                ground_truth_answer=kq.ground_truth_answer
            )
            for kq in kubesphere_questions
        ]

        # 运行评估
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = None
        if save_results:
            results_file = os.path.join(
                self.output_dir, f"kubesphere_evaluation_{timestamp}.json"
            )

        detailed_results, overall_evaluation = self.evaluator.evaluate_question_set(
            evaluation_questions, save_results=save_results, results_file=results_file
        )

        # 生成专门的KubeSphere报告
        report_file = self._generate_kubesphere_report(
            detailed_results, overall_evaluation, timestamp
        )

        logger.info(f"KubeSphere评估完成，报告已生成: {report_file}")
        return detailed_results, overall_evaluation, report_file

    def run_custom_evaluation(
        self,
        questions: List[str],
        categories: Optional[List[str]] = None,
        difficulties: Optional[List[str]] = None,
        save_results: bool = True
    ) -> Tuple[List[ComparisonResult], OverallEvaluation, str]:
        """运行自定义问题评估

        Args:
            questions: 问题列表
            categories: 对应的类别列表（可选）
            difficulties: 对应的难度列表（可选）
            save_results: 是否保存结果

        Returns:
            (详细结果, 整体评估, 报告文件路径)
        """
        logger.info(f"开始自定义评估，共 {len(questions)} 个问题")

        # 构造评估问题
        evaluation_questions = []
        for i, question in enumerate(questions):
            category = categories[i] if categories and i < len(categories) else "自定义"
            difficulty = difficulties[i] if difficulties and i < len(difficulties) else "中等"

            evaluation_questions.append(
                EvaluationQuestion(
                    question=question,
                    category=category,
                    expected_knowledge="用户自定义问题",
                    difficulty=difficulty,
                    ground_truth_answer=None
                )
            )

        # 运行评估
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = None
        if save_results:
            results_file = os.path.join(
                self.output_dir, f"custom_evaluation_{timestamp}.json"
            )

        detailed_results, overall_evaluation = self.evaluator.evaluate_question_set(
            evaluation_questions, save_results=save_results, results_file=results_file
        )

        # 生成报告
        report_file = self._generate_custom_report(
            detailed_results, overall_evaluation, timestamp
        )

        logger.info(f"自定义评估完成，报告已生成: {report_file}")
        return detailed_results, overall_evaluation, report_file

    def _get_kubesphere_questions(self, question_set: str) -> List[KubeSphereTestQuestion]:
        """获取KubeSphere测试问题"""
        if question_set == "quick":
            return get_quick_evaluation_questions()
        elif question_set == "full":
            return KubeSphereQuestionBank.get_all_questions()
        elif question_set.startswith("category:"):
            category = question_set.split(":", 1)[1]
            return KubeSphereQuestionBank.get_questions_by_category(category)
        elif question_set.startswith("difficulty:"):
            difficulty = question_set.split(":", 1)[1]
            return KubeSphereQuestionBank.get_questions_by_difficulty(difficulty)
        else:
            logger.warning(f"未知问题集类型: {question_set}，使用快速测试集")
            return get_quick_evaluation_questions()

    def _generate_kubesphere_report(
        self,
        detailed_results: List[ComparisonResult],
        overall_evaluation: OverallEvaluation,
        timestamp: str
    ) -> str:
        """生成KubeSphere专门评估报告"""
        report_file = os.path.join(
            self.output_dir, f"kubesphere_report_{timestamp}.md"
        )

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# KubeSphere RAG系统评估报告\n\n")
                f.write(f"**评估时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # 执行摘要
                f.write("## 📊 执行摘要\n\n")
                f.write(f"- **总问题数**: {overall_evaluation.total_questions}\n")
                f.write(f"- **RAG获胜**: {overall_evaluation.rag_wins} 次 ({overall_evaluation.rag_wins/overall_evaluation.total_questions:.1%})\n")
                f.write(f"- **基线获胜**: {overall_evaluation.baseline_wins} 次 ({overall_evaluation.baseline_wins/overall_evaluation.total_questions:.1%})\n")
                f.write(f"- **平局**: {overall_evaluation.ties} 次 ({overall_evaluation.ties/overall_evaluation.total_questions:.1%})\n")
                f.write(f"- **平均改进**: {overall_evaluation.avg_improvement:.1%}\n")
                f.write(f"- **结论**: {overall_evaluation.performance_summary['overall_conclusion']}\n\n")

                # 质量分析
                f.write("## 📈 质量分析\n\n")
                f.write("### 整体质量分数\n\n")
                f.write(f"| 指标 | RAG系统 | 基线模型 | 改进幅度 |\n")
                f.write(f"|------|---------|----------|----------|\n")
                f.write(f"| 平均分数 | {overall_evaluation.avg_rag_score:.3f} | {overall_evaluation.avg_baseline_score:.3f} | {overall_evaluation.avg_improvement:.1%} |\n\n")

                # 分类别性能
                f.write("### 分类别性能表现\n\n")
                f.write("| 类别 | RAG胜率 | 平均RAG分数 | 平均基线分数 | 改进幅度 | 问题数 |\n")
                f.write("|------|---------|-------------|-------------|----------|--------|\n")
                for category, perf in overall_evaluation.category_performance.items():
                    f.write(f"| {category} | {perf['win_rate']:.1%} | {perf['avg_rag_score']:.3f} | {perf['avg_baseline_score']:.3f} | {perf['avg_improvement']:.1%} | {perf['total_questions']} |\n")
                f.write("\n")

                # 关键洞察
                f.write("## 🔍 关键洞察\n\n")
                best_category = overall_evaluation.performance_summary['best_category']
                worst_category = overall_evaluation.performance_summary['worst_category']
                f.write(f"- **最佳表现类别**: {best_category}\n")
                f.write(f"- **需要改进类别**: {worst_category}\n")
                f.write(f"- **RAG胜率**: {overall_evaluation.performance_summary['rag_win_rate']:.1%}\n")
                f.write(f"- **平均改进百分比**: {overall_evaluation.performance_summary['avg_improvement_percentage']:.1f}%\n\n")

                # 详细结果
                f.write("## 📝 详细结果\n\n")
                for i, result in enumerate(detailed_results, 1):
                    f.write(f"### 问题 {i}: {result.question.question}\n\n")
                    f.write(f"**类别**: {result.question.category} | **难度**: {result.question.difficulty}\n\n")
                    f.write(f"**获胜者**: {result.winner} | **改进分数**: {result.improvement_score:.3f}\n\n")

                    f.write("#### RAG回答\n")
                    f.write(f"**质量分数**: {result.rag_quality.overall_score:.3f}\n")
                    f.write(f"**回答**: {result.rag_answer}\n\n")

                    f.write("#### 基线回答\n")
                    f.write(f"**质量分数**: {result.baseline_quality.overall_score:.3f}\n")
                    f.write(f"**回答**: {result.baseline_answer}\n\n")

                    f.write("---\n\n")

                # 技术附录
                f.write("## 🔧 技术附录\n\n")
                f.write("### 评估指标说明\n\n")
                f.write("- **忠实度**: 答案是否基于提供的文档内容\n")
                f.write("- **一致性**: 答案内在逻辑是否一致\n")
                f.write("- **完整性**: 是否充分回答了问题\n")
                f.write("- **整体分数**: 忠实度×0.4 + 一致性×0.3 + 完整性×0.3\n\n")

                f.write("### 评估环境\n\n")
                f.write(f"- **RAG模型**: {self.rag_generator.llm_client.model if hasattr(self.rag_generator.llm_client, 'model') else 'Unknown'}\n")
                f.write(f"- **检索方法**: 混合检索（密集向量 + 稀疏关键词）\n")
                f.write(f"- **知识库**: KubeSphere相关文档\n")
                f.write(f"- **评估时间**: {timestamp}\n\n")

            logger.info(f"KubeSphere评估报告已生成: {report_file}")
            return report_file

        except Exception as e:
            logger.error(f"生成KubeSphere报告失败: {str(e)}")
            return ""

    def _generate_custom_report(
        self,
        detailed_results: List[ComparisonResult],
        overall_evaluation: OverallEvaluation,
        timestamp: str
    ) -> str:
        """生成自定义评估报告"""
        report_file = os.path.join(
            self.output_dir, f"custom_report_{timestamp}.md"
        )

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# RAG系统自定义评估报告\n\n")
                f.write(f"**评估时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # 基本信息与摘要部分（类似KubeSphere报告）
                self._write_basic_summary(f, overall_evaluation)

                # 简化的详细结果
                f.write("## 📝 评估结果详情\n\n")
                for i, result in enumerate(detailed_results, 1):
                    f.write(f"### 问题 {i}\n\n")
                    f.write(f"**问题**: {result.question.question}\n\n")
                    f.write(f"**获胜者**: {result.winner} | **改进分数**: {result.improvement_score:.3f}\n\n")
                    f.write("---\n\n")

            logger.info(f"自定义评估报告已生成: {report_file}")
            return report_file

        except Exception as e:
            logger.error(f"生成自定义报告失败: {str(e)}")
            return ""

    def _write_basic_summary(self, f, overall_evaluation: OverallEvaluation):
        """写入基本摘要信息"""
        f.write("## 📊 评估摘要\n\n")
        f.write(f"- **总问题数**: {overall_evaluation.total_questions}\n")
        f.write(f"- **RAG获胜**: {overall_evaluation.rag_wins} 次\n")
        f.write(f"- **基线获胜**: {overall_evaluation.baseline_wins} 次\n")
        f.write(f"- **平局**: {overall_evaluation.ties} 次\n")
        f.write(f"- **RAG胜率**: {overall_evaluation.rag_wins/overall_evaluation.total_questions:.1%}\n")
        f.write(f"- **平均改进**: {overall_evaluation.avg_improvement:.1%}\n")
        f.write(f"- **结论**: {overall_evaluation.performance_summary['overall_conclusion']}\n\n")

    def quick_test(self, num_questions: int = 5) -> Dict[str, Any]:
        """快速测试功能"""
        logger.info(f"开始快速测试，使用 {num_questions} 个问题")

        try:
            # 获取快速测试问题
            kubesphere_questions = get_quick_evaluation_questions()[:num_questions]

            # 转换格式
            evaluation_questions = [
                EvaluationQuestion(
                    question=kq.question,
                    category=kq.category,
                    expected_knowledge=kq.expected_knowledge,
                    difficulty=kq.difficulty
                )
                for kq in kubesphere_questions
            ]

            # 运行评估（不保存结果）
            detailed_results, overall_evaluation = self.evaluator.evaluate_question_set(
                evaluation_questions, save_results=False
            )

            # 返回简化结果
            return {
                "total_questions": len(detailed_results),
                "rag_wins": overall_evaluation.rag_wins,
                "baseline_wins": overall_evaluation.baseline_wins,
                "ties": overall_evaluation.ties,
                "rag_win_rate": overall_evaluation.rag_wins / len(detailed_results),
                "avg_improvement": overall_evaluation.avg_improvement,
                "conclusion": overall_evaluation.performance_summary['overall_conclusion'],
                "questions_tested": [r.question.question for r in detailed_results]
            }

        except Exception as e:
            logger.error(f"快速测试失败: {str(e)}")
            return {"error": str(e)}

    def print_quick_summary(self, overall_evaluation: OverallEvaluation):
        """打印快速摘要"""
        print(f"\n{'='*50}")
        print("RAG vs 基线模型评估结果")
        print(f"{'='*50}")
        print(f"总问题数: {overall_evaluation.total_questions}")
        print(f"RAG获胜: {overall_evaluation.rag_wins} 次 ({overall_evaluation.rag_wins/overall_evaluation.total_questions:.1%})")
        print(f"平均改进: {overall_evaluation.avg_improvement:.1%}")
        print(f"结论: {overall_evaluation.performance_summary['overall_conclusion']}")
        print(f"{'='*50}\n")


# 便捷函数
def run_quick_kubesphere_evaluation(
    rag_generator: RAGGenerator,
    retriever: HybridRetriever,
    num_questions: int = 5
) -> Dict[str, Any]:
    """运行快速KubeSphere评估

    Args:
        rag_generator: RAG生成器
        retriever: 检索器
        num_questions: 测试问题数量

    Returns:
        评估结果摘要
    """
    runner = EvaluationRunner(rag_generator, retriever)
    return runner.quick_test(num_questions)


def run_full_kubesphere_evaluation(
    rag_generator: RAGGenerator,
    retriever: HybridRetriever,
    question_set: str = "quick"
) -> Tuple[List[ComparisonResult], OverallEvaluation, str]:
    """运行完整KubeSphere评估

    Args:
        rag_generator: RAG生成器
        retriever: 检索器
        question_set: 问题集类型

    Returns:
        (详细结果, 整体评估, 报告文件路径)
    """
    runner = EvaluationRunner(rag_generator, retriever)
    return runner.run_kubesphere_evaluation(question_set)


if __name__ == "__main__":
    # 演示用法
    print("RAG评估运行器演示")
    print("请在实际项目中导入并使用相应组件")