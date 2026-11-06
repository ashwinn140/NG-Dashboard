FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 UPLOAD_DIR=/data/uploads
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
RUN useradd -m appuser && mkdir -p /data/uploads && chown -R appuser /data /srv
USER appuser
EXPOSE 8000
# One worker on purpose: the importer runs inside the app and loads one file at a time.
CMD ["sh", "-c", "uvicorn app.server:app_factory --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
