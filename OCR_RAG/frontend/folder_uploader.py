"""
自定义文件夹上传组件
使用 HTML5 webkitdirectory 属性实现文件夹选择功能
"""
import streamlit as st
import streamlit.components.v1 as components
import json
import base64
from io import BytesIO


def folder_uploader(key: str = "folder_uploader", height: int = 200):
    """
    创建一个文件夹上传组件
    
    返回值:
        dict: 包含 folder_name 和 files 列表
              files 列表中每个元素包含 name, path, data (base64)
    """
    
    html_code = f"""
    <style>
        .folder-upload-container {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 20px;
            border: 2px dashed #ccc;
            border-radius: 10px;
            text-align: center;
            background-color: #fafafa;
            transition: all 0.3s ease;
        }}
        .folder-upload-container:hover {{
            border-color: #ff4b4b;
            background-color: #fff5f5;
        }}
        .folder-upload-container.has-files {{
            border-color: #00c853;
            background-color: #e8f5e9;
        }}
        .upload-icon {{
            font-size: 48px;
            margin-bottom: 10px;
        }}
        .upload-label {{
            display: inline-block;
            padding: 10px 24px;
            background-color: #ff4b4b;
            color: white;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px 0;
            transition: background-color 0.3s;
        }}
        .upload-label:hover {{
            background-color: #e03e3e;
        }}
        #folder-input-{key} {{
            display: none;
        }}
        .file-list {{
            max-height: 150px;
            overflow-y: auto;
            text-align: left;
            margin-top: 15px;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }}
        .file-item {{
            padding: 5px;
            border-bottom: 1px solid #eee;
            font-size: 13px;
        }}
        .file-item:last-child {{
            border-bottom: none;
        }}
        .folder-name {{
            font-weight: bold;
            color: #1976d2;
            margin: 10px 0;
        }}
        .status-text {{
            color: #666;
            font-size: 14px;
        }}
        .send-btn {{
            display: none;
            padding: 10px 30px;
            background-color: #00c853;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 10px;
            font-size: 14px;
        }}
        .send-btn:hover {{
            background-color: #00a843;
        }}
        .send-btn.show {{
            display: inline-block;
        }}
    </style>
    
    <div class="folder-upload-container" id="container-{key}">
        <div class="upload-icon">📁</div>
        <p class="status-text" id="status-{key}">点击下方按钮选择文件夹</p>
        
        <input type="file" id="folder-input-{key}" webkitdirectory directory multiple />
        <label class="upload-label" for="folder-input-{key}">选择文件夹</label>
        
        <div class="folder-name" id="folder-name-{key}"></div>
        <div class="file-list" id="file-list-{key}" style="display: none;"></div>
        
        <button class="send-btn" id="send-btn-{key}" onclick="sendToStreamlit()">确认上传</button>
    </div>
    
    <script>
        const SUPPORTED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg'];
        let collectedFiles = [];
        let folderName = '';
        
        document.getElementById('folder-input-{key}').addEventListener('change', async function(e) {{
            const files = Array.from(e.target.files);
            const container = document.getElementById('container-{key}');
            const fileListDiv = document.getElementById('file-list-{key}');
            const folderNameDiv = document.getElementById('folder-name-{key}');
            const statusText = document.getElementById('status-{key}');
            const sendBtn = document.getElementById('send-btn-{key}');
            
            if (files.length === 0) return;
            
            // 获取文件夹名（从第一个文件的路径中提取）
            const firstPath = files[0].webkitRelativePath;
            folderName = firstPath.split('/')[0];
            
            // 过滤支持的文件类型
            const supportedFiles = files.filter(file => {{
                const ext = '.' + file.name.split('.').pop().toLowerCase();
                return SUPPORTED_EXTENSIONS.includes(ext);
            }});
            
            if (supportedFiles.length === 0) {{
                statusText.textContent = '该文件夹中没有支持的文件类型 (PDF, PNG, JPG)';
                return;
            }}
            
            container.classList.add('has-files');
            folderNameDiv.textContent = '📂 文件夹: ' + folderName;
            statusText.textContent = '正在读取文件...';
            
            // 读取文件并转换为 base64
            collectedFiles = [];
            fileListDiv.innerHTML = '';
            
            for (let i = 0; i < supportedFiles.length; i++) {{
                const file = supportedFiles[i];
                const reader = new FileReader();
                
                await new Promise((resolve) => {{
                    reader.onload = function(e) {{
                        collectedFiles.push({{
                            name: file.name,
                            path: file.webkitRelativePath,
                            data: e.target.result.split(',')[1],  // base64 部分
                            type: file.type
                        }});
                        
                        const div = document.createElement('div');
                        div.className = 'file-item';
                        div.textContent = '📄 ' + file.name;
                        fileListDiv.appendChild(div);
                        
                        statusText.textContent = `已读取 ${{i + 1}} / ${{supportedFiles.length}} 个文件`;
                        resolve();
                    }};
                    reader.readAsDataURL(file);
                }});
            }}
            
            fileListDiv.style.display = 'block';
            statusText.textContent = `已选择 ${{supportedFiles.length}} 个文件，点击确认上传`;
            sendBtn.classList.add('show');
        }});
        
        function sendToStreamlit() {{
            const data = {{
                folder_name: folderName,
                files: collectedFiles
            }};
            
            // 发送到 Streamlit
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: JSON.stringify(data)
            }}, '*');
            
            document.getElementById('status-{key}').textContent = '已提交！请点击处理按钮';
            document.getElementById('send-btn-{key}').style.display = 'none';
        }}
    </script>
    """
    
    return components.html(html_code, height=height, scrolling=True)


def parse_folder_data(data_str: str) -> dict:
    """
    解析从组件返回的数据
    
    Args:
        data_str: JSON 字符串
        
    Returns:
        dict: 包含 folder_name 和 files
    """
    if not data_str:
        return None
    
    try:
        data = json.loads(data_str)
        return data
    except:
        return None


def save_uploaded_folder(data: dict, upload_dir: str) -> tuple:
    """
    保存上传的文件夹内容到指定目录
    
    Args:
        data: 从 parse_folder_data 获取的数据
        upload_dir: 保存目录
        
    Returns:
        tuple: (folder_name, list of saved file paths)
    """
    import os
    
    if not data or 'files' not in data:
        return None, []
    
    folder_name = data.get('folder_name', 'unknown')
    files = data.get('files', [])
    
    saved_paths = []
    
    for file_info in files:
        try:
            file_name = file_info['name']
            file_data = base64.b64decode(file_info['data'])
            
            # 创建以文件夹名命名的子目录
            folder_path = os.path.join(upload_dir, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            file_path = os.path.join(folder_path, file_name)
            
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            saved_paths.append(file_path)
        except Exception as e:
            print(f"Error saving file {file_info.get('name')}: {e}")
    
    return folder_name, saved_paths
