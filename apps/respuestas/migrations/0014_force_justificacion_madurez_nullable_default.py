from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('respuestas', '0013_force_respuesta_nullable_sql'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE respuestas ALTER COLUMN justificacion_madurez SET DEFAULT '';"
                "ALTER TABLE respuestas ALTER COLUMN justificacion_madurez DROP NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE respuestas ALTER COLUMN justificacion_madurez DROP DEFAULT;"
                "ALTER TABLE respuestas ALTER COLUMN justificacion_madurez SET NOT NULL;"
            ),
        ),
    ]
