"""Ensure result_type column exists and has correct data."""
from django.db import migrations, models

def ensure_result_type_values(apps, schema_editor):
    """Ensure all existing records have a result_type value."""
    GameResult = apps.get_model('game', 'GameResult')
    db_alias = schema_editor.connection.alias
    GameResult.objects.using(db_alias).filter(result_type__isnull=True).update(result_type='completion')

class Migration(migrations.Migration):

    dependencies = [
        ('game', '0005_ensure_result_type'),
    ]

    operations = [
        # First make sure the column exists
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'game_gameresult' 
                    AND column_name = 'result_type'
                ) THEN
                    ALTER TABLE game_gameresult 
                    ADD COLUMN result_type varchar(20) DEFAULT 'completion';
                END IF;
            END
            $$;
            """,
            reverse_sql="""
            -- No reverse operation needed
            """
        ),
        # Then update the field definition
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
        # Finally ensure all records have a value
        migrations.RunPython(
            ensure_result_type_values,
            reverse_code=migrations.RunPython.noop
        ),
    ]