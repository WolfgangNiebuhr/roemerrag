FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask certifi requests numpy
COPY app.py /app/app.py
COPY embedding_config.py /app/embedding_config.py
COPY ollama_endpoint.py /app/ollama_endpoint.py
EXPOSE 5600
CMD ["python", "/app/app.py"]
