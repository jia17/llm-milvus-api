import streamlit as st
import time
import json
import io
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.graph.workflow import RAGWorkflow
from src.utils.helpers import get_config, PerformanceTimer, clean_filename
from src.conversation.session_manager import SessionManager
from src.conversation.models import ChatMessage
import requests
import json
from urllib.parse import urljoin


# 页面配置
st.set_page_config(
    page_title=get_config("web.title", "智能问答系统"),
    page_icon="🤖",
    layout=get_config("web.page_config.layout", "wide"),
    initial_sidebar_state="expanded"
)


@st.cache_resource
def initialize_system():
    """初始化系统组件（使用缓存避免重复初始化）"""
    try:
        # 初始化LangGraph工作流
        workflow = RAGWorkflow()
        if not workflow.initialize_services():
            st.error("⚠️ LangGraph工作流初始化失败")
            return None
        
        # 初始化会话管理器
        session_manager = SessionManager(
            enable_compression=get_config("conversation.enable_compression", True),
            enable_checkpoints=get_config("conversation.enable_checkpoints", True)
        )
        
        return {
            "workflow": workflow,
            "vector_store": workflow.vector_store,
            "retriever": workflow.hybrid_retriever,
            "session_manager": session_manager
        }
        
    except Exception as e:
        st.error(f"❌ 系统初始化失败: {str(e)}")
        return None


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🤖 智能问答系统")
        st.markdown("---")
        
        # 系统状态
        st.subheader("📊 系统状态")
        
        components = st.session_state.get("components")
        if components:
            try:
                stats = fetch_knowledge_stats(components["vector_store"])
                st.success("🟢 系统正常")
                st.metric("📚 文档块数", stats.get("total_chunks", 0))
                st.metric("🔢 向量维度", stats.get("dimension", "N/A"))
            except:
                st.warning("🟡 系统连接异常")
        else:
            st.error("🔴 系统未初始化")
        
        st.markdown("---")
        
        # 设置选项
        st.subheader("⚙️ 设置")
        
        # 检索参数
        top_k = st.slider("检索文档数量", 1, 20, 5)
        st.session_state["top_k"] = top_k
        
        method = st.selectbox(
            "检索方法",
            ["hybrid", "dense", "sparse"],
            index=0,
            format_func=lambda x: {
                "hybrid": "🔄 混合检索",
                "dense": "🎯 稠密向量",
                "sparse": "🔍 稀疏关键词"
            }[x]
        )
        st.session_state["retrieval_method"] = method
        
        # 生成参数
        temperature = st.slider("回答创造性", 0.0, 1.0, 0.7, step=0.1)
        st.session_state["temperature"] = temperature
        
        st.markdown("---")
        
        # 操作按钮
        st.subheader("🔧 操作")
        
        if st.button("💬 会话管理", help="管理对话会话"):
            st.session_state["show_session_manager"] = True
        
        if st.button("📊 查看统计", help="查看详细统计信息"):
            st.session_state["show_stats"] = True
        
        st.markdown("---")
        st.markdown("### 📖 使用指南")
        st.markdown("""
        1. **上传文档**: 支持PDF、TXT、MD、DOCX格式
        2. **提问**: 基于已上传文档内容提问
        3. **聊天**: 普通对话模式
        4. **设置**: 调整检索和生成参数
        """)


def render_upload_section():
    """渲染文档上传区域"""
    st.header("📤 文档上传")
    
    components = st.session_state.get("components")
    if not components:
        st.error("⚠️ 系统未就绪，无法上传文档")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_files = st.file_uploader(
            "选择文档文件",
            type=['pdf', 'txt', 'md', 'docx'],
            accept_multiple_files=True,
            help="支持PDF、TXT、MD、DOCX格式，单文件最大10MB"
        )
    
    with col2:
        st.info(f"""
        📋 **支持格式**
        - PDF文档
        - TXT文本
        - Markdown文件
        - Word文档 (DOCX)
        
        📏 **文件限制**
        - 最大大小: 10MB
        - 批量上传: 支持
        """)
    
    if uploaded_files:
        if st.button("🚀 开始上传", type="primary"):
            upload_progress = st.progress(0)
            status_container = st.container()
            
            total_files = len(uploaded_files)
            success_count = 0
            
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    # 更新进度
                    upload_progress.progress((i + 1) / total_files)
                    
                    with status_container:
                        st.info(f"📤 处理文件: {uploaded_file.name}")
                    
                    # 保存临时文件
                    file_content = uploaded_file.read()
                    file_path = Path("temp") / clean_filename(uploaded_file.name)
                    file_path.parent.mkdir(exist_ok=True)
                    
                    with open(file_path, "wb") as f:
                        f.write(file_content)
                    
                    # 处理文档
                    with st.spinner(f"处理 {uploaded_file.name}..."):
                        # 加载并分块
                        chunks = components["workflow"].document_loader.load_and_chunk_document(str(file_path))
                        
                        # 生成嵌入
                        texts = [chunk.content for chunk in chunks]
                        embedding_result = components["workflow"].embedding_manager.embed_documents(texts)
                        
                        # 插入数据库
                        insert_result = components["workflow"].vector_store.insert_documents(
                            chunks, embedding_result.embeddings
                        )
                        
                        if insert_result.success:
                            success_count += 1
                            with status_container:
                                st.success(f"✅ {uploaded_file.name}: {len(chunks)} 个文档块")
                        else:
                            with status_container:
                                st.error(f"❌ {uploaded_file.name}: {insert_result.error}")
                    
                    # 清理临时文件
                    try:
                        file_path.unlink()
                    except:
                        pass
                
                except Exception as e:
                    with status_container:
                        st.error(f"❌ {uploaded_file.name}: {str(e)}")
            
            # 完成上传
            upload_progress.progress(1.0)
            
            if success_count > 0:
                st.success(f"🎉 上传完成! 成功处理 {success_count}/{total_files} 个文件")
                
            else:
                st.error("❌ 没有文件成功上传")


