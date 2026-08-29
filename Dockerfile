# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Warsaw

WORKDIR /srv/app

# libgl / libglib  - wymagane przez PyMuPDF do renderowania stron
# tesseract + pol  - odzyskiwanie etykiet z planow sytuacyjnych, gdzie napisy
#                    sa zamienione na krzywe wektorowe (patrz docs/project-docs/04)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq5 libglib2.0-0 libgl1 curl \
        tesseract-ocr tesseract-ocr-pol \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "300", "wsgi:app"]
