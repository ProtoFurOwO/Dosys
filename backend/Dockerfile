FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system dosys && adduser --system --ingroup dosys dosys

# OCR local para los PDF de resultados (texto en español). El archivo nunca sale
# del servidor: Tesseract trabaja sobre las páginas renderizadas en la propia API.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Los documentos se guardan en un volumen; la carpeta nace con el usuario de la app
# para que el contenedor pueda escribir en él sin privilegios.
RUN mkdir -p /data/documents && chown -R dosys:dosys /data && chown -R dosys:dosys /app
USER dosys

EXPOSE 8000