def render_query_section():
    """渲染问答查询区域"""
    st.header("🔍 智能问答")
    
    components = st.session_state.get("components")
    if not components:
        st.error("⚠️ 系统未就绪，无法进行查询")
        return
    
    # 问题输入
    col1, col2 = st.columns([4, 1])
    
    with col1:
        question = st.text_input(
            "请输入您的问题:",
            placeholder="例如: RAG技术的优势是什么？",
            key="question_input"
        )
    
    with col2:
        query_button = st.button("🔍 提问", type="primary", disabled=not question.strip())
    
    # 处理查询
    if query_button and question.strip():
        with st.spinner("🤔 思考中..."):
            try:
                # 获取参数
                top_k = st.session_state.get("top_k", 5)
                method = st.session_state.get("retrieval_method", "hybrid")
                temperature = st.session_state.get("temperature", 0.7)
                
                start_time = time.time()
                
                # 检索
                retrieval_result = components["retriever"].search(
                    query=question,
                    top_k=top_k,
                    method=method
                )
                
                # 生成回答
                generation_result = components["generator"].generate_answer(
                    question=question,
                    retrieval_result=retrieval_result,
                    temperature=temperature
                )
                
                total_time = time.time() - start_time
                
                # 显示结果
                st.markdown("### 🤖 AI回答")
                
                # 回答内容
                answer_container = st.container()
                with answer_container:
                    st.markdown(f"**{generation_result.answer}**")
                
                # 性能指标
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("⏱️ 总耗时", f"{total_time:.2f}s")
                with col2:
                    st.metric("🔍 检索耗时", f"{retrieval_result.retrieval_time:.2f}s")
                with col3:
                    st.metric("🎯 生成耗时", f"{generation_result.generation_time:.2f}s")
                with col4:
                    st.metric("📚 参考文档", len(generation_result.sources))
                
                # 参考文档
                if generation_result.sources:
                    st.markdown("### 📖 参考文档")
                    
                    for i, source in enumerate(generation_result.sources, 1):
                        with st.expander(f"📄 文档 {i} (相似度: {source.score:.3f})"):
                            filename = source.metadata.get('filename', '未知文件')
                            st.markdown(f"**📁 文件名:** {filename}")
                            st.markdown(f"**🔗 文档ID:** `{source.doc_id}`")
                            st.markdown(f"**📝 内容:**")
                            st.text_area(
                                "内容预览",
                                value=source.content,
                                height=150,
                                key=f"content_{i}",
                                disabled=True
                            )
                else:
                    st.warning("⚠️ 未找到相关文档，请检查是否已上传相关内容")
                
            except Exception as e:
                st.error(f"❌ 查询失败: {str(e)}")


def render_smart_conversation_section():
    """渲染智能对话区域 - 支持会话管理和意图识别"""
    st.header("🤖 智能对话")
    st.caption("🎯 智能判断何时使用RAG检索，支持多轮对话和会话管理")
    
    components = st.session_state.get("components")
    if not components or not components.get("session_manager"):
        st.error("⚠️ 会话管理器未初始化")
        return
    
    session_manager = components["session_manager"]
    
    # 会话选择和管理
    render_session_selector(session_manager)
    
    # 获取当前会话
    current_session_id = st.session_state.get("current_session_id")
    if not current_session_id:
        st.info("💡 请先创建或选择一个会话")
        return
    
    # 显示对话历史
    render_conversation_history(session_manager, current_session_id)




