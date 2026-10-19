# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir \
        -r requirements.txt \
        "pytesseract>=0.3.13,<1.0" \
        "Pillow>=10.4,<12.0"

COPY backend/app ./app
COPY sample_data /app/sample_data

RUN groupadd --system redthread \
    && useradd --system --gid redthread --home-dir /app --shell /usr/sbin/nologin redthread \
    && mkdir -p /app/data /app/reports \
    && chown -R redthread:redthread /app

USER redthread

ENV RED_THREAD_DATA_DIR=/app/data \
    RED_THREAD_REPORTS_DIR=/app/reports

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
