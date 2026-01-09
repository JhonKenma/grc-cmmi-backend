#!/usr/bin/env bash
# build.sh - VERSIÓN FINAL

set -o errexit

echo "🔧 Instalando dependencias..."
pip install -r requirements.txt

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "🗄️ Ejecutando migraciones..."
python manage.py migrate

echo "👤 Creando superusuario (si no existe)..."
python manage.py crear_superadmin --no-input

echo "✅ Build completado exitosamente"