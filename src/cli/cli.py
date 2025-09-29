import click
import json
import time
from pathlib import Path
from typing import List, Optional
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
from src.graph.workflow import RAGWorkflow
from src.utils.helpers import get_config, Logger, PerformanceTimer


class RAGSystem:
    """RAG系统管理类 - LangGraph版本"""
    
    def __init__(self):
        self.workflow = None
        self.initialized = False
    
    def initialize(self, force_reconnect: bool = False):
        """初始化系统组件"""
        try:
            if self.initialized and not force_reconnect:
                return True
            
            click.echo("🚀 初始化RAG系统...")
            
            # 初始化LangGraph工作流
            self.workflow = RAGWorkflow()
            if not self.workflow.initialize_services():
                click.echo("❌ 工作流初始化失败")
                return False
            
            self.initialized = True
            click.echo("🎉 LangGraph RAG系统初始化完成!")
            return True
            
        except Exception as e:
            click.echo(f"❌ 系统初始化失败: {str(e)}", err=True)
            return False
    
    def health_check(self):
        """健康检查"""
        if not self.initialized:
            return {"status": "未初始化"}
        
        try:
            stats = self.workflow.get_stats()
            return {
                "系统状态": "正常" if self.initialized else "异常",
                "工作流状态": "就绪" if stats["workflow_ready"] else "异常",
                "集合名称": stats.get("collection_name", "未知")
            }
        except Exception as e:
            return {"status": "异常", "错误": str(e)}


# 全局RAG系统实例
rag_system = RAGSystem()


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.pass_context
def cli(ctx, config, verbose):
    """LLM RAG 智能问答系统命令行工具"""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # 设置日志级别
    log_level = "DEBUG" if verbose else "INFO"
    Logger.setup_logger(log_level=log_level)
    
    if config:
        click.echo(f"使用配置文件: {config}")


@cli.command()
@click.pass_context
def init(ctx):
    """初始化系统"""
    verbose = ctx.obj.get('verbose', False)
    
    if verbose:
        click.echo("开始系统初始化...")
    
    success = rag_system.initialize(force_reconnect=True)
    
    if success:
        click.echo("✅ 系统初始化成功")
        exit_code = 0
    else:
        click.echo("❌ 系统初始化失败", err=True)
        exit_code = 1
    
    ctx.exit(exit_code)


@cli.command()
@click.pass_context
def status(ctx):
    """检查系统状态"""
    if not rag_system.initialize():
        click.echo("❌ 系统未就绪", err=True)
        ctx.exit(1)
    
    health_info = rag_system.health_check()
    
    click.echo("\n📊 系统状态:")
    for key, value in health_info.items():
        status_icon = "✅" if value in ["正常", "正常"] else "⚠️" if value == "未知" else "❌"
        click.echo(f"  {status_icon} {key}: {value}")
    
    # 详细统计信息
    try:
        stats = rag_system.vector_store.get_collection_stats()
        click.echo(f"\n📈 详细统计:")
        click.echo(f"  📚 集合名称: {stats.get('collection_name', 'N/A')}")
        click.echo(f"  📄 文档块数: {stats.get('entity_count', 0)}")
        click.echo(f"  🔢 向量维度: {stats.get('dimension', 'N/A')}")
        click.echo(f"  📐 索引类型: {stats.get('index_type', 'N/A')}")
    except Exception as e:
        click.echo(f"⚠️ 无法获取详细统计: {str(e)}")


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, help='递归处理目录')
@click.pass_context
def upload(ctx, file_path, recursive):
    """上传文档"""
    if not rag_system.initialize():
        click.echo("❌ 系统未就绪", err=True)
        ctx.exit(1)
    
    file_path = Path(file_path)
    
    try:
        if file_path.is_file():
            # 处理单个文件
            _upload_single_file(file_path)
        elif file_path.is_dir():
            # 处理目录
            _upload_directory(file_path, recursive)
        else:
            click.echo(f"❌ 无效路径: {file_path}", err=True)
            ctx.exit(1)
            
    except Exception as e:
        click.echo(f"❌ 上传失败: {str(e)}", err=True)
        ctx.exit(1)


