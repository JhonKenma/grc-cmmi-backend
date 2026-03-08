from rest_framework import viewsets, filters, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from apps.empresas.models import Empresa

# --- MODELOS ---
from .models import Documento, Proceso, Norma, TipoDocumento

# --- SERIALIZERS ---
from .serializers import (
    DocumentoSerializer,
    ProcesoSerializer,
    NormaSerializer,
    TipoDocumentoSerializer
)

# =============================================================================
# FILTRO PERSONALIZADO
# =============================================================================
class DocumentoFilter(django_filters.FilterSet):
    tipo_nombre = django_filters.CharFilter(field_name='tipo__nombre', lookup_expr='iexact')
    proceso_nombre = django_filters.CharFilter(field_name='proceso__nombre', lookup_expr='iexact')
    estado = django_filters.CharFilter(field_name='estado', lookup_expr='iexact')
    vencimiento_mayor_a = django_filters.NumberFilter(method='filter_vencimiento_mayor_a')
    vencimiento_rango = django_filters.CharFilter(method='filter_vencimiento_rango')

    class Meta:
        model = Documento
        fields = ['estado', 'norma']

    def filter_vencimiento_mayor_a(self, queryset, name, value):
        hoy = timezone.now().date()
        fecha_limite = hoy + timedelta(days=int(value))
        return queryset.filter(estado='vigente', fecha_proxima_revision__gt=fecha_limite)

    def filter_vencimiento_rango(self, queryset, name, value):
        hoy = timezone.now().date()
        label = value.lower()
        if "vencido" in label:
            return queryset.filter(estado='vigente', fecha_proxima_revision__lt=hoy)
        elif "30" in label:
            return queryset.filter(estado='vigente', fecha_proxima_revision__range=[hoy, hoy + timedelta(days=30)])
        elif "60" in label:
            return queryset.filter(estado='vigente', fecha_proxima_revision__range=[hoy + timedelta(days=31), hoy + timedelta(days=60)])
        elif "90" in label:
            return queryset.filter(estado='vigente', fecha_proxima_revision__range=[hoy + timedelta(days=61), hoy + timedelta(days=90)])
        elif "120" in label:
            return queryset.filter(estado='vigente', fecha_proxima_revision__range=[hoy + timedelta(days=91), hoy + timedelta(days=120)])
        return queryset

# =============================================================================
# VISTAS DE CATÁLOGOS
# =============================================================================

class IsSameEmpresaOrSuperadmin(BasePermission):
    """Permite acceso por objeto solo dentro de la empresa del usuario."""

    def has_object_permission(self, request, view, obj):
        if view.is_superadmin(request.user):
            return True

        user_empresa = getattr(request.user, 'empresa', None)
        return bool(user_empresa and obj.empresa_id == user_empresa.id)


class MultiEmpresaCatalogViewSet(viewsets.ModelViewSet):
    """Base para catálogos multiempresa con override de empresa seguro."""

    permission_classes = [IsAuthenticated, IsSameEmpresaOrSuperadmin]

    def is_superadmin(self, user):
        return bool(
            getattr(user, 'is_superuser', False)
            or getattr(user, 'es_superadmin', False)
            or getattr(user, 'rol', None) == 'superadmin'
        )

    def get_user_empresa_or_error(self):
        empresa = getattr(self.request.user, 'empresa', None)
        if not empresa:
            raise PermissionDenied('Usuario sin empresa asignada. Contacte al superadministrador.')
        return empresa

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if self.is_superadmin(user):
            empresa_id = self.request.query_params.get('empresa_id')
            if empresa_id:
                queryset = queryset.filter(empresa_id=empresa_id)
            return queryset

        empresa = self.get_user_empresa_or_error()
        return queryset.filter(empresa=empresa)

    def resolve_superadmin_empresa(self, current_empresa=None):
        empresa_id = self.request.data.get('empresa_id')
        if empresa_id is None:
            empresa_id = self.request.data.get('empresa')

        if empresa_id in (None, ''):
            return current_empresa

        try:
            return Empresa.objects.get(pk=empresa_id)
        except Empresa.DoesNotExist:
            raise ValidationError({'empresa_id': 'La empresa indicada no existe.'})

    def perform_create(self, serializer):
        user = self.request.user
        if self.is_superadmin(user):
            empresa = self.resolve_superadmin_empresa(current_empresa=None)
        else:
            empresa = self.get_user_empresa_or_error()

        serializer.save(empresa=empresa)

    def perform_update(self, serializer):
        user = self.request.user
        if self.is_superadmin(user):
            empresa = self.resolve_superadmin_empresa(current_empresa=serializer.instance.empresa)
        else:
            empresa = self.get_user_empresa_or_error()

        serializer.save(empresa=empresa)

