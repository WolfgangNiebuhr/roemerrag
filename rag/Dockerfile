FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask certifi requests numpy
COPY app.py /app/app.py
EXPOSE 5600
CMD ["python", "/app/app.py"]
