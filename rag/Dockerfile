FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask certifi requests numpy
COPY rag/app.py /app/app.py
COPY rag/embedding_config.py /app/embedding_config.py
COPY rag/ollama_endpoint.py /app/ollama_endpoint.py
COPY rag_common /rag_common
ARG RAG_BUILD_TIME
ENV RAG_BUILD_TIME=${RAG_BUILD_TIME}
EXPOSE 5600
CMD ["python", "/app/app.py"]
