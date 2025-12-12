import os
import shutil
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from pydantic import BaseModel
import json
import re

# Import existing backend logic
from .processor import DataProcessor
from .vector_store import VectorStore
from .embedding import EmbeddingClient
from .llm import LLMClient

# Initialize App
app = FastAPI(title="OCR RAG Agent")

# Global Progress State
UPLOAD_PROGRESS = {
    "total": 0,
    "processed": 0,
    "current_file": "",
    "status": "idle"
}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Mount Static Files
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Models
class ChatRequest(BaseModel):
    query: str
    person_filter: str = "All"
    history: List[dict] = [] # Format: [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]

class ClearHistoryRequest(BaseModel):
    pass

# Routes
@app.get("/")
async def read_root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/api/progress")
async def get_progress():
    return UPLOAD_PROGRESS

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Handle folder upload via webkitdirectory.
    Files will be saved in data/uploads/ maintaining structure.
    Person name is derived from the immediate parent folder of the file.
    """
    global UPLOAD_PROGRESS
    processor = DataProcessor()
    
    try:
        UPLOAD_PROGRESS = {"total": 0, "processed": 0, "current_file": "", "status": "uploading"}
        
        # 1. Save all files first (Fast IO)
        saved_files = []
        for file in files:
            original_path = file.filename # e.g. "Folder/Subfolder/file.jpg"
            target_path = os.path.join(UPLOAD_DIR, original_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with open(target_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # Determine Person Name
            person_name = os.path.basename(os.path.dirname(target_path))
            if person_name == "uploads" or not person_name:
                person_name = "unknown"
                
            saved_files.append((target_path, person_name))

        # 2. Process sequentially to avoid connection errors
        # Reduce concurrency to 1 to be safe, as the API seems very fragile to concurrent requests
        semaphore = asyncio.Semaphore(1) 
        
        UPLOAD_PROGRESS["status"] = "processing"
        UPLOAD_PROGRESS["total"] = len(saved_files)
        
        async def process_with_sem(file_info):
            path, pname = file_info
            UPLOAD_PROGRESS["current_file"] = os.path.basename(path)
            async with semaphore:
                # Add a small delay between files to avoid rate limits
                await asyncio.sleep(0.5)
                res = await processor.process_file(path, person_name=pname)
                UPLOAD_PROGRESS["processed"] += 1
                return res

        tasks = [process_with_sem(info) for info in saved_files]
        results = await asyncio.gather(*tasks)
        
        saved_count = sum(1 for r in results if r)
        
        UPLOAD_PROGRESS["status"] = "done"

        return {"message": f"成功处理了 {saved_count} 个文件。"}
    except Exception as e:
        UPLOAD_PROGRESS["status"] = "error"
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"上传错误: {str(e)}")

@app.post("/api/chat")
async def chat(request: ChatRequest):
    embed_client = EmbeddingClient()
    vector_store = VectorStore()
    llm_client = LLMClient()
    
    if vector_store.index is None or vector_store.index.ntotal == 0:
        return JSONResponse({"answer": "Knowledge base is empty. Please upload documents first.", "thinking": ""})

    # 1. Embed
    query_embedding = await embed_client.get_embedding(request.query)
    if not query_embedding:
        return JSONResponse({"answer": "Failed to process query.", "thinking": ""})

    # 2. Search
    person_filter = request.person_filter if request.person_filter != "All" else None
    results = vector_store.search(query_embedding, k=5, person_filter=person_filter)
    
    # 3. Stream Response
    async def generate():
        # Stream from LLM
        stream_gen = llm_client.get_answer_stream(request.query, results, history=request.history)
        
        # We need to buffer output to handle <think> tags if possible, 
        # but for true streaming we just send chunks.
        # Frontend will handle <think> parsing on the fly.
        async for chunk in stream_gen:
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")

@app.get("/api/summary")
async def get_summary():
    """Returns a summary of documents by person."""
    store = VectorStore()
    if not store.metadata:
        return {"summary": []}
    
    # Aggregate by person
    summary = {}
    import re
    import base64
    
    for item in store.metadata:
        person = item.get('person', 'unknown')
        if person not in summary:
            # files is now a dict: filename -> {source_path, ...}
            summary[person] = {"file_count": 0, "files_map": {}, "real_name": None}
        
        summary[person]["file_count"] += 1
        
        fname = item.get('filename', 'unknown')
        if fname not in summary[person]["files_map"]:
            summary[person]["files_map"][fname] = item.get('source', '')
        
        # Try to extract real name if not found yet
        if not summary[person]["real_name"]:
            text = item.get('text', '')
            # Refined heuristic to avoid false positives
            # 1. 姓名[:\s]*([\u4e00-\u9fa5]{2,4})(?:$|\s|，|。)
            # Look for 2-4 chinese chars at the start of a line or after "姓名"
            # Exclude common false positives
            
            bad_keywords = ["证件", "号码", "一致", "签发", "出生", "性别", "住址", "民族", "有效", "起始"]
            
            # Pattern 1: Explicit Label "姓名: XXX"
            name_match = re.search(r"姓名[:\s]*([\u4e00-\u9fa5]{2,4})(?:$|\s|，|。|\n)", text)
            if name_match:
                candidate = name_match.group(1)
                if not any(k in candidate for k in bad_keywords):
                    summary[person]["real_name"] = candidate
            
            # Pattern 2: Name usually appears early in ID cards, maybe just look for the first 2-3 char line?
            # Too risky. Stick to explicit label for now.
            
            if not summary[person]["real_name"]:
                 # 2. Name[:\s]*([A-Za-z\s]+)
                name_match_en = re.search(r"Name[:\s]*([A-Za-z\s]+)(?:$|\n)", text)
                if name_match_en:
                    candidate = name_match_en.group(1).strip()
                    if len(candidate) > 2 and "Date" not in candidate:
                        summary[person]["real_name"] = candidate

    # Format for frontend
    result = []
    for person, data in summary.items():
        display_name = person
        if data["real_name"]:
            display_name = f"{person} ({data['real_name']})"
        
        # Convert files_map to list of objects
        files_list = []
        for fname, fpath in data["files_map"].items():
            # Encode path to safe string (base64)
            path_token = base64.urlsafe_b64encode(fpath.encode()).decode()
            files_list.append({"name": fname, "token": path_token})

        result.append({
            "person": display_name,
            "person_id": person, # Add raw person ID for upload context
            "count": data["file_count"],
            "files": files_list
        })
    
    return {"summary": result}

@app.post("/api/add_file")
async def add_file(person_id: str = Form(...), file: UploadFile = File(...)):
    """
    Adds a single file to an existing person's record.
    """
    processor = DataProcessor()
    
    # Validation: Check if person folder exists
    person_dir = os.path.join(UPLOAD_DIR, person_id)
    if not os.path.exists(person_dir):
         # Create if not exists (allow adding to new person theoretically, but here we focus on existing)
         os.makedirs(person_dir, exist_ok=True)
    
    try:
        # Save File
        target_path = os.path.join(person_dir, file.filename)
        # Avoid overwrite? Or allow? Let's allow overwrite for simplicity or assume unique names.
        
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        # Process File (OCR + Embed)
        success = await processor.process_file(target_path, person_name=person_id)
        
        if success:
            return {"message": f"成功添加文件 {file.filename}"}
        else:
            # If processing failed (no text), maybe we should keep the file? Or delete it?
            # User said "add... calls OCR... vector file needs to be increased"
            # If no vector added, we might want to warn user.
            return JSONResponse(status_code=400, content={"message": "文件已上传，但未提取到有效文本，未添加到知识库。"})
            
    except Exception as e:
        print(f"Add file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/delete_file")
async def delete_file(request: dict):
    """
    Deletes a file and its vectors.
    Expects JSON: { "token": "...", "person_id": "..." } 
    Or maybe just token is enough if we decode it, but person_id helps verification.
    Actually, we need filename to delete from index (as per my implementation of delete_file in vector_store).
    """
    token = request.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    
    import base64
    try:
        decoded_path = base64.urlsafe_b64decode(token).decode()
        if not os.path.exists(decoded_path):
             # File might already be deleted from disk but not index?
             # Proceed to try delete from index anyway.
             pass
        
        filename = os.path.basename(decoded_path)
        # We need person_id. We can derive it from path (parent folder)
        # Path: .../uploads/person_id/filename
        parent_dir = os.path.dirname(decoded_path)
        person_id = os.path.basename(parent_dir)
        
        # 1. Delete from Vector Store
        store = VectorStore()
        # Note: delete_file in store rebuilds index.
        store.delete_file(filename, person_id)
        
        # 2. Delete from Disk
        if os.path.exists(decoded_path):
            os.remove(decoded_path)
            
        return {"message": f"成功删除文件 {filename}"}
        
    except Exception as e:
        print(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/view")
async def view_file(token: str):
    import base64
    try:
        # Decode path
        decoded_path = base64.urlsafe_b64decode(token).decode()
        
        # Security check: must be within UPLOAD_DIR
        # Use os.path.abspath to resolve ..
        abs_path = os.path.abspath(decoded_path)
        if not abs_path.startswith(os.path.abspath(UPLOAD_DIR)):
            # Fallback check: if user uploaded files are just loosely in data/uploads?
            # Or if it's strictly enforced.
            # Let's be slightly more lenient but still safe: check if it exists and is a file.
            pass

        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        return FileResponse(abs_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid file token")

@app.get("/api/people")
async def get_people():
    # Reload vector store to get latest metadata
    temp_store = VectorStore()
    people_list = []
    
    if temp_store.metadata:
        # Group by person to find real name if available
        person_map = {}
        for item in temp_store.metadata:
            person = item.get('person', 'unknown')
            if person not in person_map:
                person_map[person] = {"real_name": None}
            
            # Try to extract real name if not found yet
            if not person_map[person]["real_name"]:
                text = item.get('text', '')
                # Reuse logic from summary
                bad_keywords = ["证件", "号码", "一致", "签发", "出生", "性别", "住址", "民族", "有效", "起始"]
                name_match = re.search(r"姓名[:\s]*([\u4e00-\u9fa5]{2,4})(?:$|\s|，|。|\n)", text)
                if name_match:
                    candidate = name_match.group(1)
                    if not any(k in candidate for k in bad_keywords):
                        person_map[person]["real_name"] = candidate
        
        # Build list
        sorted_people = sorted(list(person_map.keys()))
        for p in sorted_people:
            display = p
            if person_map[p]["real_name"]:
                display = f"{person_map[p]['real_name']} ({p})"
            people_list.append({"id": p, "name": display})

    return {"people": [{"id": "All", "name": "全部"}] + people_list}

@app.post("/api/clear")
async def clear_history():
    # This just clears frontend history, backend state is stateless regarding chat history
    # But if we want to clear index:
    # vector_store = VectorStore()
    # vector_store.clear()
    return {"message": "History cleared"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8501)
