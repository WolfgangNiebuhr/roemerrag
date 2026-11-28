FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask certifi requests numpy
COPY rag/*.py /app/rag/
COPY rag_common /app/rag_common
ARG RAG_BUILD_TIME
ENV RAG_BUILD_TIME=${RAG_BUILD_TIME}
EXPOSE 5600
CMD ["python", "-m", "rag.app"]
