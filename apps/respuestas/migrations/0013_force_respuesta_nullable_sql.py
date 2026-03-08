from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('respuestas', '0012_alter_respuesta_respuesta_nullable'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE respuestas ALTER COLUMN respuesta DROP NOT NULL;",
            reverse_sql="ALTER TABLE respuestas ALTER COLUMN respuesta SET NOT NULL;",
        ),
    ]
