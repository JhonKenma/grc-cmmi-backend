# ShieldGrid365 Backend - Instrucciones para GitHub Copilot

Backend del sistema GRC construido con **Django 5.2 + Django REST Framework + PostgreSQL**.

---

## Stack Tecnológico

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.12 | Runtime |
| Django | 5.2 | Web Framework |
| DRF | 3.14 | API REST |
| PostgreSQL | 16 | Base de datos |
| SimpleJWT | 5.3 | Autenticación |
| Celery | 5.4 | Tareas async |
| Supabase | - | Storage de archivos |

---

## Arquitectura de Apps

```
apps/
├── core/           # Modelos base, permisos, utilidades
├── usuarios/       # Autenticación y gestión de usuarios
├── empresas/       # Multi-tenancy
├── encuestas/      # Evaluaciones CMMI tradicionales
├── evaluaciones/   # Frameworks inteligentes (ISO 27001, etc.)
├── asignaciones/   # Asignación de evaluaciones
├── respuestas/     # Respuestas y evidencias
├── notificaciones/ # Sistema de notificaciones
├── reportes/       # Generación de reportes
├── proveedores/    # Gestión de proveedores GRC
├── documentos/     # Gestión documental SGI
└── proyectos_remediacion/  # Proyectos de cierre de brecha
```

---

## Reglas de Código - OBLIGATORIAS

### 1. Modelos - Heredar de BaseModel

**SIEMPRE heredar de `BaseModel` para timestamps y soft delete:**

```python
# ✅ CORRECTO
from apps.core.models import BaseModel

class Evaluacion(BaseModel):
    """Modelo de evaluación de madurez."""

    nombre = models.CharField(max_length=200)
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='evaluaciones',
    )
    fecha_limite = models.DateField()

    class Meta:
        db_table = 'evaluaciones'
        verbose_name = 'Evaluación'
        verbose_name_plural = 'Evaluaciones'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.nombre} - {self.empresa.nombre}"


# ❌ INCORRECTO - No heredar de BaseModel
class Evaluacion(models.Model):
    nombre = models.CharField(max_length=200)
    # Falta created_at, updated_at, is_active...
```

**BaseModel proporciona:**
```python
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)  # Soft delete

    class Meta:
        abstract = True
```

### 2. Type Hints - Python 3.12

**SIEMPRE usar type hints completos:**

```python
# ✅ CORRECTO
from typing import Any

from django.db.models import QuerySet
from rest_framework.request import Request
from rest_framework.response import Response

from apps.usuarios.models import Usuario
from apps.empresas.models import Empresa


def get_usuarios_by_empresa(empresa_id: int) -> QuerySet[Usuario]:
    """Obtiene todos los usuarios activos de una empresa."""
    return Usuario.objects.filter(
        empresa_id=empresa_id,
        is_active=True,
    ).select_related('empresa')


def calculate_gap(
    nivel_actual: int,
    nivel_deseado: int,
) -> dict[str, int | str]:
    """Calcula la brecha entre niveles."""
    gap = nivel_deseado - nivel_actual
    clasificacion = _get_clasificacion_gap(gap)
    return {
        'gap': gap,
        'clasificacion': clasificacion,
    }


# ❌ INCORRECTO - Sin type hints
def get_usuarios_by_empresa(empresa_id):
    return Usuario.objects.filter(empresa_id=empresa_id)
```

### 3. ViewSets y Serializers - Patrón DRF

**SIEMPRE usar ViewSets con serializers separados:**