def render_session_selector(session_manager):
    """渲染会话选择器 - 使用API"""
    st.subheader("📋 会话管理")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # 从API获取会话列表
        try:
            api_url = "http://localhost:8000/sessions"
            response = requests.get(api_url, params={"user_id": "anonymous", "limit": 20}, timeout=10)
            
            if response.status_code == 200:
                sessions_data = response.json()
                sessions = sessions_data.get("sessions", [])
            else:
                st.warning("⚠️ 无法获取会话列表，使用本地数据")
                sessions = session_manager.list_sessions(limit=20)
        
        except Exception as e:
            st.warning(f"⚠️ API调用失败，使用本地数据: {str(e)}")
            sessions = session_manager.list_sessions(limit=20)
        
        if sessions:
            session_options = {}
            for session in sessions:
                created_time = datetime.fromisoformat(session["created_at"]).strftime("%m-%d %H:%M")
                label = f"🕐 {created_time} | {session['title']} ({session['message_count']}条)"
                session_options[label] = session["session_id"]
            
            selected_label = st.selectbox(
                "选择会话",
                options=list(session_options.keys()),
                index=0 if st.session_state.get("current_session_id") in session_options.values() else None,
                key="session_selector"
            )
            
            if selected_label:
                selected_id = session_options[selected_label]
                if st.session_state.get("current_session_id") != selected_id:
                    st.session_state["current_session_id"] = selected_id
                    st.rerun()
        else:
            st.info("暂无会话")
    
    with col2:
        if st.button("➕ 新建会话", use_container_width=True):
            try:
                # 使用API创建会话
                api_url = "http://localhost:8000/sessions"
                payload = {
                    "user_id": "anonymous",
                    "title": f"对话 {datetime.now().strftime('%m-%d %H:%M')}",
                    "metadata": {}
                }
                response = requests.post(api_url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    new_session_id = result["session_id"]
                    st.session_state["current_session_id"] = new_session_id
                    st.success(f"✅ 创建会话: {result['title']}")
                else:
                    # 回退到本地创建
                    new_session = session_manager.create_session(
                        title=f"对话 {datetime.now().strftime('%m-%d %H:%M')}"
                    )
                    st.session_state["current_session_id"] = new_session.session_id
                    st.success(f"✅ 创建会话: {new_session.title}")
                
            except Exception as e:
                # 回退到本地创建
                new_session = session_manager.create_session(
                    title=f"对话 {datetime.now().strftime('%m-%d %H:%M')}"
                )
                st.session_state["current_session_id"] = new_session.session_id
                st.success(f"✅ 创建会话: {new_session.title}")
            
            st.rerun()
    
    with col3:
        current_session_id = st.session_state.get("current_session_id")
        if current_session_id and st.button("🗑️ 删除会话", use_container_width=True):
            if st.session_state.get(f"confirm_delete_session_{current_session_id}"):
                try:
                    # 使用API删除会话
                    api_url = f"http://localhost:8000/sessions/{current_session_id}"
                    response = requests.delete(api_url, params={"user_id": "anonymous"}, timeout=10)
                    
                    if response.status_code == 200:
                        st.success("✅ 会话已删除")
                    else:
                        # 回退到本地删除
                        session_manager.delete_session(current_session_id)
                        st.success("✅ 会话已删除")
                
                except Exception as e:
                    # 回退到本地删除
                    session_manager.delete_session(current_session_id)
                    st.success("✅ 会话已删除")
                
                st.session_state["current_session_id"] = None
                st.session_state[f"confirm_delete_session_{current_session_id}"] = False
                st.rerun()
            else:
                st.session_state[f"confirm_delete_session_{current_session_id}"] = True
                st.warning("⚠️ 再次点击确认删除")


def render_conversation_history(session_manager, session_id):
    """渲染对话历史 - 从API获取会话消息"""
    try:
        # 调用API获取会话历史
        api_url = f"http://localhost:8000/sessions/{session_id}/messages"
        response = requests.get(api_url, params={"user_id": "anonymous"}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            messages = result.get("messages", [])
        else:
            st.warning("⚠️ 无法获取会话历史，使用本地缓存")
            messages = session_manager.get_messages(session_id, include_system=False)
            # 转换为API格式
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if hasattr(msg, 'timestamp') and msg.timestamp else "",
                    "metadata": msg.metadata if hasattr(msg, 'metadata') else {}
                }
                for msg in messages
            ]
    
    except Exception as e:
        st.warning(f"⚠️ API调用失败，使用本地缓存: {str(e)}")
        messages = session_manager.get_messages(session_id, include_system=False)
        # 转换为API格式
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if hasattr(msg, 'timestamp') and msg.timestamp else "",
                "metadata": msg.metadata if hasattr(msg, 'metadata') else {}
            }
            for msg in messages
        ]
    
    # 显示对话
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(messages):
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["content"])
            else:
                with st.chat_message("assistant"):
                    # 显示回答内容
                    st.write(msg["content"])
                    
                    # 检查是否使用了RAG检索
                    metadata = msg.get("metadata", {})
                    if metadata:
                        mode = metadata.get('mode', 'chat')
                        
                        if mode == "rag":
                            # RAG模式标识和统计信息
                            sources_count = metadata.get('sources_count', 0)
                            st.caption(f"🔍 **使用了RAG检索** | 参考文档: {sources_count} 个")
                            
                            # 显示检索的chunks
                            sources = metadata.get('sources', [])
                            if sources:
                                with st.expander(f"📖 查看检索内容 ({len(sources)}个文档片段)", expanded=False):
                                    for idx, source in enumerate(sources, 1):
                                        st.markdown(f"**📄 片段 {idx}** (相似度: {source.get('score', 0):.3f})")
                                        filename = source.get('metadata', {}).get('filename', '未知文件')
                                        st.markdown(f"📁 来源: {filename}")
                                        st.text_area(
                                            f"内容预览 {idx}",
                                            value=source.get('content', ''),
                                            height=100,
                                            key=f"history_source_{session_id}_{i}_{idx}",
                                            disabled=True
                                        )
                                        if idx < len(sources):
                                            st.markdown("---")
                        else:
                            # 聊天模式标识
                            st.caption(f"💬 **聊天模式** | 意图: {metadata.get('intent', 'unknown')}")
                    else:
                        # 兼容旧消息，没有metadata的情况
                        st.caption("💬 **聊天模式** (旧消息)")
                    
                    st.markdown("---")


def stream_chat_api(question: str, session_id: str = None, user_id: str = "anonymous"):
    """调用流式对话API"""
    api_url = "http://localhost:8000/conversation/stream"
    
    payload = {
        "question": question,
        "session_id": session_id,
        "user_id": user_id,
        "stream": True
    }
    
    response = requests.post(api_url, json=payload, stream=True, timeout=60)
    response.raise_for_status()
    
    return response


