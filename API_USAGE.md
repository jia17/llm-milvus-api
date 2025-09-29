q# 对话历史管理 API 使用指南

## 概述

重构后的API现在支持：
1. **流式对话** - 实时响应流
2. **会话历史管理** - 持久化对话历史
3. **用户会话统计** - 用户对话数量和统计信息

## 核心API endpoints

### 1. 流式对话API（主要功能）

**POST** `/conversation/stream`

```json
{
  "question": "用户问题",
  "session_id": "会话ID（可选，为空则创建新会话）", 
  "user_id": "用户ID（默认anonymous）",
  "stream": true,
  "title": "对话标题（可选）"
}
```

**响应格式（Server-Sent Events）：**
```
data: {"type": "session", "session_id": "uuid"}
data: {"type": "intent", "intent": "knowledge_query", "confidence": 0.8, "needs_rag": true}
data: {"type": "metadata", "mode": "rag", "sources_count": 3}
data: {"type": "content", "content": "根据 "}
data: {"type": "content", "content": "文档 "}
data: {"type": "sources", "sources": [...]}
data: [DONE]
```

### 2. 会话管理API

#### 创建新会话
**POST** `/sessions`
```json
{
  "user_id": "user123",
  "title": "关于产品的讨论",
  "metadata": {"source": "web"}
}
```

#### 获取用户会话列表  
**GET** `/sessions?user_id=user123&limit=50`

#### 获取会话详情（包含所有消息）
**GET** `/sessions/{session_id}?user_id=user123`

#### 获取会话消息历史
**GET** `/sessions/{session_id}/messages?user_id=user123&limit=20`

#### 更新会话标题
**PUT** `/sessions/{session_id}/title?user_id=user123`
```json
{"title": "新的会话标题"}
```

#### 删除会话
**DELETE** `/sessions/{session_id}?user_id=user123`

### 3. 用户统计API

#### 获取用户会话数量
**GET** `/users/{user_id}/sessions/count`

响应：
```json
{
  "user_id": "user123",
  "session_count": 25,
  "total_messages": 150,
  "compressed_sessions": 5
}
```
