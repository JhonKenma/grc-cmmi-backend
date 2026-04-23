# apps/dashboard/services/superadmin.py
"""
Servicio de dashboard para el rol SuperAdmin.
Visión global: todas las empresas, planes, usuarios, evaluaciones y proveedores.
"""

from django.utils import timezone
from django.db.models import Count, Q

from apps.empresas.models import Empresa, PlanEmpresa
from apps.usuarios.models import Usuario
from apps.encuestas.models import EvaluacionEmpresa
from apps.evaluaciones.models import Evaluacion
from apps.asignaciones_iq.models import AsignacionEvaluacionIQ
from apps.proveedores.models import Proveedor


class SuperAdminDashboardService:

    def get_summary(self) -> dict:
        return {
            "kpis": self._get_kpis(),
            "alertas": self._get_alertas(),
            "charts": self._get_charts(),
        }

    # ------------------------------------------------------------------ KPIs
    def _get_kpis(self) -> dict:
        ahora = timezone.now()

        empresas_qs = Empresa.objects.filter(activo=True)
        total_empresas = empresas_qs.count()

        # Planes próximos a vencer (≤ 30 días) y ya vencidos
        planes = PlanEmpresa.objects.select_related("empresa")
        planes_vencidos = planes.filter(
            fecha_expiracion__lt=ahora
        ).count()
        planes_por_vencer = planes.filter(
            fecha_expiracion__gte=ahora,
            fecha_expiracion__lte=ahora + timezone.timedelta(days=30),
        ).count()

        total_usuarios = Usuario.objects.filter(activo=True).exclude(rol="superadmin").count()

        total_proveedores = Proveedor.objects.filter(activo=True).count()

        # Evaluaciones encuesta
        ee_total = EvaluacionEmpresa.objects.filter(activo=True).count()
        ee_vencidas = EvaluacionEmpresa.objects.filter(estado="vencida").count()

        # Evaluaciones IQ
        iq_total = AsignacionEvaluacionIQ.objects.filter(activo=True).count()
        iq_completadas = AsignacionEvaluacionIQ.objects.filter(
            estado__in=["auditada", "aprobada"]
        ).count()

        return {
            "total_empresas": total_empresas,
            "planes_vencidos": planes_vencidos,
            "planes_por_vencer_30d": planes_por_vencer,
            "total_usuarios": total_usuarios,
            "total_proveedores": total_proveedores,
            "evaluaciones_encuesta_total": ee_total,
            "evaluaciones_encuesta_vencidas": ee_vencidas,
            "evaluaciones_iq_total": iq_total,
            "evaluaciones_iq_completadas": iq_completadas,
        }

    # --------------------------------------------------------------- Alertas
    def _get_alertas(self) -> list:
        ahora = timezone.now()
        alertas = []

        # Planes vencidos
        planes_vencidos = PlanEmpresa.objects.filter(
            fecha_expiracion__lt=ahora
        ).select_related("empresa")
        for plan in planes_vencidos:
            alertas.append({
                "tipo": "plan_vencido",
                "nivel": "critico",
                "mensaje": f"Plan de '{plan.empresa.nombre}' venció el {plan.fecha_expiracion.strftime('%d/%m/%Y')}",
                "empresa_id": str(plan.empresa.id),
            })

        # Evaluaciones vencidas
        evals_vencidas = EvaluacionEmpresa.objects.filter(
            estado="vencida"
        ).select_related("empresa", "encuesta")[:10]
        for ev in evals_vencidas:
            alertas.append({
                "tipo": "evaluacion_vencida",
                "nivel": "alto",
                "mensaje": f"Evaluación '{ev.encuesta.nombre}' de '{ev.empresa.nombre}' está vencida",
                "empresa_id": str(ev.empresa.id),
            })

        # Empresas sin plan
        empresas_sin_plan = Empresa.objects.filter(
            activo=True, plan__isnull=True
        )
        for emp in empresas_sin_plan:
            alertas.append({
                "tipo": "sin_plan",
                "nivel": "warning",
                "mensaje": f"'{emp.nombre}' no tiene plan asignado",
                "empresa_id": str(emp.id),
            })

        return alertas

    # --------------------------------------------------------------- Charts
    def _get_charts(self) -> dict:
        return {
            "empresas_por_plan": self._chart_empresas_por_plan(),
            "evaluaciones_por_estado": self._chart_evaluaciones_por_estado(),
            "proveedores_por_riesgo": self._chart_proveedores_por_riesgo(),
            "usuarios_por_rol": self._chart_usuarios_por_rol(),
        }

    def _chart_empresas_por_plan(self) -> list:
        """Distribución de empresas según el tipo de plan."""
        datos = (
            PlanEmpresa.objects.values("tipo")
            .annotate(total=Count("id"))
            .order_by("tipo")
        )
        return [{"plan": d["tipo"], "total": d["total"]} for d in datos]

    def _chart_evaluaciones_por_estado(self) -> list:
        """Encuestas + IQ agrupadas por estado (vista global)."""
        # Encuestas normales
        ee = (
            EvaluacionEmpresa.objects.filter(activo=True)
            .values("estado")
            .annotate(total=Count("id"))
        )
        # IQ
        iq = (
            AsignacionEvaluacionIQ.objects.filter(activo=True)
            .values("estado")
            .annotate(total=Count("id"))
        )

        resultado = {}
        for row in ee:
            resultado[row["estado"]] = resultado.get(row["estado"], 0) + row["total"]
        for row in iq:
            resultado[row["estado"]] = resultado.get(row["estado"], 0) + row["total"]

        return [{"estado": k, "total": v} for k, v in resultado.items()]

    def _chart_proveedores_por_riesgo(self) -> list:
        datos = (
            Proveedor.objects.filter(activo=True)
            .values("nivel_riesgo")
            .annotate(total=Count("id"))
        )
        return [{"nivel_riesgo": d["nivel_riesgo"], "total": d["total"]} for d in datos]

    def _chart_usuarios_por_rol(self) -> list:
        datos = (
            Usuario.objects.filter(activo=True)
            .exclude(rol="superadmin")
            .values("rol")
            .annotate(total=Count("id"))
        )
        return [{"rol": d["rol"], "total": d["total"]} for d in datos]