class TipoDocumentoViewSet(MultiEmpresaCatalogViewSet):
    queryset = TipoDocumento.objects.all()
    serializer_class = TipoDocumentoSerializer
    pagination_class = None


class ProcesoViewSet(MultiEmpresaCatalogViewSet):
    queryset = Proceso.objects.all().order_by('nombre')
    serializer_class = ProcesoSerializer
    pagination_class = None


class NormaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Norma.objects.all().order_by('nombre')
    serializer_class = NormaSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

# =============================================================================
# VIEWSET PRINCIPAL
# =============================================================================

class DocumentoViewSet(viewsets.ModelViewSet):
    queryset = Documento.objects.all()
    serializer_class = DocumentoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DocumentoFilter
    search_fields = ['codigo', 'titulo', 'objetivo']
    ordering = ['-fecha_creacion']

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if hasattr(user, 'empresa') and user.empresa:
            queryset = queryset.filter(empresa=user.empresa)

        if not user.is_staff:
            queryset = queryset.filter(
                Q(estado='vigente') |
                Q(elaborado_por=user) |
                Q(revisado_por=user) |
                Q(aprobado_por=user) |
                Q(nivel_confidencialidad='publico')
            ).distinct()

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        empresa = getattr(user, 'empresa', None)
        serializer.save(
            elaborado_por=user,
            empresa=empresa
        )

    # =======================================================
    # ACCIÓN: ESTADÍSTICAS DASHBOARD SGI (CORREGIDA)
    # =======================================================
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        user = self.request.user
        hoy = timezone.now().date()

        qs = Documento.objects.filter(activo=True)
        if hasattr(user, 'empresa') and user.empresa:
            qs = qs.filter(empresa=user.empresa)

        total_docs = qs.count()

        # 1. Conteos por estado
        vigentes = qs.filter(estado='vigente').count()
        borradores = qs.filter(estado='borrador').count()
        en_revision = qs.filter(estado='en_revision').count()
        obsoletos = qs.filter(estado='obsoleto').count()
        sin_archivo = qs.filter(archivo_editable__isnull=True).count()

        # 2. Base para vencimientos
        docs_vigentes = qs.filter(estado='vigente', fecha_proxima_revision__isnull=False)

        vencidos_qs = docs_vigentes.filter(fecha_proxima_revision__lt=hoy)
        critico_qs = docs_vigentes.filter(fecha_proxima_revision__range=[hoy, hoy + timedelta(days=30)])
        alerta_qs = docs_vigentes.filter(fecha_proxima_revision__range=[hoy + timedelta(days=31), hoy + timedelta(days=60)])
        preventivo90_qs = docs_vigentes.filter(fecha_proxima_revision__range=[hoy + timedelta(days=61), hoy + timedelta(days=90)])
        preventivo120_qs = docs_vigentes.filter(fecha_proxima_revision__range=[hoy + timedelta(days=91), hoy + timedelta(days=120)])

        salud_sistema = round((vigentes / total_docs) * 100, 1) if total_docs else 0
        riesgo_critico = vencidos_qs.count() + critico_qs.count()
        cuello_botella = borradores + en_revision
        calidad_archivos = round(((total_docs - sin_archivo) / total_docs) * 100, 1) if total_docs else 0

        def to_doc_resumen(qs_docs):
            return [
                {
                    "id": str(doc.id),
                    "codigo": doc.codigo,
                    "nombre": doc.titulo,
                    "proceso": doc.proceso.nombre if doc.proceso else "Sin proceso",
                    "responsable": doc.elaborado_por.get_full_name() if doc.elaborado_por else "No asignado",
                    "fecha_vencimiento": doc.fecha_proxima_revision.isoformat() if doc.fecha_proxima_revision else None
                }
                for doc in qs_docs[:20]
            ]

        vencimientos_detalle = {
            "vencidos": vencidos_qs.count(),
            "critico_30d": critico_qs.count(),
            "alerta_60d": alerta_qs.count(),
            "preventivo_90d": preventivo90_qs.count(),
            "preventivo_120d": preventivo120_qs.count(),
            "documentos_vencidos": to_doc_resumen(vencidos_qs),
            "documentos_critico_30d": to_doc_resumen(critico_qs),
            "documentos_alerta_60d": to_doc_resumen(alerta_qs),
            "documentos_preventivo_90d": to_doc_resumen(preventivo90_qs),
            "documentos_preventivo_120d": to_doc_resumen(preventivo120_qs),
        }

        # 3. Agrupaciones
        por_proceso = qs.values('proceso__nombre', 'proceso__sigla').annotate(
            cantidad=Count('id')
        ).exclude(proceso__nombre__isnull=True).order_by('-cantidad')

        por_estado = qs.values('estado').annotate(cantidad=Count('id'))

        por_alcance = qs.values('alcance').annotate(cantidad=Count('id')).exclude(alcance='')

        # NUEVO: Por tipo de documento
        por_tipo = qs.values('tipo__nombre').annotate(
            cantidad=Count('id')
        ).exclude(tipo__nombre__isnull=True).order_by('-cantidad')

        # Por nivel jerárquico
        por_nivel = qs.values('tipo__nivel_jerarquico').annotate(
            cantidad=Count('id')
        ).exclude(tipo__nivel_jerarquico__isnull=True).order_by('tipo__nivel_jerarquico')

        niveles_map = {
            1: "Nivel 1 (Estratégico)",
            2: "Nivel 2 (Táctico)",
            3: "Nivel 3 (Operativo)",
            4: "Nivel 4 (Procedimientos)",
            5: "Nivel 5 (Registros)",
        }

        por_nivel_list = [
            {"nivel": niveles_map.get(item['tipo__nivel_jerarquico'], f"Nivel {item['tipo__nivel_jerarquico']}"),
             "cantidad": item['cantidad']}
            for item in por_nivel
        ]

        # Por norma
        por_norma = qs.values('norma__nombre').annotate(
            cantidad=Count('id')
        ).exclude(norma__nombre__isnull=True).order_by('-cantidad')

        por_norma_list = [
            {
                "norma": item['norma__nombre'],
                "cantidad": item['cantidad'],
                "color": None
            }
            for item in por_norma
        ]

        # Políticas globales
        total_politicas = qs.filter(tipo__nivel_jerarquico=1).count()

        return Response({
            "total_documentos": total_docs,
            "total_politicas": total_politicas,
            "vigentes": vigentes,
            "borradores": borradores,
            "en_revision": en_revision,
            "obsoletos": obsoletos,
            "sin_archivo": sin_archivo,
            "salud_sistema": salud_sistema,
            "riesgo_critico": riesgo_critico,
            "cuello_botella": cuello_botella,
            "calidad_archivos": calidad_archivos,
            "vencimientos": vencimientos_detalle,
            "por_proceso": list(por_proceso),
            "por_estado": list(por_estado),
            "por_alcance": list(por_alcance),
            "por_nivel": por_nivel_list,
            "por_norma": por_norma_list,
            "por_tipo": list(por_tipo),   # <-- NUEVO CAMPO AGREGADO
        })

    # =======================================================
    # ACCIÓN: SUGERIR CÓDIGO
    # =======================================================
    @action(detail=False, methods=['get'])
    def sugerir_codigo(self, request):
        tipo_id = request.query_params.get('tipo_id')
        proceso_id = request.query_params.get('proceso_id')

        if not tipo_id:
            return Response({'error': 'Falta seleccionar el Tipo de Documento'}, status=400)

        try:
            tipo = TipoDocumento.objects.get(id=tipo_id)
            abreviatura = tipo.abreviatura.upper() if tipo.abreviatura else "DOC"

            sigla_proceso = "GEN"
            if proceso_id:
                try:
                    proceso = Proceso.objects.get(id=proceso_id)
                    if proceso.sigla:
                        sigla_proceso = proceso.sigla.upper()
                except Proceso.DoesNotExist:
                    pass

            prefijo = f"{abreviatura}-{sigla_proceso}-"

            filtros = {'codigo__startswith': prefijo}
            if hasattr(request.user, 'empresa') and request.user.empresa:
                filtros['empresa'] = request.user.empresa

            ultimo_doc = Documento.objects.filter(**filtros).order_by('-codigo').first()

            if ultimo_doc:
                try:
                    partes = ultimo_doc.codigo.split('-')
                    if partes[-1].isdigit():
                        consecutivo = int(partes[-1]) + 1
                    else:
                        consecutivo = 1
                except (IndexError, ValueError):
                    consecutivo = 1
            else:
                consecutivo = 1

            codigo_sugerido = f"{prefijo}{str(consecutivo).zfill(3)}"

            return Response({'codigo_sugerido': codigo_sugerido})

        except TipoDocumento.DoesNotExist:
            return Response({'error': 'Tipo de documento no encontrado'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)