# apps/empresas/migrations/0004_asignar_plan_demo_empresas.py
from django.db import migrations
from django.utils import timezone
from datetime import timedelta


def asignar_plan_demo(apps, schema_editor):
    """
    Asigna plan demo a todas las empresas que no tengan plan.
    Se ejecuta automáticamente en cada migrate (local y GCP).
    """
    Empresa     = apps.get_model('empresas', 'Empresa')
    PlanEmpresa = apps.get_model('empresas', 'PlanEmpresa')

    for empresa in Empresa.objects.all():
        plan, creado = PlanEmpresa.objects.get_or_create(empresa=empresa)
        if creado:
            plan.tipo                = 'demo'
            plan.max_usuarios        = 8
            plan.max_administradores = 2
            plan.max_auditores       = 2
            plan.fecha_expiracion    = timezone.now() + timedelta(days=60)
            plan.save()
            print(f'✅ Plan demo creado: {empresa.nombre}')
        else:
            print(f'⚠️  Ya tenía plan: {empresa.nombre}')


def revertir_plan_demo(apps, schema_editor):
    """
    Rollback: elimina los planes creados por esta migración.
    Solo elimina planes de tipo demo para no afectar otros planes.
    """
    PlanEmpresa = apps.get_model('empresas', 'PlanEmpresa')
    PlanEmpresa.objects.filter(tipo='demo').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0003_planempresa'),  # ← depende de la migración anterior
    ]

    operations = [
        migrations.RunPython(asignar_plan_demo, revertir_plan_demo),
    ]