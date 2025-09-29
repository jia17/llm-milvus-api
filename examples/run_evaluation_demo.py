#!/usr/bin/env python3
"""RAG评估演示脚本

演示如何使用RAG评估系统对比RAG增强系统与裸LLM的效果。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.evaluation_runner import EvaluationRunner, run_quick_kubesphere_evaluation
from src.evaluation.kubesphere_test_questions import get_quick_evaluation_questions
from src.generation.generator import RAGGenerator
from src.retrieval.retriever import HybridRetriever
from src.vector_store.milvus_store import MilvusVectorStore
from src.embedding.embedder import EmbeddingManager
from loguru import logger


def setup_components():
    """设置RAG系统组件"""
    try:
        # 1. 初始化向量存储
        logger.info("初始化向量存储...")
        vector_store = MilvusVectorStore()
        if not vector_store.connect():
            raise Exception("无法连接到Milvus")

        # 获取并加载已存在的集合
        logger.info("获取现有集合...")
        from pymilvus import Collection
        vector_store.collection = Collection(vector_store.collection_name)

        logger.info("加载集合到内存...")
        vector_store.load_collection()

        # 2. 初始化embedding管理器
        logger.info("初始化Embedding管理器...")
        embedding_manager = EmbeddingManager()

        # 3. 初始化检索器
        logger.info("初始化混合检索器...")
        retriever = HybridRetriever(
            vector_store=vector_store,
            embedding_manager=embedding_manager
        )

        # 4. 初始化RAG生成器
        logger.info("初始化RAG生成器...")
        rag_generator = RAGGenerator()

        return rag_generator, retriever

    except Exception as e:
        logger.error(f"组件初始化失败: {str(e)}")
        raise


def demo_quick_evaluation():
    """演示快速评估"""
    print("\n" + "="*60)
    print("RAG系统快速评估演示")
    print("="*60)

    try:
        # 设置组件
        rag_generator, retriever = setup_components()

        # 运行快速评估
        logger.info("开始快速评估...")
        result = run_quick_kubesphere_evaluation(
            rag_generator=rag_generator,
            retriever=retriever,
            num_questions=3  # 只用3个问题快速演示
        )

        # 显示结果
        print(f"\n📊 快速评估结果:")
        print(f"  测试问题数: {result['total_questions']}")
        print(f"  RAG获胜: {result['rag_wins']} 次")
        print(f"  基线获胜: {result['baseline_wins']} 次")
        print(f"  平局: {result['ties']} 次")
        print(f"  RAG胜率: {result['rag_win_rate']:.1%}")
        print(f"  平均改进: {result['avg_improvement']:.1%}")
        print(f"  结论: {result['conclusion']}")

        print(f"\n📝 测试问题:")
        for i, question in enumerate(result['questions_tested'], 1):
            print(f"  {i}. {question}")

    except Exception as e:
        logger.error(f"快速评估失败: {str(e)}")
        print(f"❌ 评估失败: {str(e)}")


def demo_full_evaluation():
    """演示完整评估"""
    print("\n" + "="*60)
    print("RAG系统完整评估演示")
    print("="*60)

    try:
        # 设置组件
        rag_generator, retriever = setup_components()

        # 创建评估运行器
        runner = EvaluationRunner(rag_generator, retriever)

        # 运行KubeSphere专门评估
        logger.info("开始完整KubeSphere评估...")
        detailed_results, overall_evaluation, report_file = runner.run_kubesphere_evaluation(
            question_set="quick",  # 使用快速问题集
            save_results=True
        )

        # 打印摘要
        runner.print_quick_summary(overall_evaluation)

        # 显示详细信息
        print(f"📄 详细评估报告已生成: {report_file}")
        print(f"📊 详细结果:")
        for i, result in enumerate(detailed_results[:3], 1):  # 只显示前3个
            print(f"\n  问题 {i}: {result.question.question}")
            print(f"    类别: {result.question.category}")
            print(f"    获胜者: {result.winner}")
            print(f"    改进分数: {result.improvement_score:.3f}")

    except Exception as e:
        logger.error(f"完整评估失败: {str(e)}")
        print(f"❌ 评估失败: {str(e)}")


def demo_custom_evaluation():
    """演示自定义问题评估"""
    print("\n" + "="*60)
    print("自定义问题评估演示")
    print("="*60)

    try:
        # 设置组件
        rag_generator, retriever = setup_components()

        # 创建评估运行器
        runner = EvaluationRunner(rag_generator, retriever)

        # 自定义测试问题
        custom_questions = [
            "KubeSphere是什么？",
            "如何在KubeSphere中配置告警？",
            "KubeSphere的可观测性功能有哪些？"
        ]

        custom_categories = ["基础概念", "配置管理", "可观测性"]
        custom_difficulties = ["简单", "中等", "中等"]

        logger.info("开始自定义问题评估...")
        detailed_results, overall_evaluation, report_file = runner.run_custom_evaluation(
            questions=custom_questions,
            categories=custom_categories,
            difficulties=custom_difficulties,
            save_results=True
        )

        # 打印结果
        print(f"📊 自定义评估结果:")
        print(f"  总问题数: {overall_evaluation.total_questions}")
        print(f"  RAG胜率: {overall_evaluation.rag_wins/overall_evaluation.total_questions:.1%}")
        print(f"  结论: {overall_evaluation.performance_summary['overall_conclusion']}")
        print(f"📄 报告文件: {report_file}")

    except Exception as e:
        logger.error(f"自定义评估失败: {str(e)}")
        print(f"❌ 评估失败: {str(e)}")


def show_kubesphere_questions():
    """显示KubeSphere测试问题示例"""
    print("\n" + "="*60)
    print("KubeSphere测试问题库示例")
    print("="*60)

    # 获取快速测试问题
    questions = get_quick_evaluation_questions()

    print(f"📝 快速测试集 (共{len(questions)}个问题):")
    for i, q in enumerate(questions[:5], 1):  # 显示前5个
        print(f"\n{i}. [{q.category}] {q.question}")
        print(f"   难度: {q.difficulty}")
        print(f"   期望知识: {q.expected_knowledge}")

    if len(questions) > 5:
        print(f"\n... 还有 {len(questions) - 5} 个问题")


def main():
    """主演示函数"""
    print("🚀 RAG评估系统演示")
    print("本演示将展示如何评估RAG系统相对于裸LLM的效果提升")

    while True:
        print("\n" + "="*60)
        print("请选择演示模式:")
        print("1. 显示KubeSphere测试问题")
        print("2. 快速评估演示 (3个问题)")
        print("3. 完整评估演示")
        print("4. 自定义问题评估演示")
        print("0. 退出")
        print("="*60)

        choice = input("请输入选择 (0-4): ").strip()

        if choice == "0":
            print("👋 感谢使用RAG评估系统演示！")
            break
        elif choice == "1":
            show_kubesphere_questions()
        elif choice == "2":
            demo_quick_evaluation()
        elif choice == "3":
            demo_full_evaluation()
        elif choice == "4":
            demo_custom_evaluation()
        else:
            print("❌ 无效选择，请重试")


if __name__ == "__main__":
    # 设置日志级别
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        print(f"❌ 程序出错: {str(e)}")