FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libpq-dev \
    postgresql-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# collectstatic se ejecuta aquí, cuando YA existen las variables de entorno
CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 2 --timeout 120"]