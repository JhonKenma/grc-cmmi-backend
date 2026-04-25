#!/bin/sh
set -o errexit

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "🔄 Aplicando migraciones..."
python manage.py migrate --fake-initial
python manage.py migrate

echo "👤 Creando superusuario (si no existe)..."
python manage.py crear_superadmin --no-input

echo "📊 Cargando datos iniciales de proveedores..."
python manage.py cargar_datos_proveedores

echo "🛡️  Cargando categorías globales de riesgo..."
python manage.py seed_categorias_riesgo

echo "✅ Build completado exitosamente"