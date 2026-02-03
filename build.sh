#!/usr/bin/env bash
set -o errexit

echo "🔧 Instalando dependencias..."
pip install -r requirements.txt

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "🔄 Sincronizando estado de todas las migraciones..."
python manage.py migrate --fake-initial

echo "🗄️ Ejecutando migraciones nuevas..."
python manage.py migrate

echo "👤 Creando superusuario (si no existe)..."
python manage.py crear_superadmin --no-input

echo "📊 Cargando datos iniciales de proveedores..."
python manage.py cargar_datos_proveedores

echo "✅ Build completado exitosamente"