import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from typing import List

from src.evaluation.retrieval_evaluator import RetrievalEvaluator, RetrievalQuality
from src.evaluation.generation_evaluator import GenerationEvaluator, GenerationQuality
from src.evaluation.self_rag import SelfRAGController, SelfRAGAction, SelfRAGResult
from src.retrieval.retriever import RetrievalResult, HybridRetriever
from src.generation.generator import RAGGenerator, GenerationResult, ChatMessage
from src.vector_store.milvus_store import SearchHit


class TestRetrievalEvaluator:
    """检索质量评估器测试"""

    def setup_method(self):
        """测试前置设置"""
        self.evaluator = RetrievalEvaluator(min_relevance_threshold=0.5)

    @pytest.mark.unit
    def test_evaluate_empty_retrieval(self):
        """测试空检索结果评估"""
        # 创建空检索结果
        retrieval_result = RetrievalResult(
            query="测试问题",
            hits=[],
            dense_hits=[],
            sparse_hits=[],
            total_hits=0,
            retrieval_time=0.1
        )

        quality = self.evaluator.evaluate_retrieval("测试问题", retrieval_result)

        assert quality.relevance_score == 0.0
        assert not quality.is_sufficient
        assert "没有检索到任何文档" in quality.quality_issues
        assert quality.recommendation == "需要扩展查询或检查文档库"

    @pytest.mark.unit
    def test_evaluate_good_retrieval(self):
        """测试高质量检索结果评估"""
        # 模拟高质量检索结果
        hits = [
            SearchHit(
                id="1",
                score=0.8,
                content="这是一个关于机器学习算法的详细介绍，包含了深度学习的基本概念和应用。",
                metadata={"filename": "ml_guide.md"},
                doc_id="doc1",
                chunk_index=0
            ),
            SearchHit(
                id="2",
                score=0.7,
                content="深度学习是机器学习的一个分支，使用神经网络进行模式识别。",
                metadata={"filename": "dl_intro.md"},
                doc_id="doc2",
                chunk_index=0
            )
        ]

        retrieval_result = RetrievalResult(
            query="什么是深度学习",
            hits=hits,
            dense_hits=hits,
            sparse_hits=[],
            total_hits=2,
            retrieval_time=0.1
        )

        quality = self.evaluator.evaluate_retrieval("什么是深度学习", retrieval_result)

        assert quality.relevance_score > 0.5
        assert quality.is_sufficient
        assert quality.confidence > 0.0

    @pytest.mark.unit
    def test_semantic_relevance_calculation(self):
        """测试语义相关性计算"""
        query = "什么是机器学习"
        content = "机器学习是人工智能的一个分支，它使计算机能够从数据中学习。"

        relevance = self.evaluator._calculate_semantic_relevance(query, content)

        assert 0.0 <= relevance <= 1.0
        assert relevance > 0.3  # 应该有一定相关性

    @pytest.mark.unit
    def test_quality_issues_identification(self):
        """测试质量问题识别"""
        # 创建低质量检索结果
        low_quality_hits = [
            SearchHit(
                id="1",
                score=0.1,
                content="不相关的内容",
                metadata={},
                doc_id="doc1",
                chunk_index=0
            )
        ]

        relevance_scores = [0.1, 0.1, 0.1]
        issues = self.evaluator._identify_quality_issues(
            "什么是机器学习", low_quality_hits, relevance_scores
        )

        assert "大部分检索结果相关性较低" in issues


class TestGenerationEvaluator:
    """生成质量评估器测试"""

    def setup_method(self):
        """测试前置设置"""
        self.evaluator = GenerationEvaluator()

    @pytest.mark.unit
    def test_evaluate_faithful_answer(self):
        """测试忠实答案评估"""
        query = "什么是深度学习？"
        answer = "根据文档，深度学习是机器学习的一个分支，使用多层神经网络进行模式识别。"

        source_chunks = [
            SearchHit(
                id="1",
                score=0.8,
                content="深度学习是机器学习的一个分支，使用多层神经网络进行模式识别。",
                metadata={"filename": "ml_guide.md"},
                doc_id="doc1",
                chunk_index=0
            )
        ]

        quality = self.evaluator.evaluate_generation(
            query, answer, source_chunks, use_llm_evaluation=False
        )

        assert quality.faithfulness_score > 0.5
        assert quality.is_reliable
        assert quality.overall_score > 0.5

    @pytest.mark.unit
    def test_evaluate_hallucinated_answer(self):
        """测试包含幻觉的答案评估"""
        query = "什么是深度学习？"
        answer = "我认为深度学习是一种新技术，众所周知它可以解决所有问题。"

        source_chunks = [
            SearchHit(
                id="1",
                score=0.8,
                content="深度学习是机器学习的一个分支。",
                metadata={"filename": "ml_guide.md"},
                doc_id="doc1",
                chunk_index=0
            )
        ]

        quality = self.evaluator.evaluate_generation(
            query, answer, source_chunks, use_llm_evaluation=False
        )

        assert quality.faithfulness_score < 0.5
        assert not quality.is_reliable
        assert "可能存在幻觉内容" in quality.quality_issues

    @pytest.mark.unit
    def test_evaluate_inconsistent_answer(self):
        """测试不一致答案评估"""
        query = "深度学习是什么？"
        answer = "深度学习是机器学习，但是深度学习不是机器学习。这很复杂。"

        source_chunks = []

        quality = self.evaluator.evaluate_generation(
            query, answer, source_chunks, use_llm_evaluation=False
        )

        assert quality.consistency_score < 0.5

    @pytest.mark.unit
    def test_evaluate_incomplete_answer(self):
        """测试不完整答案评估"""
        query = "详细解释什么是深度学习？"
        answer = "是的。"

        source_chunks = []

        quality = self.evaluator.evaluate_generation(
            query, answer, source_chunks, use_llm_evaluation=False
        )

        assert quality.completeness_score < 0.5
        assert "答案过于简短" in quality.quality_issues


