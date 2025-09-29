"""RAG评估功能测试

测试RAG vs 基线对比评估功能，验证评估器的正确性。
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from typing import List

from src.generation.generator import RAGGenerator, GenerationResult, ChatMessage
from src.retrieval.retriever import HybridRetriever, RetrievalResult
from src.vector_store.milvus_store import SearchHit
from src.evaluation.rag_vs_baseline_evaluator import (
    RAGVsBaselineEvaluator, ComparisonResult, EvaluationQuestion, OverallEvaluation
)
from src.evaluation.evaluation_runner import EvaluationRunner, run_quick_kubesphere_evaluation
from src.evaluation.kubesphere_test_questions import (
    KubeSphereQuestionBank, get_kubesphere_questions, get_quick_evaluation_questions
)


class TestKubeSphereQuestionBank:
    """KubeSphere问题库测试"""

    def test_get_all_questions(self):
        """测试获取所有问题"""
        questions = KubeSphereQuestionBank.get_all_questions()

        assert len(questions) > 0
        assert all(hasattr(q, 'question') for q in questions)
        assert all(hasattr(q, 'category') for q in questions)
        assert all(hasattr(q, 'difficulty') for q in questions)
        assert all(hasattr(q, 'expected_knowledge') for q in questions)

    def test_get_questions_by_category(self):
        """测试按类别获取问题"""
        observability_questions = KubeSphereQuestionBank.get_questions_by_category("可观测性")

        assert len(observability_questions) > 0
        assert all(q.category == "可观测性" for q in observability_questions)

    def test_get_questions_by_difficulty(self):
        """测试按难度获取问题"""
        easy_questions = KubeSphereQuestionBank.get_questions_by_difficulty("简单")

        assert len(easy_questions) > 0
        assert all(q.difficulty == "简单" for q in easy_questions)

    def test_get_quick_test_set(self):
        """测试快速测试集"""
        quick_questions = KubeSphereQuestionBank.get_quick_test_set()

        assert len(quick_questions) > 0
        # 应该包含不同难度的问题
        difficulties = {q.difficulty for q in quick_questions}
        assert len(difficulties) > 1  # 至少有2种难度

    def test_convenience_functions(self):
        """测试便捷函数"""
        # 测试 get_kubesphere_questions
        questions = get_kubesphere_questions(count=5)
        assert len(questions) <= 5

        # 测试 get_quick_evaluation_questions
        quick_questions = get_quick_evaluation_questions()
        assert len(quick_questions) > 0


class TestRAGVsBaselineEvaluator:
    """RAG vs 基线评估器测试"""

    def setup_method(self):
        """测试前置设置"""
        # Mock RAG生成器
        self.mock_rag_generator = Mock(spec=RAGGenerator)
        self.mock_rag_generator.llm_client = Mock()
        self.mock_rag_generator.llm_client.model = "test_model"
        self.mock_rag_generator.max_context_length = 1000
        self.mock_rag_generator.min_similarity_score = 0.3

        # Mock检索器
        self.mock_retriever = Mock(spec=HybridRetriever)

        # 创建评估器
        self.evaluator = RAGVsBaselineEvaluator(
            self.mock_rag_generator,
            self.mock_retriever
        )

    def test_create_default_test_questions(self):
        """测试创建默认测试问题"""
        questions = self.evaluator.create_default_test_questions()

        assert len(questions) > 0
        assert all(isinstance(q, EvaluationQuestion) for q in questions)
        assert all(q.question and q.category and q.difficulty for q in questions)

    @patch('src.evaluation.rag_vs_baseline_evaluator.time.time')
    def test_evaluate_single_question(self, mock_time):
        """测试单个问题评估"""
        # Mock时间
        mock_time.side_effect = [0, 1, 1, 2]  # 开始时间和结束时间

        # Mock检索结果
        mock_retrieval_result = RetrievalResult(
            query="测试问题",
            hits=[
                SearchHit(
                    id="1", score=0.8, content="相关内容",
                    metadata={}, doc_id="doc1", chunk_index=0
                )
            ],
            dense_hits=[],
            sparse_hits=[],
            total_hits=1,
            retrieval_time=0.1,
            method="hybrid"
        )
        self.mock_retriever.retrieve.return_value = mock_retrieval_result

        # Mock生成结果
        mock_rag_result = GenerationResult(
            question="测试问题",
            answer="RAG回答",
            sources=[mock_retrieval_result.hits[0]],
            retrieval_result=mock_retrieval_result,
            model="test_model",
            generation_time=0.5,
            total_time=0.6
        )

        mock_baseline_result = GenerationResult(
            question="测试问题",
            answer="基线回答",
            sources=[],
            retrieval_result=None,
            model="test_model",
            generation_time=0.4,
            total_time=0.4
        )

        self.mock_rag_generator.generate_answer.side_effect = [
            mock_rag_result, mock_baseline_result
        ]

        # 创建测试问题
        question = EvaluationQuestion(
            question="测试问题",
            category="测试",
            expected_knowledge="测试知识",
            difficulty="中等"
        )

        # 执行评估
        result = self.evaluator.evaluate_single_question(question)

        # 验证结果
        assert isinstance(result, ComparisonResult)
        assert result.question == question
        assert result.rag_answer == "RAG回答"
        assert result.baseline_answer == "基线回答"
        assert result.winner in ["rag", "baseline", "tie"]
        assert isinstance(result.improvement_score, float)

    def test_determine_winner(self):
        """测试获胜者判断"""
        from src.evaluation.generation_evaluator import GenerationQuality

        # RAG明显更好
        rag_quality = GenerationQuality(
            faithfulness_score=0.9, consistency_score=0.8, completeness_score=0.8,
            overall_score=0.85, is_reliable=True, quality_issues=[], confidence=0.9
        )
        baseline_quality = GenerationQuality(
            faithfulness_score=0.6, consistency_score=0.6, completeness_score=0.6,
            overall_score=0.6, is_reliable=True, quality_issues=[], confidence=0.8
        )

        winner = self.evaluator._determine_winner(rag_quality, baseline_quality)
        assert winner == "rag"

        # 接近平局
        rag_quality.overall_score = 0.62
        baseline_quality.overall_score = 0.60
        winner = self.evaluator._determine_winner(rag_quality, baseline_quality)
        assert winner == "tie"

    def test_calculate_improvement(self):
        """测试改进分数计算"""
        from src.evaluation.generation_evaluator import GenerationQuality

        rag_quality = GenerationQuality(
            faithfulness_score=0.8, consistency_score=0.8, completeness_score=0.8,
            overall_score=0.8, is_reliable=True, quality_issues=[], confidence=0.9
        )
        baseline_quality = GenerationQuality(
            faithfulness_score=0.6, consistency_score=0.6, completeness_score=0.6,
            overall_score=0.6, is_reliable=True, quality_issues=[], confidence=0.8
        )

        improvement = self.evaluator._calculate_improvement(rag_quality, baseline_quality)
        expected_improvement = (0.8 - 0.6) / 0.6  # 约33%
        assert abs(improvement - expected_improvement) < 0.01


class TestEvaluationRunner:
    """评估运行器测试"""

    def setup_method(self):
        """测试前置设置"""
        # Mock组件
        self.mock_rag_generator = Mock(spec=RAGGenerator)
        self.mock_rag_generator.llm_client = Mock()
        self.mock_rag_generator.llm_client.model = "test_model"

        self.mock_retriever = Mock(spec=HybridRetriever)

        # 创建运行器
        self.runner = EvaluationRunner(
            self.mock_rag_generator,
            self.mock_retriever,
            output_dir="test_output"
        )

    def test_get_kubesphere_questions(self):
        """测试获取KubeSphere问题"""
        # 测试快速问题集
        questions = self.runner._get_kubesphere_questions("quick")
        assert len(questions) > 0

        # 测试完整问题集
        questions = self.runner._get_kubesphere_questions("full")
        assert len(questions) > 0

        # 测试按类别
        questions = self.runner._get_kubesphere_questions("category:可观测性")
        assert len(questions) > 0
        assert all(q.category == "可观测性" for q in questions)

        # 测试按难度
        questions = self.runner._get_kubesphere_questions("difficulty:简单")
        assert len(questions) > 0
        assert all(q.difficulty == "简单" for q in questions)

    @patch('src.evaluation.evaluation_runner.os.makedirs')
    def test_quick_test(self, mock_makedirs):
        """测试快速测试功能"""
        # Mock evaluator的evaluate_question_set方法
        mock_overall_eval = OverallEvaluation(
            total_questions=3,
            rag_wins=2,
            baseline_wins=1,
            ties=0,
            avg_rag_score=0.8,
            avg_baseline_score=0.6,
            avg_improvement=0.33,
            category_performance={},
            performance_summary={
                'rag_win_rate': 0.67,
                'avg_improvement_percentage': 33.0,
                'overall_conclusion': '测试结论'
            }
        )

        mock_detailed_results = [Mock() for _ in range(3)]
        for i, mock_result in enumerate(mock_detailed_results):
            mock_result.question.question = f"测试问题{i+1}"

        self.runner.evaluator.evaluate_question_set = Mock(
            return_value=(mock_detailed_results, mock_overall_eval)
        )

        # 执行快速测试
        result = self.runner.quick_test(3)

        # 验证结果
        assert result['total_questions'] == 3
        assert result['rag_wins'] == 2
        assert result['baseline_wins'] == 1
        assert result['rag_win_rate'] == 2/3
        assert result['conclusion'] == '测试结论'
        assert len(result['questions_tested']) == 3


class TestEvaluationIntegration:
    """评估功能集成测试"""

    @pytest.mark.integration
    @patch('src.evaluation.evaluation_runner.EvaluationRunner')
    def test_run_quick_kubesphere_evaluation(self, mock_runner_class):
        """测试快速KubeSphere评估集成函数"""
        # Mock运行器
        mock_runner = Mock()
        mock_runner.quick_test.return_value = {
            'total_questions': 5,
            'rag_wins': 3,
            'conclusion': '测试通过'
        }
        mock_runner_class.return_value = mock_runner

        # Mock组件
        mock_rag_generator = Mock()
        mock_retriever = Mock()

        # 执行测试
        result = run_quick_kubesphere_evaluation(
            mock_rag_generator, mock_retriever, 5
        )

        # 验证
        assert result['total_questions'] == 5
        assert result['rag_wins'] == 3
        assert result['conclusion'] == '测试通过'
        mock_runner_class.assert_called_once_with(mock_rag_generator, mock_retriever)
        mock_runner.quick_test.assert_called_once_with(5)

    @pytest.mark.slow
    def test_full_evaluation_workflow(self):
        """测试完整评估工作流（需要真实组件）"""
        # 这个测试需要真实的组件，标记为slow
        pytest.skip("需要真实组件和API密钥")


class TestEvaluationMetrics:
    """评估指标测试"""

    def test_evaluation_question_creation(self):
        """测试评估问题创建"""
        question = EvaluationQuestion(
            question="测试问题",
            category="测试类别",
            expected_knowledge="测试知识",
            difficulty="中等"
        )

        assert question.question == "测试问题"
        assert question.category == "测试类别"
        assert question.expected_knowledge == "测试知识"
        assert question.difficulty == "中等"
        assert question.ground_truth is None

    def test_overall_evaluation_calculation(self):
        """测试整体评估计算"""
        # 这个测试会在实际的evaluator测试中覆盖
        pass


@pytest.mark.performance
class TestEvaluationPerformance:
    """评估性能测试"""

    def test_question_generation_performance(self):
        """测试问题生成性能"""
        start_time = time.time()
        questions = KubeSphereQuestionBank.get_all_questions()
        end_time = time.time()

        assert len(questions) > 0
        assert end_time - start_time < 1.0  # 应该在1秒内完成

    def test_quick_evaluation_performance(self):
        """测试快速评估性能"""
        # Mock组件以测试纯计算性能
        mock_rag_generator = Mock()
        mock_retriever = Mock()

        start_time = time.time()
        runner = EvaluationRunner(mock_rag_generator, mock_retriever)
        questions = runner._get_kubesphere_questions("quick")
        end_time = time.time()

        assert len(questions) > 0
        assert end_time - start_time < 0.5  # 问题获取应该很快


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])