def handle_smart_conversation_input():
    """处理智能对话输入 - 使用新的流式API"""
    components = st.session_state.get("components")
    if not components:
        return
    
    current_session_id = st.session_state.get("current_session_id")
    
    # 对话输入
    if prompt := st.chat_input("输入消息...", key="smart_chat_input"):
        # 显示用户消息
        with st.chat_message("user"):
            st.write(prompt)
        
        # 生成回答
        with st.chat_message("assistant"):
            try:
                # 创建容器用于流式显示
                answer_container = st.empty()
                metadata_container = st.empty()
                sources_container = st.empty()
                
                # 调用流式API
                response = stream_chat_api(prompt, current_session_id, "anonymous")
                
                # 处理流式响应
                current_answer = ""
                session_info = {}
                sources = []
                metadata = {}
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                            
                            try:
                                parsed = json.loads(data)
                                
                                if parsed['type'] == 'session':
                                    session_info = parsed
                                    # 更新当前会话ID
                                    st.session_state["current_session_id"] = parsed['session_id']
                                
                                elif parsed['type'] == 'intent':
                                    metadata.update(parsed)
                                
                                elif parsed['type'] == 'metadata':
                                    metadata.update(parsed)
                                    
                                    # 显示模式信息
                                    mode = parsed.get('mode', 'unknown')
                                    if mode == 'rag':
                                        sources_count = parsed.get('sources_count', 0)
                                        metadata_container.info(f"🔍 RAG模式 | 检索到 {sources_count} 个文档")
                                    else:
                                        metadata_container.info("💬 聊天模式")
                                
                                elif parsed['type'] == 'content':
                                    current_answer += parsed['content']
                                    answer_container.markdown(current_answer)
                                
                                elif parsed['type'] == 'sources':
                                    sources = parsed['sources']
                                    
                                    # 显示参考文档
                                    if sources:
                                        with sources_container.expander(f"📖 参考文档 ({len(sources)}个)", expanded=False):
                                            for i, source in enumerate(sources, 1):
                                                st.markdown(f"**📄 文档 {i}** (相似度: {source.get('score', 0):.3f})")
                                                filename = source.get('metadata', {}).get('filename', '未知文件')
                                                st.caption(f"📁 来源: {filename}")
                                                with st.container():
                                                    st.text_area(
                                                        f"内容 {i}",
                                                        value=source.get('content', ''),
                                                        height=100,
                                                        key=f"stream_source_{i}_{session_info.get('session_id', 'temp')}",
                                                        disabled=True
                                                    )
                                                if i < len(sources):
                                                    st.markdown("---")
                                
                                elif parsed['type'] == 'error':
                                    error_msg = parsed.get('error', '未知错误')
                                    st.error(f"❌ 对话失败: {error_msg}")
                                    current_answer = f"抱歉，对话失败: {error_msg}"
                                    break
                            
                            except json.JSONDecodeError:
                                continue
                
                # 显示性能指标
                if metadata:
                    mode = metadata.get('mode', 'unknown')
                    confidence = metadata.get('confidence', 0)
                    
                    if mode == 'rag':
                        # RAG模式的详细指标
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("🎯 意图置信度", f"{confidence:.2f}")
                        with col2:
                            st.metric("📚 检索模式", "RAG")
                        with col3:
                            st.metric("📄 参考文档", len(sources))
                    else:
                        # 聊天模式简单显示
                        st.caption(f"💬 聊天模式 | 意图: {metadata.get('intent', 'unknown')}")
                
            except Exception as e:
                error_msg = f"对话失败: {str(e)}"
                st.error(f"❌ {error_msg}")
        
        # 刷新页面显示最新消息
        st.rerun()
                    




def render_stats_section():
    """渲染统计信息区域"""
    if not st.session_state.get("show_stats", False):
        return
    
    st.header("📊 系统统计")
    
    components = st.session_state.get("components")
    if not components:
        st.error("⚠️ 系统未就绪")
        return
    
    try:
        # Milvus统计
        st.subheader("🗄️ 向量数据库")
        milvus_stats = components["vector_store"].get_collection_stats()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📚 集合名称", milvus_stats.get("collection_name", "N/A"))
        with col2:
            st.metric("📄 文档块数", milvus_stats.get("entity_count", 0))
        with col3:
            st.metric("🔢 向量维度", milvus_stats.get("dimension", "N/A"))
        
        # 检索器统计
        st.subheader("🔍 检索器")
        retriever_stats = components["retriever"].get_stats()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("⚖️ 稠密权重", f"{retriever_stats.get('dense_weight', 0):.1f}")
            st.metric("🎯 相似度阈值", f"{retriever_stats.get('similarity_threshold', 0):.2f}")
        with col2:
            st.metric("🔍 稀疏权重", f"{retriever_stats.get('sparse_weight', 0):.1f}")
            sparse_built = "✅" if retriever_stats.get('sparse_index_built', False) else "❌"
            st.metric("📇 稀疏索引", sparse_built)
        
        # 生成器统计
        st.subheader("🤖 生成器")
        generator_stats = components["generator"].get_stats()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🧠 模型", generator_stats.get("model", "N/A"))
            st.metric("📏 最大上下文", generator_stats.get("max_context_length", 0))
        with col2:
            st.metric("🎛️ 温度", f"{generator_stats.get('temperature', 0):.1f}")
            st.metric("🔢 最大Token", generator_stats.get("max_tokens", 0))
        
        # 健康检查
        st.subheader("🏥 健康检查")
        health_info = components["vector_store"].health_check()
        
        health_data = {
            "连接状态": "✅ 正常" if health_info.get("connected", False) else "❌ 异常",
            "集合存在": "✅ 是" if health_info.get("collection_exists", False) else "❌ 否",
            "集合加载": "✅ 是" if health_info.get("collection_loaded", False) else "❌ 否",
            "索引存在": "✅ 是" if health_info.get("index_exists", False) else "❌ 否"
        }
        
        for key, value in health_data.items():
            st.text(f"{key}: {value}")
        
    except Exception as e:
        st.error(f"❌ 获取统计信息失败: {str(e)}")
    
    if st.button("❌ 关闭统计"):
        st.session_state["show_stats"] = False
        st.rerun()


