from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('respuestas', '0011_merge_20260308_0402'),
    ]

    operations = [
        migrations.AlterField(
            model_name='respuesta',
            name='respuesta',
            field=models.CharField(
                blank=True,
                choices=[
                    ('NO_APLICA', 'No Aplica'),
                    ('SI_CUMPLE', 'Sí Cumple'),
                    ('CUMPLE_PARCIAL', 'Cumple Parcialmente'),
                    ('NO_CUMPLE', 'No Cumple'),
                ],
                default=None,
                help_text='El usuario solo puede marcar NO_APLICA. Si deja vacío, sube evidencias para que el auditor califique.',
                max_length=20,
                null=True,
                verbose_name='Respuesta del Usuario',
            ),
        ),
    ]