class TestSelfRAGController:
    """Self-RAG控制器测试"""

    def setup_method(self):
        """测试前置设置"""
        # 模拟检索器
        self.mock_retriever = Mock(spec=HybridRetriever)

        # 模拟生成器
        self.mock_generator = Mock(spec=RAGGenerator)

        # 创建控制器
        self.controller = SelfRAGController(
            retriever=self.mock_retriever,
            generator=self.mock_generator,
            max_iterations=2,
            min_retrieval_quality=0.5,
            min_generation_quality=0.6
        )

    @pytest.mark.unit
    def test_retrieval_action_decision(self):
        """测试检索行动决策"""
        # 高质量检索
        high_quality = RetrievalQuality(
            relevance_score=0.8,
            confidence=0.9,
            is_sufficient=True,
            quality_issues=[],
            recommendation="继续"
        )
        action = self.controller._decide_retrieval_action(high_quality)
        assert action == SelfRAGAction.CONTINUE

        # 低质量检索
        low_quality = RetrievalQuality(
            relevance_score=0.1,
            confidence=0.5,
            is_sufficient=False,
            quality_issues=["质量太差"],
            recommendation="拒绝"
        )
        action = self.controller._decide_retrieval_action(low_quality)
        assert action == SelfRAGAction.REJECT

    @pytest.mark.unit
    def test_generation_action_decision(self):
        """测试生成行动决策"""
        # 高质量生成
        high_quality = GenerationQuality(
            faithfulness_score=0.8,
            consistency_score=0.8,
            completeness_score=0.8,
            overall_score=0.8,
            is_reliable=True,
            quality_issues=[],
            confidence=0.9
        )
        action = self.controller._decide_generation_action(high_quality)
        assert action == SelfRAGAction.CONTINUE

        # 低忠实度生成
        low_faithfulness = GenerationQuality(
            faithfulness_score=0.2,
            consistency_score=0.8,
            completeness_score=0.8,
            overall_score=0.6,
            is_reliable=False,
            quality_issues=["忠实度低"],
            confidence=0.5
        )
        action = self.controller._decide_generation_action(low_faithfulness)
        assert action == SelfRAGAction.RETRIEVE

    @pytest.mark.unit
    def test_parameter_adjustment(self):
        """测试参数调整"""
        # 检索参数调整
        quality = RetrievalQuality(
            relevance_score=0.3,
            confidence=0.5,
            is_sufficient=False,
            quality_issues=["缺乏文档多样性"],
            recommendation="改进"
        )

        adjusted_params = self.controller._adjust_retrieval_params({}, quality)
        assert adjusted_params['top_k'] >= 3

        # 生成参数调整
        gen_quality = GenerationQuality(
            faithfulness_score=0.3,
            consistency_score=0.5,
            completeness_score=0.4,
            overall_score=0.4,
            is_reliable=False,
            quality_issues=["忠实度低"],
            confidence=0.5
        )

        adjusted_gen_params = self.controller._adjust_generation_params({}, gen_quality)
        assert adjusted_gen_params['temperature'] == 0.3

    @pytest.mark.integration
    @patch('src.evaluation.self_rag.logger')
    def test_self_rag_workflow(self, mock_logger):
        """测试完整的Self-RAG工作流"""
        # 模拟检索结果
        mock_retrieval_result = RetrievalResult(
            query="测试问题",
            hits=[
                SearchHit(
                    id="1",
                    score=0.8,
                    content="相关内容",
                    metadata={},
                    doc_id="doc1",
                    chunk_index=0
                )
            ],
            dense_hits=[],
            sparse_hits=[],
            total_hits=1,
            retrieval_time=0.1
        )

        self.mock_retriever.search.return_value = mock_retrieval_result

        # 模拟生成结果
        mock_generation_result = GenerationResult(
            question="测试问题",
            answer="这是一个测试回答",
            sources=[mock_retrieval_result.hits[0]],
            retrieval_result=mock_retrieval_result,
            generation_time=0.2,
            total_time=0.3,
            model="test-model"
        )

        self.mock_generator.generate_multi_turn_answer.return_value = mock_generation_result

        # 执行Self-RAG
        result = self.controller.generate_with_self_rag("测试问题")

        # 验证结果
        assert result.query == "测试问题"
        assert result.final_answer == "这是一个测试回答"
        assert result.iteration_count >= 1
        assert result.confidence >= 0.0

    @pytest.mark.unit
    def test_quick_generate_without_self_rag(self):
        """测试快速生成（禁用Self-RAG）"""
        # 模拟检索和生成
        mock_retrieval_result = RetrievalResult(
            query="测试问题",
            hits=[],
            dense_hits=[],
            sparse_hits=[],
            total_hits=0,
            retrieval_time=0.1
        )

        mock_generation_result = GenerationResult(
            question="测试问题",
            answer="普通回答",
            sources=[],
            retrieval_result=mock_retrieval_result,
            generation_time=0.1,
            total_time=0.2,
            model="test-model"
        )

        self.mock_retriever.search.return_value = mock_retrieval_result
        self.mock_generator.generate_answer.return_value = mock_generation_result

        result = self.controller.quick_generate(
            "测试问题",
            enable_self_evaluation=False
        )

        assert result["answer"] == "普通回答"
        assert not result["self_rag_enabled"]

    @pytest.mark.unit
    def test_confidence_calculation(self):
        """测试置信度计算"""
        retrieval_quality = RetrievalQuality(
            relevance_score=0.8,
            confidence=0.9,
            is_sufficient=True,
            quality_issues=[],
            recommendation="好"
        )

        generation_quality = GenerationQuality(
            faithfulness_score=0.7,
            consistency_score=0.8,
            completeness_score=0.8,
            overall_score=0.77,
            is_reliable=True,
            quality_issues=[],
            confidence=0.8
        )

        confidence = self.controller._calculate_overall_confidence(
            retrieval_quality, generation_quality
        )

        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # 应该有较高置信度


