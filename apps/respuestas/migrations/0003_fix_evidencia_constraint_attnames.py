from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Recrea el CheckConstraint usando attnames directos (respuesta_id / respuesta_iq_id)
    en lugar de traversal FK (respuesta / respuesta_iq).
    Ambas formas generan el mismo SQL en PostgreSQL, pero la versión attname funciona
    correctamente en la validación Python-level de validate_constraints().
    """

    dependencies = [
        ('respuestas', '0002_fix_evidencia_respuesta_nullable'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='evidencia',
            name='evidencia_exactly_one_respuesta_chk',
        ),
        migrations.AddConstraint(
            model_name='evidencia',
            constraint=models.CheckConstraint(
                condition=(
                    (
                        models.Q(respuesta_id__isnull=False)
                        & models.Q(respuesta_iq_id__isnull=True)
                    )
                    | (
                        models.Q(respuesta_id__isnull=True)
                        & models.Q(respuesta_iq_id__isnull=False)
                    )
                ),
                name='evidencia_exactly_one_respuesta_chk',
            ),
        ),
    ]