```python
# ✅ CORRECTO - views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.permissions import IsAdmin, IsAuditor
from apps.evaluaciones.models import Evaluacion
from apps.evaluaciones.serializers import (
    EvaluacionSerializer,
    EvaluacionCreateSerializer,
    EvaluacionDetailSerializer,
)


class EvaluacionViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de evaluaciones."""

    queryset = Evaluacion.objects.filter(is_active=True)
    permission_classes = [IsAdmin | IsAuditor]

    def get_serializer_class(self):
        if self.action == 'create':
            return EvaluacionCreateSerializer
        if self.action == 'retrieve':
            return EvaluacionDetailSerializer
        return EvaluacionSerializer

    def get_queryset(self) -> QuerySet[Evaluacion]:
        """Filtra por empresa del usuario."""
        user = self.request.user
        queryset = super().get_queryset()

        if user.rol != 'superadmin':
            queryset = queryset.filter(empresa=user.empresa)

        return queryset.select_related('empresa').prefetch_related('dimensiones')

    @action(detail=True, methods=['post'])
    def duplicar(self, request: Request, pk: int = None) -> Response:
        """Duplica una evaluación existente."""
        evaluacion = self.get_object()
        nueva = evaluacion.duplicar()
        serializer = self.get_serializer(nueva)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

```python
# ✅ CORRECTO - serializers.py
from rest_framework import serializers

from apps.evaluaciones.models import Evaluacion, Dimension


class DimensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dimension
        fields = ['id', 'nombre', 'orden', 'peso']


class EvaluacionSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)

    class Meta:
        model = Evaluacion
        fields = [
            'id', 'nombre', 'descripcion', 'empresa', 'empresa_nombre',
            'fecha_inicio', 'fecha_limite', 'estado', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class EvaluacionDetailSerializer(EvaluacionSerializer):
    dimensiones = DimensionSerializer(many=True, read_only=True)

    class Meta(EvaluacionSerializer.Meta):
        fields = EvaluacionSerializer.Meta.fields + ['dimensiones']
```

### 4. Evitar N+1 - select_related y prefetch_related

**SIEMPRE optimizar queries:**

```python
# ✅ CORRECTO - Optimizado
def get_queryset(self) -> QuerySet[Asignacion]:
    return Asignacion.objects.filter(
        is_active=True
    ).select_related(
        'usuario',           # ForeignKey
        'empresa',           # ForeignKey
        'evaluacion',        # ForeignKey
    ).prefetch_related(
        'respuestas',        # Reverse ForeignKey (many)
        'respuestas__evidencias',  # Nested prefetch
    )


# ❌ INCORRECTO - Causa N+1
def get_queryset(self):
    asignaciones = Asignacion.objects.all()
    for a in asignaciones:
        print(a.usuario.email)  # Query por cada iteración!
        print(a.empresa.nombre) # Otra query!
    return asignaciones
```

**Cuándo usar cada uno:**
- `select_related`: ForeignKey y OneToOne (JOIN en SQL)
- `prefetch_related`: ManyToMany y reverse ForeignKey (query separada)

### 5. Permisos Personalizados

**SIEMPRE usar permisos de apps/core/permissions.py:**

```python
# ✅ CORRECTO
from apps.core.permissions import IsAdmin, IsSuperAdmin, IsAuditor, IsOwnerOrAdmin

class EvaluacionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]  # Solo administradores

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAdmin() | IsAuditor()]  # Admin o Auditor
        if self.action == 'destroy':
            return [IsSuperAdmin()]  # Solo SuperAdmin
        return super().get_permissions()


# Definición de permisos (apps/core/permissions.py)
from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """Permite acceso a administradores y superadmin."""

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated and
            request.user.rol in ['administrador', 'superadmin']
        )


class IsAuditor(BasePermission):
    """Permite acceso a auditores."""

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated and
            request.user.rol == 'auditor'
        )