class TestSelfRAGIntegration:
    """Self-RAG集成测试"""

    @pytest.mark.integration
    def test_self_rag_factory_method(self):
        """测试Self-RAG工厂方法"""
        from src.generation.generator import RAGGenerator

        # 模拟检索器
        mock_retriever = Mock()

        # 测试工厂方法
        generator, self_rag_controller = RAGGenerator.create_self_rag_generator(
            retriever=mock_retriever
        )

        assert generator is not None
        assert isinstance(generator, RAGGenerator)

        if self_rag_controller is not None:
            assert isinstance(self_rag_controller, SelfRAGController)

    @pytest.mark.integration
    @patch('src.utils.helpers.get_config')
    def test_config_integration(self, mock_get_config):
        """测试配置集成"""
        # 模拟配置
        config_values = {
            "self_rag.enabled": True,
            "self_rag.iteration.max_iterations": 2,
            "self_rag.quality_thresholds.min_retrieval_quality": 0.4,
            "self_rag.quality_thresholds.min_generation_quality": 0.5,
            "self_rag.evaluation.retrieval.min_relevance_threshold": 0.3
        }

        def config_side_effect(key, default=None):
            return config_values.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # 创建带配置的评估器
        retrieval_evaluator = RetrievalEvaluator()
        assert retrieval_evaluator.min_relevance_threshold == 0.5  # 默认值

        generation_evaluator = GenerationEvaluator()
        assert generation_evaluator is not None

    @pytest.mark.slow
    @pytest.mark.integration
    def test_performance_impact(self):
        """测试Self-RAG性能影响"""
        # 模拟组件
        mock_retriever = Mock()
        mock_generator = Mock()

        # 创建控制器
        controller = SelfRAGController(
            retriever=mock_retriever,
            generator=mock_generator,
            max_iterations=1
        )

        # 模拟快速响应
        mock_retrieval_result = RetrievalResult(
            query="性能测试",
            hits=[],
            dense_hits=[],
            sparse_hits=[],
            total_hits=0,
            retrieval_time=0.01
        )

        mock_generation_result = GenerationResult(
            question="性能测试",
            answer="快速回答",
            sources=[],
            retrieval_result=mock_retrieval_result,
            generation_time=0.01,
            total_time=0.02,
            model="test-model"
        )

        mock_retriever.search.return_value = mock_retrieval_result
        mock_generator.generate_multi_turn_answer.return_value = mock_generation_result

        # 测试响应时间
        start_time = time.time()
        result = controller.quick_generate("性能测试", enable_self_evaluation=True)
        end_time = time.time()

        response_time = end_time - start_time

        # Self-RAG应该在合理时间内完成
        assert response_time < 2.0  # 2秒以内
        assert result["answer"] is not None


# 测试配置
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])