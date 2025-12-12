import os

# OCR Configuration
OCR_API_BASE = "http://localhost:8009/v1"
OCR_API_KEY = "EMPTY"
OCR_MODEL = "HunyuanOCR" 

# Embedding Configuration
# User provided: http://10.10.18.210:7288
# We assume standard OpenAI-compatible format: /v1/embeddings
EMBED_API_BASE = "http://10.10.18.210:7288/v1" 
EMBED_API_KEY = "weshare_llm"
EMBED_MODEL = "bge-m3"

# LLM Configuration
LLM_API_BASE = "http://10.10.18.210:8288/v1"
LLM_API_KEY = "weshare_llm"
LLM_MODEL = "qwq-32b"

# Data Persistence Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
INDEX_FILE = os.path.join(DATA_DIR, "faiss_index.bin")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.pkl")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
