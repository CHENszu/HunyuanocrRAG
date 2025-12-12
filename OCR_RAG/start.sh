#!/bin/bash

# Define project directory
PROJECT_DIR="/home/ubuntu/chen/ocr_agent"
PORT=8501

# Navigate to project directory
cd "$PROJECT_DIR" || exit

# --- 1. Environment Activation ---
# Source conda
source /home/ubuntu/anaconda3/etc/profile.d/conda.sh

# Check if current environment is already vllm_identify
if [[ "$CONDA_DEFAULT_ENV" != "vllm_identify" ]]; then
    echo "Current environment is '$CONDA_DEFAULT_ENV'. Switching to 'vllm_identify'..."
    conda activate vllm_identify
else
    echo "Already in 'vllm_identify' environment."
fi

# Double check activation
if [[ "$CONDA_DEFAULT_ENV" != "vllm_identify" ]]; then
    echo "Error: Failed to activate conda environment 'vllm_identify'."
    exit 1
fi

# --- 2. Port Conflict Handling ---
echo "Checking port $PORT..."
PID=$(lsof -t -i:$PORT)

if [ -n "$PID" ]; then
    echo "Port $PORT is occupied by PID $PID. Killing it..."
    kill -9 $PID
    sleep 2 # Wait a bit for the process to die
    echo "Port $PORT released."
else
    echo "Port $PORT is free."
fi

# --- 3. Start Application ---
echo "Starting RAG Agent (FastAPI + HTML)..."
# Run FastAPI via Uvicorn module to ensure correct python env
python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT --reload

