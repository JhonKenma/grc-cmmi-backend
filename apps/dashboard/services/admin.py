# apps/dashboard/services/admin.py
"""
Servicio de dashboard para el rol Administrador de Empresa.
Visión acotada a su empresa: encuestas, IQ, usuarios, proveedores y proyectos.
"""

from django.utils import timezone
from django.db.models import Count, Avg, Q

from apps.encuestas.models import EvaluacionEmpresa
from apps.asignaciones.models import Asignacion
from apps.asignaciones_iq.models import AsignacionEvaluacionIQ, CalculoNivelIQ
from apps.proveedores.models import Proveedor
from apps.usuarios.models import Usuario


class AdminDashboardService:

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

        # Plan
        plan = getattr(empresa, "plan", None)
        plan_info = None
        if plan:
            plan_info = {
                "tipo": plan.tipo,
                "esta_activo": plan.esta_activo,
                "dias_restantes": plan.dias_restantes,
                "max_usuarios": plan.max_usuarios,
            }

        # Usuarios de la empresa
        usuarios_activos = Usuario.objects.filter(empresa=empresa, activo=True).count()

        # Evaluaciones encuesta
        ee_qs = EvaluacionEmpresa.objects.filter(empresa=empresa, activo=True)
        ee_activas = ee_qs.filter(estado__in=["activa", "en_progreso"]).count()
        ee_completadas = ee_qs.filter(estado="completada").count()
        ee_vencidas = ee_qs.filter(estado="vencida").count()

        # Evaluaciones IQ
        iq_qs = AsignacionEvaluacionIQ.objects.filter(empresa=empresa, activo=True)
        iq_pendientes = iq_qs.filter(estado__in=["pendiente", "en_progreso"]).count()
        iq_en_auditoria = iq_qs.filter(estado="completada").count()
        iq_auditadas = iq_qs.filter(estado__in=["auditada", "aprobada"]).count()

        # Asignaciones encuesta (tareas de usuarios)
        asig_qs = Asignacion.objects.filter(empresa=empresa, activo=True)
        asig_pendientes = asig_qs.filter(estado="pendiente").count()
        asig_en_progreso = asig_qs.filter(estado="en_progreso").count()
        asig_vencidas = asig_qs.filter(estado="vencido").count()
        asig_auditoria = asig_qs.filter(estado="pendiente_auditoria").count()

        # Proveedores
        total_proveedores = Proveedor.objects.filter(empresa=empresa, activo=True).count()
        proveedores_riesgo_alto = Proveedor.objects.filter(
            empresa=empresa, activo=True, nivel_riesgo="alto"
        ).count()

        # GAP promedio (última evaluación IQ auditada)
        gap_promedio = (
            CalculoNivelIQ.objects.filter(empresa=empresa)
            .aggregate(avg_gap=Avg("gap"))
            .get("avg_gap")
        )

        return {
            "plan": plan_info,
            "usuarios_activos": usuarios_activos,
            "evaluaciones_encuesta": {
                "activas": ee_activas,
                "completadas": ee_completadas,
                "vencidas": ee_vencidas,
            },
            "evaluaciones_iq": {
                "pendientes": iq_pendientes,
                "en_auditoria": iq_en_auditoria,
                "auditadas": iq_auditadas,
            },
            "asignaciones": {
                "pendientes": asig_pendientes,
                "en_progreso": asig_en_progreso,
                "pendiente_auditoria": asig_auditoria,
                "vencidas": asig_vencidas,
            },
            "proveedores": {
                "total": total_proveedores,
                "riesgo_alto": proveedores_riesgo_alto,
            },
            "gap_promedio": round(float(gap_promedio), 2) if gap_promedio else None,
        }

    # --------------------------------------------------------------- Alertas
    def _get_alertas(self) -> list:
        empresa = self.empresa
        ahora = timezone.now()
        alertas = []

        # Plan próximo a vencer
        plan = getattr(empresa, "plan", None)
        if plan and plan.fecha_expiracion:
            dias = plan.dias_restantes
            if dias is not None and dias <= 30:
                nivel = "critico" if dias <= 7 else "warning"
                alertas.append({
                    "tipo": "plan_por_vencer",
                    "nivel": nivel,
                    "mensaje": f"El plan '{plan.get_tipo_display()}' vence en {dias} días",
                })

        # Evaluaciones vencidas
        ee_vencidas = EvaluacionEmpresa.objects.filter(
            empresa=empresa, estado="vencida"
        ).select_related("encuesta")
        for ev in ee_vencidas:
            alertas.append({
                "tipo": "evaluacion_vencida",
                "nivel": "alto",
                "mensaje": f"Evaluación '{ev.encuesta.nombre}' está vencida",
                "evaluacion_id": str(ev.id),
            })

        # Asignaciones vencidas
        asig_vencidas = Asignacion.objects.filter(
            empresa=empresa, estado="vencido", activo=True
        ).select_related("usuario_asignado", "dimension")[:5]
        for asig in asig_vencidas:
            alertas.append({
                "tipo": "asignacion_vencida",
                "nivel": "alto",
                "mensaje": (
                    f"Asignación de '{asig.usuario_asignado.nombre_completo}' "
                    f"({asig.dimension.nombre if asig.dimension else 'completa'}) está vencida"
                ),
            })

        # IQ vencidas
        iq_vencidas = AsignacionEvaluacionIQ.objects.filter(
            empresa=empresa, estado="vencida", activo=True
        ).select_related("usuario_asignado", "evaluacion")[:5]
        for iq in iq_vencidas:
            alertas.append({
                "tipo": "iq_vencida",
                "nivel": "alto",
                "mensaje": (
                    f"IQ '{iq.evaluacion.nombre}' de '{iq.usuario_asignado.nombre_completo}' está vencida"
                ),
            })

        return alertas

    # --------------------------------------------------------------- Charts
    def _get_charts(self) -> dict:
        return {
            "progreso_evaluaciones": self._chart_progreso_evaluaciones(),
            "iq_por_estado": self._chart_iq_por_estado(),
            "gap_por_seccion": self._chart_gap_por_seccion(),
            "asignaciones_por_estado": self._chart_asignaciones_por_estado(),
            "proveedores_por_riesgo": self._chart_proveedores_por_riesgo(),
        }

    def _chart_progreso_evaluaciones(self) -> list:
        """Evaluaciones de encuesta agrupadas por estado."""
        datos = (
            EvaluacionEmpresa.objects.filter(empresa=self.empresa, activo=True)
            .values("estado")
            .annotate(total=Count("id"))
        )
        return [{"estado": d["estado"], "total": d["total"]} for d in datos]

    def _chart_iq_por_estado(self) -> list:
        datos = (
            AsignacionEvaluacionIQ.objects.filter(empresa=self.empresa, activo=True)
            .values("estado")
            .annotate(total=Count("id"))
        )
        return [{"estado": d["estado"], "total": d["total"]} for d in datos]

    def _chart_gap_por_seccion(self) -> list:
        """GAP promedio por sección/dominio de la última evaluación IQ auditada."""
        ultima_iq = (
            AsignacionEvaluacionIQ.objects.filter(
                empresa=self.empresa, estado__in=["auditada", "aprobada"]
            )
            .order_by("-fecha_auditada")
            .first()
        )
        if not ultima_iq:
            return []

        datos = CalculoNivelIQ.objects.filter(asignacion=ultima_iq).values(
            "seccion", "nivel_actual", "nivel_deseado", "gap", "clasificacion_gap"
        )
        return list(datos)

    def _chart_asignaciones_por_estado(self) -> list:
        datos = (
            Asignacion.objects.filter(empresa=self.empresa, activo=True)
            .values("estado")
            .annotate(total=Count("id"))
        )
        return [{"estado": d["estado"], "total": d["total"]} for d in datos]

    def _chart_proveedores_por_riesgo(self) -> list:
        datos = (
            Proveedor.objects.filter(empresa=self.empresa, activo=True)
            .values("nivel_riesgo")
            .annotate(total=Count("id"))
        )
        return [{"nivel_riesgo": d["nivel_riesgo"], "total": d["total"]} for d in datos]