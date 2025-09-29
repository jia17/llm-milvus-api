# LLM-Milvus RAG 系统使用手册

## 项目简介
基于大模型和Milvus向量数据库的智能问答系统，支持多格式文档处理、混合检索策略，提供Web/API/CLI三种接口。

## 核心特性
- **混合检索**: 稠密向量+稀疏关键词双路召回，RRF融合排序
- **智能对话**: 自动判断RAG需求，支持多轮对话和会话管理
- **多接口**: Streamlit Web界面、FastAPI服务、Click CLI工具
- **文档支持**: PDF、TXT、MD、DOCX格式，智能分块处理

## 快速开始

### 1. 环境准备
```bash
# 安装依赖和启动服务
make init-env

# 配置API密钥 (编辑.env文件)
KIMI_API_KEY=your_kimi_key
SILICONFLOW_API_KEY=your_siliconflow_key
```

### 2. 启动服务
```bash
# 启动向量数据库
make docker-up

# 启动Web界面 (http://localhost:8501)
make run-web

# 启动API服务 (http://localhost:8000)
make run-api
```

### 3. 使用方式

**Web界面** - 最直观
- 文档上传和管理
- 智能问答
- 多轮对话

**API调用** - 程序集成
```bash
# 上传文档
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@document.pdf"

# 问答查询
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "你的问题"}'

# 智能对话
curl -X POST http://localhost:8000/conversation \
  -H "Content-Type: application/json" \
  -d '{"question": "问题", "stream": true}'
```

**CLI工具** - 批量处理
```bash
python -m src.cli.cli upload data/sample_docs/
python -m src.cli.cli query "什么是RAG技术？"
```

## 开发运维

### 开发命令
```bash
make dev          # 格式化+检查+测试
make test         # 运行测试
make clean        # 清理缓存
```

### 系统配置
核心配置在`config/config.yaml`:
- 检索权重: `retrieval.dense_weight` (稠密) / `sparse_weight` (稀疏)
- 相似度阈值: `retrieval.similarity_threshold`
- 文档分块: `document.chunk_size` / `chunk_overlap`

### 常见问题
- **Milvus连接失败**: 确保`make docker-up`完成且等待10-15秒
- **检索无结果**: Web界面重建稀疏索引
- **API密钥错误**: 检查`.env`文件配置

---

