#!/usr/bin/env bash
set -o errexit

echo "🔧 Instalando dependencias..."
pip install -r requirements.txt

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "🔄 Reseteando migraciones de proveedores..."
python manage.py migrate proveedores zero --noinput || echo "⚠️ No hay migraciones previas de proveedores"

echo "🗄️ Ejecutando migraciones..."
python manage.py migrate

echo "👤 Creando superusuario (si no existe)..."
python manage.py crear_superadmin --no-input

echo "📊 Cargando datos iniciales de proveedores..."
python manage.py cargar_datos_proveedores

echo "✅ Build completado exitosamente"