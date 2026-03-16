# Migration: add status_extra to MigrationJob for non-blocking status API (node_progress, levels)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0039_add_node_naming_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='migrationjob',
            name='status_extra',
            field=models.JSONField(blank=True, default=dict, null=True, verbose_name='Status extra (node_progress, levels)'),
        ),
    ]
