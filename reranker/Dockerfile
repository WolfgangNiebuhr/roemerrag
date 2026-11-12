FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask einops sentence-transformers torch
COPY app.py /app/app.py
ENV RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L6-v2
RUN python -c 'from sentence_transformers import CrossEncoder; import os; CrossEncoder(os.environ["RERANK_MODEL"], trust_remote_code=True)'
EXPOSE 5000
CMD ["python", "/app/app.py"]
