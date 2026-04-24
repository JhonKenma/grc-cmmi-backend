# apps/dashboard/services/usuario.py
"""
Servicio de dashboard para roles Usuario / Analista de Riesgos.
Visión personal: mis asignaciones de encuesta y mis evaluaciones IQ.
"""

from django.utils import timezone
from django.db.models import Count

from apps.asignaciones.models import Asignacion
from apps.asignaciones_iq.models import AsignacionEvaluacionIQ


class UsuarioDashboardService:

    def __init__(self, user):
        self.user = user
        self.empresa = user.empresa

    def get_summary(self) -> dict:
        return {
            "kpis": self._get_kpis(),
            "alertas": self._get_alertas(),
            "charts": self._get_charts(),
        }

    # ------------------------------------------------------------------ KPIs
    def _get_kpis(self) -> dict:
        ahora = timezone.now()

        # Asignaciones de encuesta del usuario
        asig_qs = Asignacion.objects.filter(
            usuario_asignado=self.user, activo=True
        )
        asig_pendientes = asig_qs.filter(estado="pendiente").count()
        asig_en_progreso = asig_qs.filter(estado="en_progreso").count()
        asig_completadas = asig_qs.filter(
            estado__in=["completado", "pendiente_auditoria", "auditado"]
        ).count()
        asig_vencidas = asig_qs.filter(estado="vencido").count()

        # Próxima asignación de encuesta que vence
        proxima_asig = (
            asig_qs.filter(
                estado__in=["pendiente", "en_progreso"],
                fecha_limite__gte=ahora.date(),
            )
            .order_by("fecha_limite")
            .values("id", "fecha_limite", "dimension__nombre")
            .first()
        )

        # Evaluaciones IQ del usuario
        iq_qs = AsignacionEvaluacionIQ.objects.filter(
            usuario_asignado=self.user, activo=True
        )
        iq_pendientes = iq_qs.filter(estado__in=["pendiente", "en_progreso"]).count()
        iq_completadas = iq_qs.filter(
            estado__in=["completada", "auditada", "aprobada"]
        ).count()
        iq_vencidas = iq_qs.filter(estado="vencida").count()

        # Próxima IQ que vence
        proxima_iq = (
            iq_qs.filter(
                estado__in=["pendiente", "en_progreso"],
                fecha_limite__gte=ahora.date(),
            )
            .order_by("fecha_limite")
            .values("id", "fecha_limite", "evaluacion__nombre")
            .first()
        )

        return {
            "asignaciones_encuesta": {
                "pendientes": asig_pendientes,
                "en_progreso": asig_en_progreso,
                "completadas": asig_completadas,
                "vencidas": asig_vencidas,
                "proxima_vencimiento": proxima_asig,
            },
            "evaluaciones_iq": {
                "pendientes": iq_pendientes,
                "completadas": iq_completadas,
                "vencidas": iq_vencidas,
                "proxima_vencimiento": proxima_iq,
            },
        }

    # --------------------------------------------------------------- Alertas
    def _get_alertas(self) -> list:
        ahora = timezone.now()
        alertas = []

        # Asignaciones vencidas
        asig_vencidas = Asignacion.objects.filter(
            usuario_asignado=self.user,
            estado="vencido",
            activo=True,
        ).select_related("dimension")[:5]
        for asig in asig_vencidas:
            alertas.append({
                "tipo": "asignacion_vencida",
                "nivel": "critico",
                "mensaje": (
                    f"Tu asignación '{asig.dimension.nombre if asig.dimension else 'evaluación completa'}' "
                    f"está vencida"
                ),
                "asignacion_id": str(asig.id),
            })

        # IQ vencidas
        iq_vencidas = AsignacionEvaluacionIQ.objects.filter(
            usuario_asignado=self.user,
            estado="vencida",
            activo=True,
        ).select_related("evaluacion")[:5]
        for iq in iq_vencidas:
            alertas.append({
                "tipo": "iq_vencida",
                "nivel": "critico",
                "mensaje": f"Tu evaluación IQ '{iq.evaluacion.nombre}' está vencida",
                "asignacion_id": iq.id,
            })

        # Próximas a vencer (3 días)
        asig_urgentes = Asignacion.objects.filter(
            usuario_asignado=self.user,
            estado__in=["pendiente", "en_progreso"],
            activo=True,
            fecha_limite__lte=(ahora + timezone.timedelta(days=3)).date(),
            fecha_limite__gte=ahora.date(),
        ).select_related("dimension")
        for asig in asig_urgentes:
            alertas.append({
                "tipo": "asignacion_urgente",
                "nivel": "warning",
                "mensaje": (
                    f"Tienes {asig.dias_restantes} día(s) para completar "
                    f"'{asig.dimension.nombre if asig.dimension else 'evaluación'}'"
                ),
                "asignacion_id": str(asig.id),
            })

        return alertas

    # --------------------------------------------------------------- Charts
    def _get_charts(self) -> dict:
        return {
            "mis_asignaciones_por_estado": self._chart_mis_asignaciones(),
            "mis_iq_por_estado": self._chart_mis_iq(),
        }

    def _chart_mis_asignaciones(self) -> list:
        datos = (
            Asignacion.objects.filter(usuario_asignado=self.user, activo=True)
            .values("estado")
            .annotate(total=Count("id"))
        )
        return [{"estado": d["estado"], "total": d["total"]} for d in datos]

    def _chart_mis_iq(self) -> list:
        datos = (
            AsignacionEvaluacionIQ.objects.filter(
                usuario_asignado=self.user, activo=True
            )
            .values("estado")
            .annotate(total=Count("id"))
        )
        return [{"estado": d["estado"], "total": d["total"]} for d in datos]