def render_session_management_modal():
    """渲染会话管理模态框"""
    if not st.session_state.get("show_session_manager", False):
        return
    
    components = st.session_state.get("components")
    if not components or not components.get("session_manager"):
        st.error("⚠️ 会话管理器未初始化")
        return
    
    session_manager = components["session_manager"]
    
    st.header("📋 会话管理")
    
    # 会话统计
    st.subheader("📊 会话统计")
    stats = session_manager.get_stats()
    
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 总会话数", stats.get("total_sessions", 0))
        with col2:
            st.metric("🔄 活跃会话", stats.get("active_sessions", 0))
        with col3:
            st.metric("📁 压缩会话", stats.get("compressed_sessions", 0))
        with col4:
            st.metric("💬 总消息数", stats.get("total_messages", 0))
        
        # 压缩率
        compression_rate = stats.get("compression_rate", 0)
        st.progress(compression_rate, text=f"压缩率: {compression_rate:.1%}")
    
    st.markdown("---")
    
    # 会话列表管理
    st.subheader("📜 会话列表")
    
    # 操作按钮
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 刷新列表", use_container_width=True):
            st.rerun()
    
    with col2:
        cleanup_days = st.selectbox("清理天数", [7, 30, 90], index=1)
        if st.button(f"🧹 清理{cleanup_days}天前", use_container_width=True):
            cleaned = session_manager.cleanup_old_sessions(cleanup_days)
            st.success(f"✅ 清理了 {cleaned} 个旧会话")
            st.rerun()
    
    with col3:
        if st.button("📥 导入会话", use_container_width=True):
            st.session_state["show_import_dialog"] = True
    
    # 会话列表
    sessions = session_manager.list_sessions(limit=50, include_metadata=True)
    
    if sessions:
        st.info(f"📋 共有 {len(sessions)} 个会话")
        
        for session in sessions:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                
                with col1:
                    # 会话信息
                    created_time = datetime.fromisoformat(session["created_at"]).strftime("%Y-%m-%d %H:%M")
                    compressed_icon = "📁" if session.get("compressed", False) else ""
                    st.markdown(f"**📋 {session['title']}** {compressed_icon}")
                    st.caption(f"创建时间: {created_time} | 消息数: {session['message_count']}")
                
                with col2:
                    if st.button("📝 编辑", key=f"edit_{session['session_id']}"):
                        st.session_state[f"edit_title_{session['session_id']}"] = True
                
                with col3:
                    if st.button("📤 导出", key=f"export_{session['session_id']}"):
                        # 导出会话
                        export_path = session_manager.export_session(session["session_id"], "json")
                        if export_path:
                            st.success(f"✅ 已导出到: {export_path}")
                        else:
                            st.error("❌ 导出失败")
                
                with col4:
                    if st.button("🕰️ 检查点", key=f"checkpoints_{session['session_id']}"):
                        st.session_state[f"show_checkpoints_{session['session_id']}"] = True
                
                with col5:
                    if st.button("🗑️ 删除", key=f"delete_session_{session['session_id']}"):
                        st.session_state[f"confirm_delete_session_{session['session_id']}"] = True
                
                # 编辑标题对话框
                if st.session_state.get(f"edit_title_{session['session_id']}", False):
                    new_title = st.text_input(
                        "新标题",
                        value=session['title'],
                        key=f"new_title_{session['session_id']}"
                    )
                    
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("✅ 保存", key=f"save_title_{session['session_id']}"):
                            if session_manager.update_session_title(session['session_id'], new_title):
                                st.success("✅ 标题已更新")
                            else:
                                st.error("❌ 更新失败")
                            st.session_state[f"edit_title_{session['session_id']}"] = False
                            st.rerun()
                    
                    with col_cancel:
                        if st.button("❌ 取消", key=f"cancel_title_{session['session_id']}"):
                            st.session_state[f"edit_title_{session['session_id']}"] = False
                            st.rerun()
                
                # 检查点管理
                if st.session_state.get(f"show_checkpoints_{session['session_id']}", False):
                    checkpoints = session_manager.list_checkpoints(session['session_id'])
                    
                    if checkpoints:
                        st.info(f"🕰️ 会话 '{session['title']}' 的检查点 ({len(checkpoints)} 个)")
                        
                        for checkpoint in checkpoints:
                            checkpoint_time = datetime.fromisoformat(checkpoint["created_at"]).strftime("%m-%d %H:%M")
                            file_size = checkpoint["file_size"] / 1024  # KB
                            
                            st.markdown(f"**🕰️ {checkpoint_time}** | {checkpoint['message_count']} 消息 | {file_size:.1f}KB")
                            
                            if st.button("🔄 恢复", key=f"restore_{checkpoint['checkpoint_id']}"):
                                restored = session_manager.restore_from_checkpoint(session['session_id'], checkpoint['checkpoint_id'])
                                if restored:
                                    st.success("✅ 会话已恢复")
                                    st.rerun()
                                else:
                                    st.error("❌ 恢复失败")
                    else:
                        st.info("💭 暂无检查点")
                    
                    if st.button("❌ 关闭检查点", key=f"close_checkpoints_{session['session_id']}"):
                        st.session_state[f"show_checkpoints_{session['session_id']}"] = False
                        st.rerun()
                
                st.markdown("---")
    else:
        st.info("💭 暂无会话")
    
    # 导入对话框
    if st.session_state.get("show_import_dialog", False):
        st.subheader("📥 导入会话")
        
        uploaded_file = st.file_uploader(
            "选择会话文件",
            type=['json'],
            help="支持JSON格式的会话文件"
        )
        
        if uploaded_file:
            col_import, col_cancel = st.columns(2)
            
            with col_import:
                if st.button("📥 开始导入", type="primary"):
                    # 保存临时文件
                    temp_path = Path("temp") / uploaded_file.name
                    temp_path.parent.mkdir(exist_ok=True)
                    
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.read())
                    
                    # 导入会话
                    components = st.session_state.get("components")
                    if components and "session_manager" in components:
                        new_session_id = components["session_manager"].import_session(str(temp_path))
                    else:
                        st.error("❌ 会话管理器未初始化")
                        new_session_id = None
                    
                    # 清理临时文件
                    try:
                        temp_path.unlink()
                    except:
                        pass
                    
                    if new_session_id:
                        st.success(f"✅ 会话导入成功: {new_session_id}")
                        st.session_state["show_import_dialog"] = False
                        st.rerun()
                    else:
                        st.error("❌ 导入失败")
            
            with col_cancel:
                if st.button("❌ 取消导入"):
                    st.session_state["show_import_dialog"] = False
                    st.rerun()
    
    # 关闭按钮
    if st.button("❌ 关闭会话管理"):
        st.session_state["show_session_manager"] = False
        st.rerun()


