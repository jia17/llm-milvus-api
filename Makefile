# LLM RAG Project Makefile

.PHONY: help install dev-install test lint format type-check clean run-api run-web run-cli docker-up docker-down

# 默认目标
help:
	@echo "LLM RAG Project - 可用命令："
	@echo ""
	@echo "📦 安装和环境:"
	@echo "  install       - 安装生产依赖"
	@echo "  dev-install   - 安装开发依赖"
	@echo "  clean         - 清理缓存和临时文件"
	@echo ""
	@echo "🧪 测试和质量:"
	@echo "  test          - 运行所有测试"
	@echo "  test-unit     - 运行单元测试"
	@echo "  test-api      - 运行API测试"
	@echo "  test-cov      - 运行测试并生成覆盖率报告"
	@echo "  lint          - 代码风格检查"
	@echo "  format        - 代码格式化"
	@echo "  type-check    - 类型检查"
	@echo ""
	@echo "🚀 运行服务:"
	@echo "  run-api       - 启动API服务"
	@echo "  run-web       - 启动Web界面"
	@echo "  run-cli       - 运行CLI工具"
	@echo ""
	@echo "🐳 Docker:"
	@echo "  docker-up     - 启动Milvus服务"
	@echo "  docker-down   - 停止Milvus服务"
	@echo "  docker-logs   - 查看Milvus日志"
	@echo ""
	@echo "🔧 开发工具:"
	@echo "  init-env      - 初始化开发环境"
	@echo "  check-deps    - 检查依赖状态"

# 安装依赖
install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install -e .
	pip install pytest pytest-cov pytest-asyncio black flake8 mypy

# 测试
test:
	pytest tests/ -v

test-unit:
	pytest tests/ -v -m "not integration"

test-api:
	pytest tests/test_api.py -v

test-cov:
	pytest tests/ --cov=src --cov-report=html --cov-report=term

# 代码质量
lint:
	flake8 src/ tests/ --max-line-length=120 --ignore=E203,W503

format:
	black src/ tests/ --line-length=120

type-check:
	mypy src/ --ignore-missing-imports

# 运行服务
run-api:
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

run-web:
	streamlit run src/web/streamlit_app.py --server.port 8501 --server.address 0.0.0.0

run-cli:
	python -m src.cli.cli --help

# Docker操作
docker-up:
	cd docker && docker-compose up -d
	@echo "⏳ 等待Milvus启动..."
	@sleep 10
	@echo "✅ Milvus服务已启动"
	@echo "🌐 Attu管理界面: http://localhost:3000"

docker-down:
	cd docker && docker-compose down

docker-logs:
	cd docker && docker-compose logs -f standalone

# 开发环境初始化
init-env:
	@echo "🚀 初始化开发环境..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "📄 已创建.env文件，请编辑添加API密钥"; \
	fi
	$(MAKE) dev-install
	$(MAKE) docker-up
	@echo "✅ 开发环境初始化完成！"
	@echo ""
	@echo "📝 下一步:"
	@echo "1. 编辑 .env 文件，添加API密钥"
	@echo "2. 运行 'make test' 确保一切正常"
	@echo "3. 运行 'make run-api' 启动API服务"
	@echo "4. 运行 'make run-web' 启动Web界面"

# 检查依赖
check-deps:
	@echo "🔍 检查Python环境..."
	@python --version
	@echo "🔍 检查pip包..."
	@pip list | grep -E "(fastapi|streamlit|pymilvus|loguru)"
	@echo "🔍 检查Docker..."
	@docker --version || echo "❌ Docker未安装"
	@echo "🔍 检查Docker Compose..."
	@docker-compose --version || echo "❌ Docker Compose未安装"

# 清理
clean:
	@echo "🧹 清理缓存和临时文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ temp/ logs/ 2>/dev/null || true
	@echo "✅ 清理完成"

# 快速开发命令
dev: format lint type-check test
	@echo "✅ 开发检查完成"

# 部署前检查
pre-deploy: clean format lint type-check test-cov
	@echo "✅ 部署前检查完成"

# 示例命令
demo:
	@echo "🎯 运行演示..."
	python -m src.cli.cli init
	python -m src.cli.cli upload data/sample_docs/
	python -m src.cli.cli query "什么是RAG技术？"

# 备份数据
backup:
	@echo "💾 备份Milvus数据..."
	cd docker && docker-compose exec standalone tar -czf /tmp/milvus_backup.tar.gz /var/lib/milvus
	cd docker && docker cp milvus-standalone:/tmp/milvus_backup.tar.gz ./milvus_backup_$(shell date +%Y%m%d_%H%M%S).tar.gz
	@echo "✅ 备份完成"

# 性能测试
benchmark:
	@echo "⚡ 运行性能测试..."
	python -c "\
import time; \
from src.embedding.embedder import EmbeddingManager; \
from src.utils.helpers import PerformanceTimer; \
manager = EmbeddingManager(); \
test_texts = ['这是测试文本'] * 10; \
with PerformanceTimer('嵌入性能测试'): \
    result = manager.embed_documents(test_texts); \
    print(f'处理了 {len(test_texts)} 个文本'); \
    print(f'生成了 {len(result.embeddings)} 个向量')"