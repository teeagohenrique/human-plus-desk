# syntax=docker/dockerfile:1

# Fase de runtime: Python 3.14 slim + dependências pinadas + modelo NER PT.
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Instalar dependências de produção primeiro: cache é prefixo estável.
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Modelo NER local (PT). Não está no PyPI; descompacta do GitHub (rede necessária).
RUN python -m spacy download pt_core_news_sm

# Aplicação (src/) vem depois: reconstrói rápido só quando o código muda.
COPY . .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
