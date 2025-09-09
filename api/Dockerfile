# ========= Base =========
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/root/.cache/huggingface

# System deps (curl for health checks; git for HF private repos if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /api

# -------- Optional: pin torch CPU (keeps image smaller & Cloud Run-friendly) --------
# If you use GPU elsewhere, override at build time or in a separate Dockerfile.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.3.* torchvision==0.18.* torchaudio==2.3.*

# ========= Deps layer (cacheable) =========
COPY requirements.txt .
RUN pip install -r requirements.txt

# ========= App =========
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Healthcheck (optional)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fsS http://localhost:8000/health || exit 1

# Start the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
