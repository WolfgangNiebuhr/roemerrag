FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask einops sentence-transformers torch
COPY reranker/app.py /app/app.py
ENV RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L6-v2
RUN python -c 'from sentence_transformers import CrossEncoder; import os; CrossEncoder(os.environ["RERANK_MODEL"], trust_remote_code=True)'
COPY rag_common /rag_common
ARG RAG_BUILD_TIME
ENV RAG_BUILD_TIME=${RAG_BUILD_TIME}
EXPOSE 5000
CMD ["python", "/app/app.py"]
