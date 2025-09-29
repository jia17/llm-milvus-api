import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
import json

from src.conversation.session_manager import SessionManager, ConversationSession, ContextCompressor
from src.conversation.models import ChatMessage


class TestContextCompressor:
    """测试上下文压缩器"""
    
    def setup_method(self):
        self.compressor = ContextCompressor(
            max_uncompressed_messages=5,
            compression_ratio=0.5,
            preserve_recent_messages=2
        )
    
    def test_should_compress(self):
        """测试压缩判断"""
        messages = [ChatMessage(role="user", content=f"message {i}") for i in range(3)]
        assert not self.compressor.should_compress(messages)
        
        messages = [ChatMessage(role="user", content=f"message {i}") for i in range(6)]
        assert self.compressor.should_compress(messages)
    
    def test_compress_history(self):
        """测试历史压缩"""
        messages = [
            ChatMessage(role="user", content="第一条消息"),
            ChatMessage(role="assistant", content="这是一个重要的回答"),
            ChatMessage(role="user", content="普通消息"),
            ChatMessage(role="assistant", content="普通回答"),
            ChatMessage(role="user", content="包含错误关键词的消息"),
            ChatMessage(role="assistant", content="最近的回答1"),
            ChatMessage(role="user", content="最近的消息2"),
        ]
        
        compressed, info = self.compressor.compress_history(messages)
        
        assert info["compressed"] == True
        assert len(compressed) < len(messages)
        assert info["original_count"] == len(messages)
        assert info["compressed_count"] == len(compressed)


class TestSessionManager:
    """测试会话管理器"""
    
    def setup_method(self):
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.session_manager = SessionManager(
            storage_dir=self.temp_dir,
            enable_compression=True,
            enable_checkpoints=True
        )
        # 更新压缩器参数用于测试
        if self.session_manager.compressor:
            self.session_manager.compressor.max_uncompressed_messages = 5
    
    def teardown_method(self):
        # 清理临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_session(self):
        """测试创建会话"""
        session = self.session_manager.create_session(title="测试会话")
        
        assert session.session_id is not None
        assert session.title == "测试会话"
        assert len(session.messages) == 0
        assert session.created_at is not None
        
        # 验证文件已保存
        session_file = Path(self.temp_dir) / f"session_{session.session_id}.json"
        assert session_file.exists()
    
    def test_add_message(self):
        """测试添加消息"""
        session = self.session_manager.create_session(title="测试会话")
        
        # 添加消息
        message = ChatMessage(role="user", content="测试消息")
        success = self.session_manager.add_message(session.session_id, message)
        
        assert success == True
        
        # 验证消息已添加
        messages = self.session_manager.get_messages(session.session_id)
        assert len(messages) == 1
        assert messages[0].content == "测试消息"
    
    def test_get_session(self):
        """测试获取会话"""
        # 创建会话
        original_session = self.session_manager.create_session(title="测试会话")
        
        # 获取会话
        retrieved_session = self.session_manager.get_session(original_session.session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == original_session.session_id
        assert retrieved_session.title == original_session.title
    
    def test_list_sessions(self):
        """测试列出会话"""
        # 创建多个会话
        session1 = self.session_manager.create_session(title="会话1")
        session2 = self.session_manager.create_session(title="会话2")
        
        # 列出会话
        sessions = self.session_manager.list_sessions()
        
        assert len(sessions) == 2
        session_ids = [s["session_id"] for s in sessions]
        assert session1.session_id in session_ids
        assert session2.session_id in session_ids
    
    def test_delete_session(self):
        """测试删除会话"""
        session = self.session_manager.create_session(title="待删除会话")
        
        # 删除会话
        success = self.session_manager.delete_session(session.session_id)
        assert success == True
        
        # 验证会话已删除
        retrieved_session = self.session_manager.get_session(session.session_id)
        assert retrieved_session is None
        
        # 验证文件已删除
        session_file = Path(self.temp_dir) / f"session_{session.session_id}.json"
        assert not session_file.exists()
    
    def test_export_import_session(self):
        """测试会话导出导入"""
        # 创建会话并添加消息
        session = self.session_manager.create_session(title="导出测试会话")
        self.session_manager.add_message(session.session_id, ChatMessage(role="user", content="测试消息1"))
        self.session_manager.add_message(session.session_id, ChatMessage(role="assistant", content="测试回答1"))
        
        # 导出会话
        export_path = self.session_manager.export_session(session.session_id, "json")
        assert export_path is not None
        assert Path(export_path).exists()
        
        # 导入会话
        new_session_id = self.session_manager.import_session(export_path)
        assert new_session_id is not None
        assert new_session_id != session.session_id  # 应该生成新ID
        
        # 验证导入的会话
        imported_session = self.session_manager.get_session(new_session_id)
        assert imported_session is not None
        assert imported_session.title == "[导入] 导出测试会话"
        assert len(imported_session.messages) == 2
    
    def test_compression_trigger(self):
        """测试自动压缩触发"""
        session = self.session_manager.create_session(title="压缩测试")
        
        # 添加超过阈值的消息
        for i in range(7):  # 超过max_uncompressed_messages=5的阈值
            self.session_manager.add_message(
                session.session_id, 
                ChatMessage(role="user", content=f"消息 {i}")
            )
        
        # 获取会话检查是否被压缩
        updated_session = self.session_manager.get_session(session.session_id)
        
        # 由于启用压缩，消息数量应该少于原始数量
        assert len(updated_session.messages) < 7
        assert updated_session.compressed == True
        assert "compression" in updated_session.metadata


@pytest.mark.integration
class TestSessionManagerIntegration:
    """集成测试"""
    
    def test_session_persistence(self):
        """测试会话持久化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建第一个管理器实例
            manager1 = SessionManager(storage_dir=temp_dir)
            session = manager1.create_session(title="持久化测试")
            manager1.add_message(session.session_id, ChatMessage(role="user", content="测试消息"))
            
            # 创建第二个管理器实例（模拟程序重启）
            manager2 = SessionManager(storage_dir=temp_dir)
            
            # 从第二个实例获取会话
            retrieved_session = manager2.get_session(session.session_id)
            
            assert retrieved_session is not None
            assert retrieved_session.title == "持久化测试"
            assert len(retrieved_session.messages) == 1
            assert retrieved_session.messages[0].content == "测试消息"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])