def _upload_single_file(file_path: Path):
    """上传单个文件"""
    click.echo(f"📤 上传文件: {file_path.name}")
    
    with PerformanceTimer("文档处理"):
        # 使用LangGraph工作流处理上传
        result = rag_system.workflow.upload_document(str(file_path))
        
        if result.get("error"):
            click.echo(f"❌ 上传失败: {result['error']}", err=True)
        else:
            click.echo(f"✅ {result.get('answer', '上传成功')}")


def _upload_directory(dir_path: Path, recursive: bool):
    """上传目录中的文档"""
    click.echo(f"📁 处理目录: {dir_path}")
    
    # 获取支持的文件格式
    supported_formats = set(get_config("document.supported_formats", [".pdf", ".txt", ".md"]))
    
    # 查找文件
    pattern = "**/*" if recursive else "*"
    files = []
    
    for file_path in dir_path.glob(pattern):
        if file_path.is_file() and file_path.suffix.lower() in supported_formats:
            files.append(file_path)
    
    if not files:
        click.echo("⚠️ 未找到支持的文档文件")
        return
    
    click.echo(f"📄 找到 {len(files)} 个文件")
    
    # 处理每个文件
    success_count = 0
    with click.progressbar(files, label="处理文件") as bar:
        for file_path in bar:
            try:
                _upload_single_file(file_path)
                success_count += 1
            except Exception as e:
                click.echo(f"\n❌ 文件处理失败 {file_path.name}: {str(e)}")
    
    click.echo(f"✅ 批量上传完成: {success_count}/{len(files)} 个文件成功")
    
    if success_count > 0:
        click.echo("🔄 重建检索索引...")
        rag_system.retriever.build_sparse_index(force_rebuild=True)
        click.echo("✅ 索引重建完成")


@cli.command()
@click.argument('question')
@click.option('--top-k', '-k', default=5, help='检索文档数量')
@click.option('--method', '-m', default='hybrid', type=click.Choice(['dense', 'sparse', 'hybrid']), help='检索方法')
@click.option('--output', '-o', type=click.Choice(['simple', 'detailed', 'json']), default='simple', help='输出格式')
@click.pass_context
def query(ctx, question, top_k, method, output):
    """查询问答"""
    if not rag_system.initialize():
        click.echo("❌ 系统未就绪", err=True)
        ctx.exit(1)
    
    try:
        click.echo(f"🔍 查询: {question}")
        
        with PerformanceTimer("查询处理"):
            # 使用LangGraph工作流处理查询
            result = rag_system.workflow.query_documents(question)
        
        # 输出结果
        if output == 'json':
            _output_json_result(result)
        elif output == 'detailed':
            _output_detailed_result(result)
        else:
            _output_simple_result(result)
            
    except Exception as e:
        click.echo(f"❌ 查询失败: {str(e)}", err=True)
        ctx.exit(1)


def _output_simple_result(result):
    """简单格式输出"""
    click.echo(f"\n💬 问题: {result.get('query', '未知')}")
    click.echo(f"🤖 回答: {result.get('answer', '无回答')}")
    click.echo(f"⏱️  耗时: {result.get('total_time', 0):.2f}秒")
    
    sources = result.get('sources', [])
    if sources:
        click.echo(f"📚 参考文档: {len(sources)} 个")


def _output_detailed_result(result):
    """详细格式输出"""
    click.echo(f"\n" + "="*60)
    click.echo(f"💬 问题: {result.question}")
    click.echo(f"🤖 回答: {result.answer}")
    click.echo(f"⏱️  总耗时: {result.total_time:.2f}秒")
    click.echo(f"🔍 检索耗时: {result.retrieval_result.retrieval_time:.2f}秒")
    click.echo(f"🎯 生成耗时: {result.generation_time:.2f}秒")
    click.echo(f"📊 检索方法: {result.retrieval_result.method}")
    
    if result.sources:
        click.echo(f"\n📚 参考文档 ({len(result.sources)} 个):")
        for i, source in enumerate(result.sources, 1):
            click.echo(f"\n  📄 文档 {i} (相似度: {source.score:.3f})")
            filename = source.metadata.get('filename', '未知文件')
            click.echo(f"     📁 文件: {filename}")
            click.echo(f"     📝 内容: {source.content[:200]}...")
    else:
        click.echo("\n⚠️ 未找到相关文档")


