import streamlit as st
import os
import sys
import glob
import streamlit.components.v1 as components

# Add current dir to sys.path to ensure backend imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.processor import DataProcessor
from backend.vector_store import VectorStore
from backend.embedding import EmbeddingClient
from backend.llm import LLMClient

st.set_page_config(page_title="RAG Agent", layout="wide")

st.title("📄 Document RAG Agent")

# Define Data Directory for Uploads
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_user_folders(base_path):
    """获取指定路径下的所有用户文件夹"""
    if not os.path.exists(base_path):
        return []
    folders = []
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path):
            # 检查文件夹中是否有支持的文件
            files = glob.glob(os.path.join(item_path, "*"))
            supported_files = [f for f in files if f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))]
            if supported_files:
                folders.append((item, len(supported_files)))
    return folders

# Sidebar for Indexing
with st.sidebar:
    st.header("管理知识库")
    
    # 选择上传模式
    upload_mode = st.radio(
        "选择数据导入方式",
        ["📂 选择服务器文件夹", "📁 浏览服务器目录", "📤 上传文件"],
        horizontal=True
    )
    
    st.divider()
    
    if upload_mode == "📂 选择服务器文件夹":
        # 模式1: 直接选择服务器上的用户文件夹
        st.subheader("选择用户文件夹")
        
        # 基础数据目录
        base_data_path = st.text_input(
            "数据根目录", 
            "/home/ubuntu/chen/ocr_agent/test/test_data",
            help="包含多个用户文件夹的根目录"
        )
        
        if os.path.exists(base_data_path):
            user_folders = get_user_folders(base_data_path)
            
            if user_folders:
                st.success(f"找到 {len(user_folders)} 个用户文件夹")
                
                # 创建选择框
                folder_options = [f"{name} ({count}个文件)" for name, count in user_folders]
                selected_folders = st.multiselect(
                    "选择要处理的用户文件夹",
                    options=folder_options,
                    default=[],
                    help="可以选择多个用户文件夹批量处理"
                )
                
                # 全选按钮
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("全选"):
                        st.session_state['selected_all'] = True
                        st.rerun()
                with col2:
                    if st.button("清空选择"):
                        st.session_state['selected_all'] = False
                        st.rerun()
                
                if 'selected_all' in st.session_state and st.session_state['selected_all']:
                    selected_folders = folder_options
                
                if selected_folders:
                    # 提取文件夹名
                    selected_names = [f.split(" (")[0] for f in selected_folders]
                    
                    st.info(f"已选择 {len(selected_names)} 个用户: {', '.join(selected_names)}")
                    
                    if st.button("🚀 开始处理选中的文件夹", type="primary"):
                        processor = DataProcessor()
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        total_folders = len(selected_names)
                        processed_files = 0
                        
                        for idx, folder_name in enumerate(selected_names):
                            folder_path = os.path.join(base_data_path, folder_name)
                            status_text.text(f"处理用户文件夹: {folder_name}...")
                            
                            try:
                                result = processor.process_directory(folder_path)
                                processed_files += 1
                            except Exception as e:
                                st.warning(f"处理 {folder_name} 时出错: {e}")
                            
                            progress_bar.progress(int((idx + 1) / total_folders * 100))
                        
                        st.success(f"✅ 完成！已处理 {processed_files}/{total_folders} 个用户文件夹")
                        st.session_state['selected_all'] = False
            else:
                st.warning("该目录下没有找到包含支持文件的文件夹")
        else:
            st.error("路径不存在")
    
    elif upload_mode == "📁 浏览服务器目录":
        # 模式2: 浏览并处理服务器上的任意目录
        st.subheader("批量处理目录")
        data_path = st.text_input("数据目录路径", "/home/ubuntu/chen/ocr_agent/test/test_data")
        
        if st.button("构建/更新索引"):
            if not os.path.exists(data_path):
                st.error("路径不存在！")
            else:
                processor = DataProcessor()
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(current, total, msg):
                    progress = int((current / total) * 100) if total > 0 else 0
                    progress_bar.progress(progress)
                    status_text.text(f"{msg} ({current}/{total})")
                
                try:
                    result = processor.process_directory(data_path, progress_callback=update_progress)
                    st.success(result)
                except Exception as e:
                    st.error(f"发生错误: {e}")
    
    else:  # 上传文件模式
        # 模式3: 上传文件（支持文件夹选择）
        st.subheader("上传文件")
        
        # 使用 HTML5 webkitdirectory 的自定义组件
        st.markdown("##### 📂 文件夹上传（推荐）")
        
        folder_upload_html = '''
        <style>
            .folder-upload-box {
                border: 2px dashed #ff4b4b;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                background-color: #fafafa;
                margin: 10px 0;
            }
            .folder-upload-box:hover {
                background-color: #fff0f0;
            }
            .folder-btn {
                background-color: #ff4b4b;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            }
            .folder-btn:hover {
                background-color: #e03e3e;
            }
            #folder-input {
                display: none;
            }
            .file-info {
                margin-top: 10px;
                font-size: 13px;
                color: #666;
            }
        </style>
        
        <div class="folder-upload-box">
            <p>📁 点击选择整个文件夹</p>
            <input type="file" id="folder-input" webkitdirectory directory multiple />
            <label for="folder-input" class="folder-btn">选择文件夹</label>
            <div id="file-info" class="file-info"></div>
        </div>
        
        <script>
            document.getElementById('folder-input').addEventListener('change', function(e) {
                const files = Array.from(e.target.files);
                const supportedExts = ['.pdf', '.png', '.jpg', '.jpeg'];
                const supported = files.filter(f => {
                    const ext = '.' + f.name.split('.').pop().toLowerCase();
                    return supportedExts.includes(ext);
                });
                
                if (files.length > 0) {
                    const folderName = files[0].webkitRelativePath.split('/')[0];
                    document.getElementById('file-info').innerHTML = 
                        '📂 文件夹: <b>' + folderName + '</b><br>' +
                        '📄 文件数: ' + supported.length + ' 个支持的文件';
                }
            });
        </script>
        '''
        
        components.html(folder_upload_html, height=150)
        
        st.caption("⚠️ 由于浏览器限制，请使用上方'选择服务器文件夹'功能处理服务器上的数据")
        
        st.markdown("---")
        st.markdown("##### 📄 传统文件上传")
        
        uploaded_files = st.file_uploader(
            "选择文件", 
            type=['pdf', 'png', 'jpg', 'jpeg'], 
            accept_multiple_files=True,
            help="选择多个文件上传"
        )
        
        if uploaded_files:
            upload_person = st.text_input(
                "用户名称", 
                value="unknown", 
                help="所有上传的文件将归类到这个用户名下"
            )
            
            if st.button("处理上传的文件"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner("处理中..."):
                    try:
                        processor = DataProcessor()
                        total_files = len(uploaded_files)
                        success_count = 0
                        
                        # 创建用户专属目录
                        user_upload_dir = os.path.join(UPLOAD_DIR, upload_person)
                        os.makedirs(user_upload_dir, exist_ok=True)
                        
                        for i, uploaded_file in enumerate(uploaded_files):
                            status_text.text(f"处理 {uploaded_file.name} ({i+1}/{total_files})...")
                            
                            # 保存到用户专属目录
                            file_path = os.path.join(user_upload_dir, uploaded_file.name)
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            if processor.process_file(file_path, person_name=upload_person):
                                success_count += 1
                            
                            progress_bar.progress(int((i + 1) / total_files * 100))
                        
                        st.success(f"✅ 成功处理 {success_count}/{total_files} 个文件，用户: {upload_person}")
                            
                    except Exception as e:
                        st.error(f"处理出错: {e}")

    st.divider()
    st.header("🔍 搜索过滤")

    # 加载元数据用于过滤
    temp_store = VectorStore()
    available_people = sorted(list(set([m.get('person', 'unknown') for m in temp_store.metadata]))) if temp_store.metadata else []
    selected_person = st.selectbox("按用户过滤", ["全部"] + available_people)

# 主聊天界面
col_header, col_clear = st.columns([6, 1])
with col_header:
    st.header("💬 智能问答")
with col_clear:
    st.write("")  # 占位
    if st.button("🗑️ 清空对话"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("请输入问题..."):
    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Rerun to update chat history display immediately
    st.rerun()

# Logic to handle response generation only if the last message is from user
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # RAG Logic
            embed_client = EmbeddingClient()
            vector_store = VectorStore()
            llm_client = LLMClient()
            
            prompt = st.session_state.messages[-1]["content"]
            
            if vector_store.index is None or vector_store.index.ntotal == 0:
                st.warning("知识库为空，请先构建索引")
                response = "暂无文档数据，请先上传并处理文件"
            else:
                # 1. Embed query
                query_embedding = embed_client.get_embedding(prompt)
                
                if query_embedding:
                    # 2. Search
                    person_filter = selected_person if selected_person != "全部" else None
                    results = vector_store.search(query_embedding, k=5, person_filter=person_filter)
                    
                    # 3. Generate Answer
                    raw_response = llm_client.get_answer(prompt, results)
                    
                    # 4. Process Thinking Block
                    # Assuming thinking is enclosed in <think>...</think>
                    import re
                    
                    def format_thinking(text):
                        # Use DOTALL for multiline match, IGNORECASE just in case
                        pattern = r"<think>(.*?)</think>"
                        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                        if match:
                            thinking_content = match.group(1).strip()
                            main_content = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE).strip()
                            
                            formatted_text = f"""<div style='color: gray; font-size: 0.9em; border-left: 3px solid #ccc; padding-left: 10px; margin-bottom: 10px;'>
                                <i>Thinking Process:</i><br>
                                {thinking_content.replace(chr(10), '<br>')}
                            </div>
                            
{main_content}"""
                            return formatted_text
                        return text

                    response = format_thinking(raw_response)
                    st.markdown(response, unsafe_allow_html=True)
                else:
                    response = "处理查询失败"
                    st.error(response)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            # Rerun to show the assistant message in the history loop
            st.rerun()
