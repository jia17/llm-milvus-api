import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from src.graph.workflow import RAGWorkflow
from src.graph.state import TaskType, IntentType


class TestLangGraphWorkflow:
    """LangGraph工作流测试"""
    
    @pytest.fixture
    def workflow(self):
        """工作流实例"""
        return RAGWorkflow()
    
    def test_intent_recognition_rag(self, workflow):
        """测试意图识别 - RAG查询"""
        result = workflow.process_query("什么是机器学习？")
        
        assert result["intent_type"] in ["knowledge_query", "uncertain"]
        assert result["confidence"] > 0
        assert "answer" in result
    
    def test_intent_recognition_chat(self, workflow):
        """测试意图识别 - 闲聊"""
        result = workflow.process_query("你好")
        
        assert result["intent_type"] in ["casual_chat", "uncertain"]  
        assert "answer" in result
    
    def test_document_upload_workflow(self, workflow):
        """测试文档上传工作流"""
        # 创建临时测试文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("这是一个测试文档。\n包含一些测试内容。")
            temp_file = f.name
        
        try:
            result = workflow.upload_document(temp_file)
            
            assert "answer" in result
            assert not result.get("error")
            
        finally:
            os.unlink(temp_file)
    
    @patch('src.vector_store.milvus_store.MilvusVectorStore.initialize')
    def test_workflow_initialization_failure(self, mock_init, workflow):
        """测试工作流初始化失败"""
        mock_init.return_value = False
        
        assert not workflow.initialize_services()
    
    def test_workflow_stats(self, workflow):
        """测试工作流统计信息"""
        stats = workflow.get_stats()
        
        assert "workflow_ready" in stats
        assert "collection_name" in stats
        assert "embedding_model" in stats


@pytest.mark.integration
class TestLangGraphIntegration:
    """LangGraph集成测试"""
    
    def test_end_to_end_rag_flow(self):
        """端到端RAG流程测试"""
        workflow = RAGWorkflow()
        
        # 测试查询（假设有预存文档）
        result = workflow.query_documents("测试查询")
        
        assert "answer" in result
        assert "total_time" in result
        assert result["total_time"] >= 0
    
    def test_workflow_state_persistence(self):
        """测试工作流状态持久化"""
        workflow = RAGWorkflow()
        
        # 第一次查询
        result1 = workflow.process_query("第一个问题", thread_id="test_thread")
        
        # 获取状态
        state = workflow.get_workflow_state("test_thread")
        assert state is not None
        
        # 第二次查询（同一线程）
        result2 = workflow.process_query("第二个问题", thread_id="test_thread")
        
        assert result1 != result2