def _output_json_result(result):
    """JSON格式输出"""
    output_data = {
        "question": result.question,
        "answer": result.answer,
        "total_time": result.total_time,
        "generation_time": result.generation_time,
        "retrieval_time": result.retrieval_result.retrieval_time if result.retrieval_result else 0,
        "method": result.retrieval_result.method if result.retrieval_result else "unknown",
        "sources": [
            {
                "id": source.id,
                "content": source.content,
                "score": source.score,
                "metadata": source.metadata,
                "doc_id": source.doc_id,
                "chunk_index": source.chunk_index
            }
            for source in result.sources
        ]
    }
    
    click.echo(json.dumps(output_data, ensure_ascii=False, indent=2))


@cli.command()
@click.pass_context
def chat(ctx):
    """交互式聊天"""
    if not rag_system.initialize():
        click.echo("❌ 系统未就绪", err=True)
        ctx.exit(1)
    
    click.echo("💬 进入交互式聊天模式")
    click.echo("💡 输入 'quit', 'exit' 或 Ctrl+C 退出")
    click.echo("💡 输入 'help' 查看帮助")
    click.echo("-" * 50)
    
    while True:
        try:
            question = click.prompt("🤔 您的问题", type=str)
            
            if question.lower() in ['quit', 'exit']:
                break
            elif question.lower() == 'help':
                _show_chat_help()
                continue
            elif question.strip() == '':
                continue
            
            # 处理查询
            try:
                with PerformanceTimer("查询处理", verbose=False):
                    retrieval_result = rag_system.retriever.search(
                        query=question,
                        top_k=5,
                        method='hybrid'
                    )
                    
                    generation_result = rag_system.generator.generate_answer(
                        question=question,
                        retrieval_result=retrieval_result
                    )
                
                click.echo(f"\n🤖 {generation_result.answer}")
                
                if generation_result.sources:
                    click.echo(f"📚 参考了 {len(generation_result.sources)} 个文档片段")
                else:
                    click.echo("⚠️ 未找到相关文档")
                
                click.echo(f"⏱️ 耗时: {generation_result.total_time:.2f}秒\n")
                
            except Exception as e:
                click.echo(f"❌ 查询出错: {str(e)}\n")
        
        except (KeyboardInterrupt, EOFError):
            break
    
    click.echo("\n👋 再见!")


def _show_chat_help():
    """显示聊天帮助"""
    help_text = """
💡 聊天模式帮助:
  - 直接输入问题进行查询
  - 'quit' 或 'exit': 退出聊天
  - 'help': 显示此帮助
  - Ctrl+C: 强制退出
    """
    click.echo(help_text)


@cli.command()
@click.argument('doc_id')
@click.pass_context
def delete(ctx, doc_id):
    """删除文档"""
    if not rag_system.initialize():
        click.echo("❌ 系统未就绪", err=True)
        ctx.exit(1)
    
    try:
        success = rag_system.vector_store.delete_by_doc_id(doc_id)
        
        if success:
            click.echo(f"✅ 文档删除成功: {doc_id}")
            
            # 重建索引
            click.echo("🔄 重建检索索引...")
            rag_system.retriever.build_sparse_index(force_rebuild=True)
            click.echo("✅ 索引重建完成")
        else:
            click.echo(f"❌ 文档删除失败或不存在: {doc_id}", err=True)
            ctx.exit(1)
            
    except Exception as e:
        click.echo(f"❌ 删除文档失败: {str(e)}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def rebuild_index(ctx):
    """重建检索索引"""
    if not rag_system.initialize():
        click.echo("❌ 系统未就绪", err=True)
        ctx.exit(1)
    
    try:
        click.echo("🔄 开始重建检索索引...")
        
        with PerformanceTimer("索引重建"):
            rag_system.retriever.build_sparse_index(force_rebuild=True)
        
        click.echo("✅ 索引重建完成")
        
    except Exception as e:
        click.echo(f"❌ 索引重建失败: {str(e)}", err=True)
        ctx.exit(1)


def main():
    """主函数"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n👋 用户中断，退出程序")
        sys.exit(0)
    except Exception as e:
        click.echo(f"❌ 程序异常: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()