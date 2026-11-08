FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt
COPY *.py ./
RUN useradd -r -u 1001 app && mkdir -p /data/uploads && chown -R app /data
USER app
EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