def fetch_documents(vector_store):
    """获取文档列表"""
    try:
        if not vector_store.collection:
            return {"documents": [], "total": 0}
        
        # 复用统一的文档统计逻辑
        stats = fetch_knowledge_stats(vector_store)
        if not stats.get("total_documents"):
            return {"documents": [], "total": 0}
        
        # 获取所有chunks并分组
        search_results = vector_store.collection.query(
            expr="doc_id != ''",
            output_fields=["doc_id", "content", "metadata", "chunk_index"],
            limit=10000
        )
        
        # 按文档分组
        doc_chunks = {}
        for result in search_results:
            doc_id = result.get('doc_id')
            if doc_id:
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = []
                doc_chunks[doc_id].append(result)
        
        # 构建文档信息
        docs = []
        for doc_id, chunks in doc_chunks.items():
            if chunks:
                # 使用第一个chunk的metadata作为文档信息
                first_chunk = chunks[0]
                try:
                    metadata = json.loads(first_chunk.get('metadata', '{}'))
                except:
                    metadata = {}
                
                # 计算总内容长度用于预览
                total_content = " ".join([chunk.get('content', '') for chunk in chunks])
                preview = total_content[:200] + '...' if len(total_content) > 200 else total_content
                
                docs.append({
                    "doc_id": doc_id,
                    "filename": metadata.get('filename', '未知文件'),
                    "file_type": metadata.get('file_type', 'unknown'),
                    "file_size": metadata.get('file_size', 0),
                    "created_time": metadata.get('created_time', 0),
                    "modified_time": metadata.get('modified_time', 0),
                    "preview": preview,
                    "chunk_count": len(chunks)
                })
        
        return {"documents": docs, "total": len(docs)}
        
    except Exception as e:
        st.error(f"获取文档列表失败: {str(e)}")
        return {"documents": [], "total": 0}


def fetch_knowledge_stats(vector_store):
    """获取知识库统计"""
    try:
        if not vector_store.collection:
            return {}
        
        # 获取基础统计
        collection_stats = vector_store.get_collection_stats()
        
        # 获取所有chunks
        all_chunks = vector_store.collection.query(
            expr="doc_id != ''",
            output_fields=["doc_id", "metadata"],
            limit=10000
        )
        
        # 基于文档级别进行统计
        documents = {}  # doc_id -> metadata
        for chunk in all_chunks:
            doc_id = chunk.get('doc_id')
            if not doc_id:
                continue
                
            try:
                import json
                metadata = json.loads(chunk.get('metadata', '{}'))
                
                # 只存储每个文档的第一个chunk的metadata
                if doc_id not in documents:
                    documents[doc_id] = metadata
                    
            except:
                continue
        
        # 文档总数
        doc_count = len(documents)
        
        # 文件类型统计（基于文档级别）
        file_types = {}
        for metadata in documents.values():
            file_type = metadata.get('file_type', 'unknown')
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        # 实际chunks数量（去重后的真实文档块数）
        actual_chunks = len(all_chunks)
        
        return {
            "total_documents": doc_count,
            "total_chunks": actual_chunks,  # 显示真实chunks数量
            "file_types": file_types,
            "collection_name": collection_stats.get("collection_name"),
            "dimension": collection_stats.get("dimension"),
            "index_type": collection_stats.get("index_type")
        }
        
    except Exception as e:
        st.error(f"获取知识库统计失败: {str(e)}")
        return {}


def search_documents(vector_store, query: str, limit: int = 10):
    """搜索文档 - 使用向量检索而不是LIKE查询"""
    try:
        if not vector_store.collection:
            return {"results": [], "total": 0}
        
        # 获取系统组件进行向量检索
        components = st.session_state.get("components")
        if not components or not components.get("retriever"):
            # 降级方案：获取所有文档然后在内存中过滤
            all_results = vector_store.collection.query(
                expr="doc_id != ''",
                output_fields=["id", "doc_id", "content", "metadata", "chunk_index"],
                limit=1000  # 获取更多文档用于过滤
            )
            
            # 在内存中进行简单的文本匹配
            search_results = []
            query_lower = query.lower()
            
            for result in all_results:
                content = result.get('content', '')
                if query_lower in content.lower():
                    try:
                        import json
                        metadata = json.loads(result.get('metadata', '{}'))
                        
                        search_results.append({
                            "id": result.get('id'),
                            "doc_id": result.get('doc_id'),
                            "filename": metadata.get('filename', '未知文件'),
                            "content": content,
                            "chunk_index": result.get('chunk_index', 0),
                            "highlight": content.replace(query, f"**{query}**")
                        })
                        
                        if len(search_results) >= limit:
                            break
                    except:
                        continue
            
            return {"results": search_results, "total": len(search_results), "query": query}
        
        else:
            # 使用向量检索器进行智能搜索
            retriever = components["retriever"]
            retrieval_result = retriever.search(
                query=query,
                top_k=limit,
                method="hybrid"
            )
            
            search_results = []
            for hit in retrieval_result.hits:
                search_results.append({
                    "id": hit.id,
                    "doc_id": hit.doc_id,
                    "filename": hit.metadata.get('filename', '未知文件'),
                    "content": hit.content,
                    "chunk_index": hit.chunk_index,
                    "highlight": hit.content.replace(query, f"**{query}**"),
                    "score": hit.score
                })
            
            return {"results": search_results, "total": len(search_results), "query": query}
        
    except Exception as e:
        st.error(f"搜索文档失败: {str(e)}")
        return {"results": [], "total": 0}


