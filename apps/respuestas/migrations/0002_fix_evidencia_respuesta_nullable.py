from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('respuestas', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE evidencias '
                'ALTER COLUMN respuesta_id DROP NOT NULL;'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddConstraint(
            model_name='evidencia',
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(('respuesta__isnull', False), ('respuesta_iq__isnull', True)))
                    | (models.Q(('respuesta__isnull', True), ('respuesta_iq__isnull', False)))
                ),
                name='evidencia_exactly_one_respuesta_chk',
            ),
        ),
    ]