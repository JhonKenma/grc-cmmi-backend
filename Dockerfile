FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libpq-dev \
    postgresql-dev \
    bash

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.org/simple \
    --timeout=300 \
    --retries=5

COPY . .
RUN chmod +x build.sh
RUN sed -i 's/\r//' build.sh
EXPOSE 8080


# Al arrancar: corre build.sh y luego gunicorn
CMD ["sh", "-c", "./build.sh && gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 2 --timeout 120"]