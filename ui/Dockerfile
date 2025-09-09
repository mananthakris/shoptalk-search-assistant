FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# copies files from /ui into /app
COPY . . 

EXPOSE 8501

# Healthcheck (optional)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD wget -q -O- http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
