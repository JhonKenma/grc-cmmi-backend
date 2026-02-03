#!/usr/bin/env bash
set -o errexit

echo "🔧 Instalando dependencias..."
pip install -r requirements.txt

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "🔄 Limpiando registros de migraciones de proveedores..."
python manage.py migrate --fake proveedores zero || echo "⚠️ No se pudo hacer fake zero"

echo "🗄️ Ejecutando migraciones..."
python manage.py migrate --run-syncdb

echo "👤 Creando superusuario (si no existe)..."
python manage.py crear_superadmin --no-input

echo "📊 Cargando datos iniciales de proveedores..."
python manage.py cargar_datos_proveedores

echo "✅ Build completado exitosamente"