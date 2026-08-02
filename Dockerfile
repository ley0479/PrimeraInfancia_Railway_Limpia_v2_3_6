FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    PORT=5000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gosu \
       libcairo2 \
       libpango-1.0-0 \
       libpangocairo-1.0-0 \
       libgdk-pixbuf-2.0-0 \
       shared-mime-info \
       fonts-dejavu-core \
       fonts-liberation \
       poppler-utils \
       tesseract-ocr \
       tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser

COPY backend/requirements-production.txt /tmp/requirements-production.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements-production.txt

COPY --chown=appuser:appuser . /app
RUN chmod 0755 /app/start_hosting.sh /app/backend/start_gunicorn.sh /app/backend/init_hosting.py

EXPOSE 5000
CMD ["./start_hosting.sh"]
