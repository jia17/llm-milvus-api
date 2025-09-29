from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import json
import uuid
import os
from pathlib import Path
import pickle
import gzip
from loguru import logger

from .models import ChatMessage
from src.utils.helpers import get_config


@dataclass
class ConversationSession:
    """对话会话数据结构"""
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage]
    metadata: Dict[str, Any]
    compressed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [{"role": msg.role, "content": msg.content, "metadata": msg.metadata} for msg in self.messages],
            "metadata": self.metadata,
            "compressed": self.compressed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationSession':
        """从字典创建会话对象"""
        return cls(
            session_id=data["session_id"],
            title=data["title"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=[ChatMessage(role=msg["role"], content=msg["content"], metadata=msg.get("metadata", {})) for msg in data["messages"]],
            metadata=data.get("metadata", {}),
            compressed=data.get("compressed", False)
        )


@dataclass
class SessionCheckpoint:
    """会话检查点"""
    checkpoint_id: str
    session_id: str
    created_at: datetime
    message_count: int
    compressed_history: bytes
    metadata: Dict[str, Any]


class ContextCompressor:
    """上下文压缩器 - 智能压缩对话历史"""
    
    def __init__(
        self,
        max_uncompressed_messages: int = None,
        compression_ratio: float = None,
        preserve_recent_messages: int = None
    ):
        self.max_uncompressed_messages = max_uncompressed_messages or get_config("conversation.compression.max_uncompressed_messages", 20)
        self.compression_ratio = compression_ratio or get_config("conversation.compression.compression_ratio", 0.3)
        self.preserve_recent_messages = preserve_recent_messages or get_config("conversation.compression.preserve_recent_messages", 5)
        logger.info(f"上下文压缩器初始化: max_messages={self.max_uncompressed_messages}")
    
    def should_compress(self, messages: List[ChatMessage]) -> bool:
        """判断是否需要压缩"""
        return len(messages) > self.max_uncompressed_messages
    
    def compress_history(self, messages: List[ChatMessage]) -> Tuple[List[ChatMessage], Dict[str, Any]]:
        """压缩对话历史"""
        if not self.should_compress(messages):
            return messages, {"compressed": False, "original_count": len(messages)}
        
        try:
            # 保留最近的消息
            recent_messages = messages[-self.preserve_recent_messages:]
            old_messages = messages[:-self.preserve_recent_messages]
            
            if not old_messages:
                return messages, {"compressed": False, "reason": "no_old_messages"}
            
            # 压缩策略：保留关键信息，去除冗余
            compressed_messages = self._compress_messages(old_messages)
            
            # 合并压缩后的消息和最近消息
            final_messages = compressed_messages + recent_messages
            
            compression_info = {
                "compressed": True,
                "original_count": len(messages),
                "compressed_count": len(final_messages),
                "compression_ratio": len(final_messages) / len(messages),
                "compressed_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"对话历史压缩完成: {len(messages)} -> {len(final_messages)} 条消息")
            return final_messages, compression_info
            
        except Exception as e:
            logger.error(f"对话历史压缩失败: {str(e)}")
            return messages, {"compressed": False, "error": str(e)}
    
    def _compress_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """压缩消息的核心算法"""
        if not messages:
            return []
        
        # 简单的压缩策略：选择性保留重要消息
        compressed = []
        
        # 保留第一条消息（通常是上下文设置）
        if messages:
            compressed.append(messages[0])
        
        # 保留包含重要信息的消息
        important_keywords = {'错误', '问题', '解决', '重要', '注意', '关键', '文档', '配置'}
        
        for msg in messages[1:]:
            if any(keyword in msg.content for keyword in important_keywords):
                compressed.append(msg)
            elif len(msg.content) > 200:  # 保留长消息
                # 截断长消息但保留开头和结尾
                content = msg.content
                if len(content) > 400:
                    content = content[:200] + "...[压缩]..." + content[-200:]
                compressed.append(ChatMessage(role=msg.role, content=content))
        
        # 确保至少保留一定比例的消息
        target_count = max(2, int(len(messages) * self.compression_ratio))
        if len(compressed) < target_count:
            # 补充一些随机消息
            remaining = messages[1:]
            for msg in remaining:
                if msg not in compressed and len(compressed) < target_count:
                    compressed.append(msg)
        
        return compressed


class SessionManager:
    """会话管理器 - 处理对话会话的生命周期"""
    
    def __init__(
        self,
        storage_dir: str = None,
        enable_compression: bool = None,
        enable_checkpoints: bool = None
    ):
        self.storage_dir = Path(storage_dir or get_config("conversation.storage_dir", "./data/sessions"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.checkpoint_dir = self.storage_dir / "checkpoints"
        self.checkpoint_dir.mkdir(exist_ok=True)
        
        self.enable_compression = enable_compression if enable_compression is not None else get_config("conversation.enable_compression", True)
        self.enable_checkpoints = enable_checkpoints if enable_checkpoints is not None else get_config("conversation.enable_checkpoints", True)
        
        self.checkpoint_interval = get_config("conversation.checkpoints.auto_checkpoint_interval", 10)
        
        self.compressor = ContextCompressor() if self.enable_compression else None
        
        # 内存中的活跃会话缓存
        self._active_sessions: Dict[str, ConversationSession] = {}
        
        logger.info(f"会话管理器初始化: storage={self.storage_dir}, compression={self.enable_compression}")
    
    def create_session(
        self,
        title: str = None,
        metadata: Dict[str, Any] = None
    ) -> ConversationSession:
        """创建新的对话会话"""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        session = ConversationSession(
            session_id=session_id,
            title=title or f"对话 {now.strftime('%m-%d %H:%M')}",
            created_at=now,
            updated_at=now,
            messages=[],
            metadata=metadata or {}
        )
        
        # 缓存到内存
        self._active_sessions[session_id] = session
        
        # 立即保存
        self._save_session(session)
        
        logger.info(f"创建新会话: {session_id}, 标题: {session.title}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """获取会话"""
        # 先查内存缓存
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        
        # 从磁盘加载
        session = self._load_session(session_id)
        if session:
            self._active_sessions[session_id] = session
        
        return session
    
    def add_message(
        self,
        session_id: str,
        message: ChatMessage,
        auto_compress: bool = True
    ) -> bool:
        """向会话添加消息"""
        session = self.get_session(session_id)
        if not session:
            logger.error(f"会话不存在: {session_id}")
            return False
        
        # 添加消息
        session.messages.append(message)
        session.updated_at = datetime.now(timezone.utc)
        
        # 自动压缩检查
        if auto_compress and self.compressor and self.compressor.should_compress(session.messages):
            compressed_messages, compression_info = self.compressor.compress_history(session.messages)
            session.messages = compressed_messages
            session.metadata["compression"] = compression_info
            session.compressed = True
        
        # 保存会话
        self._save_session(session)
        
        # 创建检查点
        if self.enable_checkpoints and len(session.messages) % self.checkpoint_interval == 0:
            self._create_checkpoint(session)
        
        return True
    
    def get_messages(
        self,
        session_id: str,
        limit: int = None,
        include_system: bool = True
    ) -> List[ChatMessage]:
        """获取会话消息"""
        session = self.get_session(session_id)
        if not session:
            return []
        
        messages = session.messages
        
        if not include_system:
            messages = [msg for msg in messages if msg.role != "system"]
        
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def list_sessions(
        self,
        limit: int = 50,
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """列出所有会话"""
        try:
            sessions = []
            
            # 扫描存储目录
            for session_file in self.storage_dir.glob("session_*.json"):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                    
                    session_info = {
                        "session_id": session_data["session_id"],
                        "title": session_data["title"],
                        "created_at": session_data["created_at"],
                        "updated_at": session_data["updated_at"],
                        "message_count": len(session_data["messages"]),
                        "compressed": session_data.get("compressed", False)
                    }
                    
                    if include_metadata:
                        session_info["metadata"] = session_data.get("metadata", {})
                    
                    sessions.append(session_info)
                    
                except Exception as e:
                    logger.warning(f"跳过损坏的会话文件: {session_file}, 错误: {str(e)}")
                    continue
            
            # 按更新时间排序
            sessions.sort(key=lambda x: x["updated_at"], reverse=True)
            
            return sessions[:limit]
            
        except Exception as e:
            logger.error(f"列出会话失败: {str(e)}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            # 从内存删除
            if session_id in self._active_sessions:
                del self._active_sessions[session_id]
            
            # 删除文件
            session_file = self.storage_dir / f"session_{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            
            # 删除相关检查点
            checkpoint_pattern = f"checkpoint_{session_id}_*.pkl.gz"
            for checkpoint_file in self.checkpoint_dir.glob(checkpoint_pattern):
                checkpoint_file.unlink()
            
            logger.info(f"删除会话: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除会话失败: {session_id}, 错误: {str(e)}")
            return False
    
    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.title = title
        session.updated_at = datetime.now(timezone.utc)
        return self._save_session(session)
    
    def export_session(self, session_id: str, format: str = "json") -> Optional[str]:
        """导出会话到文件"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        try:
            export_dir = self.storage_dir / "exports"
            export_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format.lower() == "json":
                filename = f"session_{session_id}_{timestamp}.json"
                filepath = export_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
                
            elif format.lower() == "txt":
                filename = f"session_{session_id}_{timestamp}.txt"
                filepath = export_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"对话会话导出\n")
                    f.write(f"会话ID: {session.session_id}\n")
                    f.write(f"标题: {session.title}\n")
                    f.write(f"创建时间: {session.created_at}\n")
                    f.write(f"更新时间: {session.updated_at}\n")
                    f.write(f"消息数量: {len(session.messages)}\n")
                    f.write(f"{'='*50}\n\n")
                    
                    for i, msg in enumerate(session.messages, 1):
                        role_name = {"user": "用户", "assistant": "助手", "system": "系统"}.get(msg.role, msg.role)
                        f.write(f"[{i}] {role_name}:\n{msg.content}\n\n")
            else:
                logger.error(f"不支持的导出格式: {format}")
                return None
            
            logger.info(f"会话导出成功: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"导出会话失败: {session_id}, 错误: {str(e)}")
            return None
    
    def import_session(self, filepath: str) -> Optional[str]:
        """从文件导入会话"""
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                logger.error(f"导入文件不存在: {filepath}")
                return None
            
            if filepath.suffix.lower() == ".json":
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 生成新的会话ID避免冲突
                original_id = data["session_id"]
                new_id = str(uuid.uuid4())
                data["session_id"] = new_id
                data["title"] = f"[导入] {data['title']}"
                
                session = ConversationSession.from_dict(data)
                
                # 保存会话
                self._active_sessions[new_id] = session
                self._save_session(session)
                
                logger.info(f"会话导入成功: {original_id} -> {new_id}")
                return new_id
            else:
                logger.error(f"不支持的导入格式: {filepath.suffix}")
                return None
                
        except Exception as e:
            logger.error(f"导入会话失败: {filepath}, 错误: {str(e)}")
            return None
    
    def _save_session(self, session: ConversationSession) -> bool:
        """保存会话到磁盘"""
        try:
            session_file = self.storage_dir / f"session_{session.session_id}.json"
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"保存会话失败: {session.session_id}, 错误: {str(e)}")
            return False
    
    def _load_session(self, session_id: str) -> Optional[ConversationSession]:
        """从磁盘加载会话"""
        try:
            session_file = self.storage_dir / f"session_{session_id}.json"
            
            if not session_file.exists():
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return ConversationSession.from_dict(data)
            
        except Exception as e:
            logger.error(f"加载会话失败: {session_id}, 错误: {str(e)}")
            return None
    
    def _create_checkpoint(self, session: ConversationSession) -> bool:
        """创建会话检查点"""
        if not self.enable_checkpoints:
            return False
        
        try:
            checkpoint_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            # 压缩历史消息
            compressed_data = gzip.compress(
                pickle.dumps([asdict(msg) for msg in session.messages])
            )
            
            checkpoint = SessionCheckpoint(
                checkpoint_id=checkpoint_id,
                session_id=session.session_id,
                created_at=now,
                message_count=len(session.messages),
                compressed_history=compressed_data,
                metadata={
                    "title": session.title,
                    "compression_level": 9  # 最大压缩级别
                }
            )
            
            # 保存检查点
            checkpoint_file = self.checkpoint_dir / f"checkpoint_{session.session_id}_{now.strftime('%Y%m%d_%H%M%S')}.pkl.gz"
            
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(checkpoint, f)
            
            logger.info(f"检查点创建成功: {checkpoint_id}")
            return True
            
        except Exception as e:
            logger.error(f"创建检查点失败: {session.session_id}, 错误: {str(e)}")
            return False
    
    def list_checkpoints(self, session_id: str) -> List[Dict[str, Any]]:
        """列出会话的所有检查点"""
        try:
            checkpoints = []
            pattern = f"checkpoint_{session_id}_*.pkl.gz"
            
            for checkpoint_file in self.checkpoint_dir.glob(pattern):
                try:
                    with open(checkpoint_file, 'rb') as f:
                        checkpoint = pickle.load(f)
                    
                    checkpoints.append({
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "created_at": checkpoint.created_at.isoformat(),
                        "message_count": checkpoint.message_count,
                        "file_size": checkpoint_file.stat().st_size,
                        "metadata": checkpoint.metadata
                    })
                    
                except Exception as e:
                    logger.warning(f"跳过损坏的检查点: {checkpoint_file}, 错误: {str(e)}")
                    continue
            
            # 按创建时间排序
            checkpoints.sort(key=lambda x: x["created_at"], reverse=True)
            return checkpoints
            
        except Exception as e:
            logger.error(f"列出检查点失败: {session_id}, 错误: {str(e)}")
            return []
    
    def restore_from_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str
    ) -> Optional[ConversationSession]:
        """从检查点恢复会话"""
        try:
            # 查找检查点文件
            checkpoint_files = list(self.checkpoint_dir.glob(f"checkpoint_{session_id}_*.pkl.gz"))
            target_checkpoint = None
            
            for checkpoint_file in checkpoint_files:
                try:
                    with open(checkpoint_file, 'rb') as f:
                        checkpoint = pickle.load(f)
                    
                    if checkpoint.checkpoint_id == checkpoint_id:
                        target_checkpoint = checkpoint
                        break
                        
                except Exception:
                    continue
            
            if not target_checkpoint:
                logger.error(f"检查点不存在: {checkpoint_id}")
                return None
            
            # 解压缩历史消息
            messages_data = pickle.loads(gzip.decompress(target_checkpoint.compressed_history))
            messages = [ChatMessage(**msg_dict) for msg_dict in messages_data]
            
            # 重建会话
            session = ConversationSession(
                session_id=session_id,
                title=target_checkpoint.metadata.get("title", "恢复的会话"),
                created_at=target_checkpoint.created_at,
                updated_at=datetime.now(timezone.utc),
                messages=messages,
                metadata={"restored_from": checkpoint_id}
            )
            
            # 更新缓存和保存
            self._active_sessions[session_id] = session
            self._save_session(session)
            
            logger.info(f"从检查点恢复会话: {session_id}, 消息数: {len(messages)}")
            return session
            
        except Exception as e:
            logger.error(f"从检查点恢复失败: {checkpoint_id}, 错误: {str(e)}")
            return None
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """清理旧会话"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
            cleaned_count = 0
            
            for session_file in self.storage_dir.glob("session_*.json"):
                try:
                    # 检查文件修改时间
                    file_mtime = datetime.fromtimestamp(session_file.stat().st_mtime, tz=timezone.utc)
                    
                    if file_mtime < cutoff_time:
                        # 提取session_id并删除
                        session_id = session_file.stem.replace("session_", "")
                        self.delete_session(session_id)
                        cleaned_count += 1
                        
                except Exception as e:
                    logger.warning(f"清理会话文件失败: {session_file}, 错误: {str(e)}")
                    continue
            
            logger.info(f"清理完成: 删除了 {cleaned_count} 个旧会话")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理旧会话失败: {str(e)}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取会话管理统计信息"""
        try:
            sessions = self.list_sessions(limit=1000)
            
            total_sessions = len(sessions)
            active_sessions = len(self._active_sessions)
            compressed_sessions = sum(1 for s in sessions if s.get("compressed", False))
            
            total_messages = sum(s["message_count"] for s in sessions)
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "compressed_sessions": compressed_sessions,
                "compression_rate": compressed_sessions / max(total_sessions, 1),
                "total_messages": total_messages,
                "avg_messages_per_session": total_messages / max(total_sessions, 1),
                "storage_dir": str(self.storage_dir),
                "enable_compression": self.enable_compression,
                "enable_checkpoints": self.enable_checkpoints
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {}