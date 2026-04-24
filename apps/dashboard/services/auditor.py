# apps/dashboard/services/auditor.py
"""
Servicio de dashboard para el rol Auditor.
Visión centrada en sus asignaciones IQ pendientes de revisión.
"""

from django.utils import timezone
from django.db.models import Count, Avg

from apps.asignaciones_iq.models import AsignacionEvaluacionIQ, CalculoNivelIQ
from apps.asignaciones.models import Asignacion


class AuditorDashboardService:

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
        empresa = self.empresa
        ahora = timezone.now()
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        iq_qs = AsignacionEvaluacionIQ.objects.filter(empresa=empresa, activo=True)

        # Pendientes de auditar (el usuario completó, falta auditor)
        pendientes_auditoria = iq_qs.filter(estado="completada").count()

        # En revisión (el auditor las tiene asignadas/en proceso)
        en_revision = iq_qs.filter(
            auditado_por=self.user, estado="completada"
        ).count()

        # Auditadas este mes por este auditor
        auditadas_mes = iq_qs.filter(
            auditado_por=self.user,
            estado__in=["auditada", "aprobada"],
            fecha_auditada__gte=inicio_mes,
        ).count()

        # IQ vencidas en la empresa
        iq_vencidas = iq_qs.filter(estado="vencida").count()

        # Asignaciones de encuesta pendientes de revisión (pendiente_auditoria)
        asig_pendientes = Asignacion.objects.filter(
            empresa=empresa,
            estado="pendiente_auditoria",
            activo=True,
        ).count()

        # GAP promedio de las auditorías que hizo este auditor
        gap_promedio = (
            CalculoNivelIQ.objects.filter(
                asignacion__auditado_por=self.user
            )
            .aggregate(avg=Avg("gap"))
            .get("avg")
        )

        return {
            "iq_pendientes_auditoria": pendientes_auditoria,
            "iq_en_revision_mia": en_revision,
            "iq_auditadas_este_mes": auditadas_mes,
            "iq_vencidas": iq_vencidas,
            "asignaciones_encuesta_pendientes": asig_pendientes,
            "gap_promedio_mis_auditorias": (
                round(float(gap_promedio), 2) if gap_promedio else None
            ),
        }

    # --------------------------------------------------------------- Alertas
    def _get_alertas(self) -> list:
        empresa = self.empresa
        ahora = timezone.now()
        alertas = []

        # IQ urgentes (próximas a vencer con estado pendiente/en_progreso)
        urgentes = AsignacionEvaluacionIQ.objects.filter(
            empresa=empresa,
            activo=True,
            estado__in=["pendiente", "en_progreso", "completada"],
            fecha_limite__lte=(ahora + timezone.timedelta(days=3)).date(),
            fecha_limite__gte=ahora.date(),
        ).select_related("usuario_asignado", "evaluacion")
        for iq in urgentes:
            alertas.append({
                "tipo": "iq_urgente",
                "nivel": "critico",
                "mensaje": (
                    f"IQ '{iq.evaluacion.nombre}' de '{iq.usuario_asignado.nombre_completo}' "
                    f"vence en {iq.dias_restantes} día(s)"
                ),
            })

        # Asignaciones encuesta pendientes de auditoría
        asig_urgentes = Asignacion.objects.filter(
            empresa=empresa,
            estado="pendiente_auditoria",
            activo=True,
            fecha_limite__lte=(ahora + timezone.timedelta(days=3)).date(),
        ).select_related("usuario_asignado", "dimension")[:5]
        for asig in asig_urgentes:
            alertas.append({
                "tipo": "asignacion_urgente",
                "nivel": "warning",
                "mensaje": (
                    f"Asignación de '{asig.usuario_asignado.nombre_completo}' "
                    f"esperando auditoría — vence pronto"
                ),
            })

        return alertas

    # --------------------------------------------------------------- Charts
    def _get_charts(self) -> dict:
        return {
            "iq_por_estado": self._chart_iq_por_estado(),
            "gap_clasificacion": self._chart_gap_clasificacion(),
            "carga_semanal": self._chart_carga_semanal(),
        }

    def _chart_iq_por_estado(self) -> list:
        datos = (
            AsignacionEvaluacionIQ.objects.filter(empresa=self.empresa, activo=True)
            .values("estado")
            .annotate(total=Count("id"))
        )
        return [{"estado": d["estado"], "total": d["total"]} for d in datos]

    def _chart_gap_clasificacion(self) -> list:
        """Distribución de brechas por clasificación en la empresa."""
        datos = (
            CalculoNivelIQ.objects.filter(empresa=self.empresa)
            .values("clasificacion_gap")
            .annotate(total=Count("id"))
        )
        return [{"clasificacion": d["clasificacion_gap"], "total": d["total"]} for d in datos]

    def _chart_carga_semanal(self) -> list:
        """IQ auditadas por este auditor en las últimas 8 semanas."""
        from django.db.models.functions import TruncWeek

        datos = (
            AsignacionEvaluacionIQ.objects.filter(
                auditado_por=self.user,
                estado__in=["auditada", "aprobada"],
                fecha_auditada__isnull=False,
            )
            .annotate(semana=TruncWeek("fecha_auditada"))
            .values("semana")
            .annotate(total=Count("id"))
            .order_by("semana")
        )
        return [
            {"semana": d["semana"].strftime("%Y-%m-%d"), "total": d["total"]}
            for d in datos
        ]