def get_document_detail(vector_store, doc_id: str):
    """获取文档详细信息"""
    try:
        if not vector_store.collection:
            return None
        
        # 查询该文档的所有块
        chunks = vector_store.collection.query(
            expr=f'doc_id == "{doc_id}"',
            output_fields=["id", "content", "metadata", "chunk_index"],
            limit=1000
        )
        
        if not chunks:
            return None
        
        # 按chunk_index排序
        chunks.sort(key=lambda x: x.get('chunk_index', 0))
        
        # 解析第一个块的metadata作为文档metadata
        import json
        try:
            doc_metadata = json.loads(chunks[0].get('metadata', '{}'))
        except:
            doc_metadata = {}
        
        # 构建响应
        doc_info = {
            "doc_id": doc_id,
            "filename": doc_metadata.get('filename', '未知文件'),
            "file_type": doc_metadata.get('file_type', 'unknown'),
            "file_size": doc_metadata.get('file_size', 0),
            "created_time": doc_metadata.get('created_time', 0),
            "modified_time": doc_metadata.get('modified_time', 0),
            "chunk_count": len(chunks),
            "chunks": []
        }
        
        for chunk in chunks:
            try:
                chunk_metadata = json.loads(chunk.get('metadata', '{}'))
            except:
                chunk_metadata = {}
                
            doc_info["chunks"].append({
                "id": chunk.get('id'),
                "content": chunk.get('content', ''),
                "chunk_index": chunk.get('chunk_index', 0),
                "chunk_length": chunk_metadata.get('chunk_length', 0)
            })
        
        return doc_info
        
    except Exception as e:
        st.error(f"获取文档详情失败: {str(e)}")
        return None