class IsOwnerOrAdmin(BasePermission):
    """Permite acceso al propietario del recurso o admin."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.rol in ['administrador', 'superadmin']:
            return True
        return obj.usuario == request.user


# ❌ INCORRECTO - Permisos inline sin reutilización
class MyView(APIView):
    def get(self, request):
        if request.user.rol != 'admin':  # Lógica suelta
            return Response(status=403)
```

### 6. Servicios para Lógica Compleja

**Extraer lógica de negocio a servicios:**

```python
# ✅ CORRECTO - apps/evaluaciones/services.py
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.evaluaciones.models import Evaluacion, Dimension
from apps.respuestas.models import CalculoNivel
from apps.notificaciones.services import NotificacionService


class EvaluacionService:
    """Servicio para lógica de negocio de evaluaciones."""

    def __init__(self, evaluacion: Evaluacion):
        self.evaluacion = evaluacion

    @transaction.atomic
    def calcular_resultados(self) -> dict[str, Any]:
        """Calcula los resultados finales de la evaluación."""
        resultados = []

        for dimension in self.evaluacion.dimensiones.all():
            calculo = self._calcular_dimension(dimension)
            resultados.append(calculo)

        # Guardar cálculos
        CalculoNivel.objects.bulk_create(
            [CalculoNivel(**r) for r in resultados]
        )

        # Notificar
        NotificacionService.enviar_evaluacion_completada(
            self.evaluacion
        )

        return {
            'evaluacion_id': self.evaluacion.id,
            'resultados': resultados,
            'fecha_calculo': timezone.now().isoformat(),
        }

    def _calcular_dimension(self, dimension: Dimension) -> dict:
        """Calcula el nivel de una dimensión."""
        respuestas = dimension.respuestas.filter(estado='auditado')
        # ... lógica de cálculo
        return {...}


# Uso en ViewSet
class EvaluacionViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def calcular(self, request, pk=None):
        evaluacion = self.get_object()
        service = EvaluacionService(evaluacion)
        resultado = service.calcular_resultados()
        return Response(resultado)
```

### 7. Migraciones

```python
# ✅ CORRECTO - Migración con operaciones seguras
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('evaluaciones', '0001_initial'),
    ]

    operations = [
        # Agregar campo nullable primero
        migrations.AddField(
            model_name='evaluacion',
            name='nuevo_campo',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
        # Luego en otra migración: llenar datos y quitar null
    ]


# ❌ INCORRECTO - Campo NOT NULL sin default
migrations.AddField(
    model_name='evaluacion',
    name='nuevo_campo',
    field=models.CharField(max_length=100),  # Fallará con datos existentes
)
```

---

## Patrones Prohibidos

```python
# ❌ NUNCA queries en loops
for user in users:
    empresas = user.empresa.all()  # N+1!

# ❌ NUNCA lógica de negocio en serializers
class MySerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        # 100 líneas de lógica aquí... MAL
        # Usar un Service

# ❌ NUNCA hardcodear IDs
Empresa.objects.get(id=1)  # Magic number
Empresa.objects.get(nombre='Default')  # Mejor, pero usar settings

# ❌ NUNCA ignorar transacciones para operaciones múltiples
def crear_evaluacion_completa(data):
    evaluacion = Evaluacion.objects.create(...)
    for dim in data['dimensiones']:
        Dimension.objects.create(...)  # Si falla, queda inconsistente!
    # Usar @transaction.atomic

# ❌ NUNCA exponer campos sensibles en serializers
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'  # Expone password!
```

---

## Estructura de URLs

```python
# apps/evaluaciones/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.evaluaciones.views import EvaluacionViewSet, DimensionViewSet

router = DefaultRouter()
router.register(r'evaluaciones', EvaluacionViewSet, basename='evaluacion')
router.register(r'dimensiones', DimensionViewSet, basename='dimension')

urlpatterns = [
    path('', include(router.urls)),
]
```

---

## Testing

```python
# tests/test_evaluaciones.py
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.usuarios.models import Usuario
from apps.evaluaciones.models import Evaluacion


@pytest.fixture
def admin_client(db) -> APIClient:
    """Cliente autenticado como administrador."""
    user = Usuario.objects.create_user(
        email='admin@test.com',
        password='testpass123',
        rol='administrador',
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestEvaluacionAPI:

    def test_listar_evaluaciones_requiere_autenticacion(self):
        """Verifica que el endpoint requiere autenticación."""
        client = APIClient()
        response = client.get('/api/evaluaciones/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_admin_puede_crear_evaluacion(self, admin_client):
        """Verifica que un admin puede crear evaluaciones."""
        data = {
            'nombre': 'Evaluación Test',
            'descripcion': 'Descripción de prueba',
        }
        response = admin_client.post('/api/evaluaciones/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['nombre'] == 'Evaluación Test'
```
