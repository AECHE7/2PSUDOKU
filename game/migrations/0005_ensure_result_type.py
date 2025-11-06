"""Ensure result_type field exists and is properly initialized."""
from django.db import migrations, models

def ensure_result_type_default(apps, schema_editor):
    """Set default value for any existing records."""
    GameResult = apps.get_model('game', 'GameResult')
    GameResult.objects.filter(result_type__isnull=True).update(result_type='completion')

class Migration(migrations.Migration):
    dependencies = [
        ('game', '0004_alter_gameresult_loser'),
    ]

    operations = [
        migrations.RunPython(ensure_result_type_default),
        # Re-add field definition to ensure it exists
        migrations.AlterField(
            model_name='gameresult',
            name='result_type',
            field=models.CharField(
                choices=[
                    ('completion', 'Won by completing puzzle first'),
                    ('forfeit', 'Won by opponent forfeit/abandonment'),
                    ('timeout', 'Won by opponent timeout'),
                ],
                default='completion',
                max_length=20,
            ),
        ),
    ]