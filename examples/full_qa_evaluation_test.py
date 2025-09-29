#!/usr/bin/env python3
"""完整的QA对评估测试

运行所有26个KubeSphere QA对的完整评估
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.evaluation_runner import EvaluationRunner
from src.generation.generator import RAGGenerator
from src.retrieval.retriever import HybridRetriever
from src.vector_store.milvus_store import MilvusVectorStore
from src.embedding.embedder import EmbeddingManager
from loguru import logger
import time


def setup_components():
    """设置RAG系统组件"""
    try:
        logger.info("🔧 初始化RAG系统组件...")

        # 1. 初始化向量存储
        logger.info("📊 连接Milvus数据库...")
        vector_store = MilvusVectorStore()
        if not vector_store.connect():
            raise Exception("无法连接到Milvus")

        # 获取并加载已存在的集合
        logger.info("📚 加载KubeSphere知识库...")
        from pymilvus import Collection
        vector_store.collection = Collection(vector_store.collection_name)
        vector_store.load_collection()

        # 2. 初始化embedding管理器
        logger.info("🔤 初始化Embedding管理器...")
        embedding_manager = EmbeddingManager()

        # 3. 初始化检索器
        logger.info("🔍 初始化混合检索器...")
        retriever = HybridRetriever(
            vector_store=vector_store,
            embedding_manager=embedding_manager
        )

        # 4. 初始化RAG生成器
        logger.info("🤖 初始化RAG生成器...")
        rag_generator = RAGGenerator()

        logger.info("✅ 所有组件初始化完成")
        return rag_generator, retriever

    except Exception as e:
        logger.error(f"❌ 组件初始化失败: {str(e)}")
        raise


def main():
    """主测试函数"""
    print("🚀 KubeSphere QA对完整评估测试")
    print("=" * 80)

    try:
        # 设置组件
        rag_generator, retriever = setup_components()

        # 初始化评估运行器
        runner = EvaluationRunner(rag_generator, retriever)

        print(f"\n📝 开始完整QA对评估 (26个KubeSphere问题)")
        print("-" * 80)

        start_time = time.time()

        # 运行完整的KubeSphere评估
        detailed_results, overall_eval, report_file = runner.run_kubesphere_evaluation(
            question_set="full",
            save_results=True
        )

        end_time = time.time()
        duration = end_time - start_time

        print(f"\n📊 完整评估结果:")
        print(f"  ⏱️  总耗时: {duration:.1f}秒")
        print(f"  📈 测试问题数: {overall_eval.total_questions}")
        print(f"  🏆 RAG获胜: {overall_eval.rag_wins} 次")
        print(f"  🔧 基线获胜: {overall_eval.baseline_wins} 次")
        print(f"  🤝 平局: {overall_eval.ties} 次")
        print(f"  📊 RAG胜率: {overall_eval.rag_wins/overall_eval.total_questions:.1%}")

        if overall_eval.total_questions > 0:
            avg_improvement = overall_eval.total_improvement / overall_eval.total_questions
            print(f"  📈 平均改进: {avg_improvement:.1%}")

        # 分类别统计
        print(f"\n📋 分类别表现:")
        category_stats = {}
        for result in detailed_results:
            cat = result.question_data.get('category', '未分类')
            if cat not in category_stats:
                category_stats[cat] = {'total': 0, 'rag_wins': 0}
            category_stats[cat]['total'] += 1
            if result.winner == 'rag':
                category_stats[cat]['rag_wins'] += 1

        for category, stats in category_stats.items():
            win_rate = stats['rag_wins'] / stats['total'] if stats['total'] > 0 else 0
            print(f"  {category}: {stats['rag_wins']}/{stats['total']} ({win_rate:.1%})")

        # 难度分析
        print(f"\n🎯 难度分析:")
        difficulty_stats = {}
        for result in detailed_results:
            diff = result.question_data.get('difficulty', '未知')
            if diff not in difficulty_stats:
                difficulty_stats[diff] = {'total': 0, 'rag_wins': 0}
            difficulty_stats[diff]['total'] += 1
            if result.winner == 'rag':
                difficulty_stats[diff]['rag_wins'] += 1

        for difficulty, stats in difficulty_stats.items():
            win_rate = stats['rag_wins'] / stats['total'] if stats['total'] > 0 else 0
            print(f"  {difficulty}: {stats['rag_wins']}/{stats['total']} ({win_rate:.1%})")

        # 根据结果给出建议
        rag_win_rate = overall_eval.rag_wins / overall_eval.total_questions
        print(f"\n💡 评估结论:")
        if rag_win_rate >= 0.8:
            print("  ✅ RAG系统表现优秀，显著优于基线模型")
            print("  📈 可以放心投入生产环境")
        elif rag_win_rate >= 0.6:
            print("  ⚡ RAG系统表现良好，但仍有优化空间")
            print("  🔧 建议检查较弱类别的检索质量")
        else:
            print("  ⚠️  RAG系统需要优化")
            print("  🔍 建议检查检索策略和生成参数")

        if report_file:
            print(f"\n📄 详细报告已保存: {report_file}")

    except Exception as e:
        logger.error(f"❌ 评估失败: {str(e)}")
        print(f"❌ 评估失败: {str(e)}")
        sys.exit(1)

    print("\n🎉 完整评估完成！")


if __name__ == "__main__":
    # 设置日志级别
    logger.remove()
    logger.add(sys.stderr, level="INFO")  # 显示重要信息

    main()