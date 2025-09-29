#!/usr/bin/env python3
"""简单的RAG评估测试

直接运行快速评估，无需交互式输入
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.evaluation_runner import run_quick_kubesphere_evaluation
from src.generation.generator import RAGGenerator
from src.retrieval.retriever import HybridRetriever
from src.vector_store.milvus_store import MilvusVectorStore
from src.embedding.embedder import EmbeddingManager
from loguru import logger


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
    print("🚀 KubeSphere RAG评估系统测试")
    print("=" * 60)

    try:
        # 设置组件
        rag_generator, retriever = setup_components()

        print("\n📝 开始快速评估 (使用3个KubeSphere问题)...")
        print("-" * 60)

        # 运行快速评估（使用QA对）
        result = run_quick_kubesphere_evaluation(
            rag_generator=rag_generator,
            retriever=retriever,
            num_questions=3
        )

        # 显示结果
        print("\n📊 评估结果:")
        print(f"  📈 测试问题数: {result['total_questions']}")
        print(f"  🏆 RAG获胜: {result['rag_wins']} 次")
        print(f"  🔧 基线获胜: {result['baseline_wins']} 次")
        print(f"  🤝 平局: {result['ties']} 次")
        print(f"  📊 RAG胜率: {result['rag_win_rate']:.1%}")
        print(f"  📈 平均改进: {result['avg_improvement']:.1%}")
        print(f"  🎯 结论: {result['conclusion']}")

        print(f"\n📋 测试问题:")
        for i, question in enumerate(result['questions_tested'], 1):
            print(f"  {i}. {question}")

        # 根据结果给出建议
        print(f"\n💡 分析建议:")
        if result['rag_win_rate'] >= 0.7:
            print("  ✅ RAG系统表现优秀，显著优于基线模型")
        elif result['rag_win_rate'] >= 0.5:
            print("  ⚠️  RAG系统表现良好，但仍有优化空间")
        else:
            print("  ❌ RAG系统需要优化，检查检索质量和生成策略")

        if result['avg_improvement'] > 0.2:
            print("  📈 平均改进超过20%，效果显著")
        elif result['avg_improvement'] > 0.1:
            print("  📊 平均改进超过10%，效果明显")
        else:
            print("  🔧 改进幅度较小，建议调优参数")

    except Exception as e:
        logger.error(f"❌ 评估失败: {str(e)}")
        print(f"❌ 评估失败: {str(e)}")
        sys.exit(1)

    print("\n🎉 评估完成！")


if __name__ == "__main__":
    # 设置日志级别，减少噪音
    logger.remove()
    logger.add(sys.stderr, level="WARNING")  # 只显示警告和错误

    main()