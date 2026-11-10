FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 UPLOAD_DIR=/data/uploads
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY frontend ./frontend
RUN sh frontend/build.sh
COPY entrypoint.sh /entrypoint.sh
RUN useradd -m appuser && chmod +x /entrypoint.sh && mkdir -p /data/uploads && chown -R appuser /data /srv
EXPOSE 8000
# One worker on purpose: the importer runs inside the app and loads one file at a time.
ENTRYPOINT ["/entrypoint.sh"]