def delete_document(vector_store, doc_id: str):
    """删除文档"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"开始删除文档: {doc_id}")
        
        # 检查文档是否存在
        if not vector_store.collection:
            st.error("❌ 向量数据库连接未初始化")
            return False
        
        # 先查询文档是否存在
        expr = f'doc_id == "{doc_id}"'
        existing_docs = vector_store.collection.query(
            expr=expr,
            output_fields=["id"],
            limit=1
        )
        
        if not existing_docs:
            st.info("ℹ️ 文档已不存在于数据库中")
            return True
        
        # 执行删除
        result = vector_store.delete_by_doc_id(doc_id)
        
        if result:
            logger.info(f"文档删除成功: {doc_id}")
        else:
            logger.error(f"文档删除失败: {doc_id}")
        
        return result
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"删除文档异常: {doc_id}, 错误: {str(e)}")
        st.error(f"删除文档失败: {str(e)}")
        return False


def render_knowledge_management():
    """渲染知识库管理界面"""
    st.header("📚 知识库管理")
    
    components = st.session_state.get("components")
    if not components:
        st.error("⚠️ 系统未就绪，无法管理知识库")
        return
    
    vector_store = components["vector_store"]
    
    # 知识库统计
    st.subheader("📊 知识库统计")
    
    stats = fetch_knowledge_stats(vector_store)
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📚 文档总数", stats.get("total_documents", 0))
        with col2:
            st.metric("📄 文档块数", stats.get("total_chunks", 0))
        with col3:
            st.metric("🔢 向量维度", stats.get("dimension", "N/A"))
        with col4:
            st.metric("📇 索引类型", stats.get("index_type", "N/A"))
        
        # 文件类型分布
        if stats.get("file_types"):
            st.subheader("📁 文件类型分布")
            file_types = stats["file_types"]
            
            # 显示为图表
            if file_types:
                cols = st.columns(len(file_types))
                for i, (file_type, count) in enumerate(file_types.items()):
                    with cols[i]:
                        st.metric(f"📄 {file_type.upper()}", count)
    
    st.markdown("---")
    
    # 搜索功能
    st.subheader("🔍 搜索文档")
    col1, col2 = st.columns([4, 1])
    
    with col1:
        search_query = st.text_input("搜索关键词", placeholder="输入要搜索的内容...")
    
    with col2:
        search_limit = st.selectbox("结果数量", [5, 10, 20, 50], index=1)
    
    if search_query:
        with st.spinner("🔍 搜索中..."):
            search_results = search_documents(vector_store, search_query, search_limit)
        
        if search_results["results"]:
            st.success(f"🎯 找到 {search_results['total']} 个结果")
            
            for i, result in enumerate(search_results["results"], 1):
                with st.expander(f"📄 {result['filename']} - 块 {result['chunk_index']} (相关度较高)"):
                    st.markdown(f"**文档ID:** `{result['doc_id']}`")
                    st.markdown(f"**文件名:** {result['filename']}")
                    st.markdown(f"**块索引:** {result['chunk_index']}")
                    st.markdown("**内容预览:**")
                    st.text_area("", value=result['content'], height=100, key=f"search_content_{i}", disabled=True)
        else:
            st.warning("😔 未找到相关内容")
    
    st.markdown("---")
    
    # 文档列表
    st.subheader("📋 文档列表")
    
    # 刷新按钮
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 刷新列表"):
            st.rerun()
    
    with col2:
        show_details = st.checkbox("显示详细信息", value=False)
    
    # 获取文档列表
    with st.spinner("📚 加载文档列表..."):
        docs_data = fetch_documents(vector_store)
    
    if docs_data["documents"]:
        st.info(f"📚 共有 {docs_data['total']} 个文档")
        
        for doc in docs_data["documents"]:
            with st.container():
                # 文档基本信息
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**📄 {doc['filename']}**")
                    if show_details:
                        st.caption(f"ID: `{doc['doc_id']}`")
                        st.caption(f"类型: {doc['file_type']} | 大小: {doc['file_size']} bytes")
                        if doc['created_time']:
                            created_time = datetime.fromtimestamp(doc['created_time']).strftime("%Y-%m-%d %H:%M")
                            st.caption(f"创建时间: {created_time}")
                
                with col2:
                    if st.button("🔍 查看", key=f"view_{doc['doc_id']}"):
                        st.session_state[f"show_detail_{doc['doc_id']}"] = True
                
                with col3:
                    if st.button("🗑️ 删除", key=f"delete_{doc['doc_id']}", type="secondary"):
                        st.session_state[f"confirm_delete_{doc['doc_id']}"] = True
                
                with col4:
                    # 文件类型图标
                    file_type = doc['file_type'].lower()
                    if file_type == '.pdf':
                        st.markdown("📕")
                    elif file_type == '.docx':
                        st.markdown("📘")
                    elif file_type in ['.txt', '.md']:
                        st.markdown("📄")
                    else:
                        st.markdown("📋")
                
                # 内容预览
                if show_details and doc.get('preview'):
                    st.text_area(
                        "内容预览",
                        value=doc['preview'],
                        height=80,
                        key=f"preview_{doc['doc_id']}",
                        disabled=True
                    )
                
                # 确认删除对话框
                if st.session_state.get(f"confirm_delete_{doc['doc_id']}", False):
                    st.warning(f"⚠️ 确认删除文档 '{doc['filename']}'？此操作不可撤销！")
                    col_yes, col_no = st.columns(2)
                    
                    with col_yes:
                        if st.button("✅ 确认删除", key=f"confirm_yes_{doc['doc_id']}", type="primary"):
                            with st.spinner("🗑️ 删除中，请稍候..."):
                                success = delete_document(vector_store, doc['doc_id'])
                                if success:
                                    # 清理相关的session state
                                    st.session_state[f"confirm_delete_{doc['doc_id']}"] = False
                                    if f"show_detail_{doc['doc_id']}" in st.session_state:
                                        del st.session_state[f"show_detail_{doc['doc_id']}"]
                                    
                                    st.success("✅ 文档删除成功")
                                    
                                    
                                    time.sleep(1)  # 让用户看到成功消息
                                    st.rerun()
                                else:
                                    st.error("❌ 文档删除失败，请稍后重试")
                                    st.session_state[f"confirm_delete_{doc['doc_id']}"] = False
                    
                    with col_no:
                        if st.button("❌ 取消", key=f"confirm_no_{doc['doc_id']}"):
                            st.session_state[f"confirm_delete_{doc['doc_id']}"] = False
                            st.rerun()
                
                # 详细信息对话框
                if st.session_state.get(f"show_detail_{doc['doc_id']}", False):
                    with st.spinner("📄 加载文档详情..."):
                        doc_detail = get_document_detail(vector_store, doc['doc_id'])
                    
                    if doc_detail:
                        st.info(f"📄 **{doc_detail['filename']}** 详细信息")
                        
                        # 基本信息
                        detail_col1, detail_col2 = st.columns(2)
                        with detail_col1:
                            st.text(f"文档ID: {doc_detail['doc_id']}")
                            st.text(f"文件类型: {doc_detail['file_type']}")
                            st.text(f"文件大小: {doc_detail['file_size']} bytes")
                        
                        with detail_col2:
                            st.text(f"文档块数: {doc_detail['chunk_count']}")
                            if doc_detail['created_time']:
                                created = datetime.fromtimestamp(doc_detail['created_time']).strftime("%Y-%m-%d %H:%M:%S")
                                st.text(f"创建时间: {created}")
                        
                        # 文档块列表
                        if doc_detail['chunks']:
                            st.markdown("**📝 文档块内容:**")
                            
                            for chunk in doc_detail['chunks']:
                                with st.expander(f"📄 块 {chunk['chunk_index']} ({chunk['chunk_length']} 字符)"):
                                    st.text_area(
                                        "内容",
                                        value=chunk['content'],
                                        height=200,
                                        key=f"chunk_{chunk['id']}",
                                        disabled=True
                                    )
                    else:
                        st.error("❌ 无法获取文档详情")
                    
                    if st.button("❌ 关闭详情", key=f"close_detail_{doc['doc_id']}"):
                        st.session_state[f"show_detail_{doc['doc_id']}"] = False
                        st.rerun()
                
                st.markdown("---")
    
    else:
        st.info("📭 暂无文档，请先上传一些文档")
    
    # 批量操作
    st.subheader("🔧 批量操作")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.empty()  # 占位符
    
    with col2:
        if st.button("📊 查看系统统计", type="secondary"):
            st.session_state["show_stats"] = True


def main():
    """主函数"""
    # 初始化系统
    if "components" not in st.session_state:
        with st.spinner("🚀 系统初始化中..."):
            st.session_state.components = initialize_system()
    
    # 初始化当前页面状态
    if "current_page" not in st.session_state:
        st.session_state.current_page = "upload"
    
    # 渲染侧边栏
    render_sidebar()
    
    # 主内容区域
    if not st.session_state.get("components"):
        st.error("❌ 系统初始化失败，请检查配置和服务状态")
        st.stop()
    
    # 使用按钮导航代替tabs，防止自动跳转
    st.markdown("### 导航")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📤 文档上传", use_container_width=True, 
                     type="primary" if st.session_state.current_page == "upload" else "secondary"):
            st.session_state.current_page = "upload"
            st.rerun()
    
    with col2:
        if st.button("🔍 智能问答", use_container_width=True, 
                     type="primary" if st.session_state.current_page == "query" else "secondary"):
            st.session_state.current_page = "query"
            st.rerun()
    
    with col3:
        if st.button("🤖 智能对话", use_container_width=True, 
                     type="primary" if st.session_state.current_page == "smart_chat" else "secondary"):
            st.session_state.current_page = "smart_chat"
            st.rerun()
    
    with col4:
        if st.button("📚 知识库管理", use_container_width=True, 
                     type="primary" if st.session_state.current_page == "knowledge" else "secondary"):
            st.session_state.current_page = "knowledge"
            st.rerun()
    
    st.markdown("---")
    
    # 根据当前页面渲染对应内容
    if st.session_state.current_page == "upload":
        render_upload_section()
    elif st.session_state.current_page == "query":
        render_query_section()
    elif st.session_state.current_page == "smart_chat":
        render_smart_conversation_section()
        handle_smart_conversation_input()
    elif st.session_state.current_page == "knowledge":
        render_knowledge_management()
    
    # 统计信息（模态框式）
    render_stats_section()
    
    # 会话管理（模态框式）
    render_session_management_modal()
    
    # 页脚
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        🤖 LLM RAG 智能问答系统 | 基于 Milvus + Kimi + SiliconFlow
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()