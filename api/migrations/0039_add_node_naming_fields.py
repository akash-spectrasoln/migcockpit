# Generated migration for adding business_name and technical_name to CanvasNode

from django.db import migrations, models


def populate_node_names(apps, schema_editor):
    """Populate business_name and technical_name from existing node data"""
    CanvasNode = apps.get_model('api', 'CanvasNode')
    for node in CanvasNode.objects.all():
        # Generate business_name from node_name or label if available
        if not node.business_name:
            node.business_name = getattr(node, 'node_name', None) or getattr(node, 'label', None) or f'{node.node_type} Node'
        
        # Generate technical_name from node_id
        if not node.technical_name and node.node_id:
            short_id = node.node_id[:8] if len(node.node_id) >= 8 else node.node_id.ljust(8, '0')
            node_type = node.node_type.lower() if node.node_type else 'node'
            node.technical_name = f'{node_type}_{short_id}'
        
        node.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0038_auto_20251204_1605'),
    ]

    operations = [
        # Add business_name field (nullable initially)
        migrations.AddField(
            model_name='canvasnode',
            name='business_name',
            field=models.CharField(max_length=255, null=True, blank=True, verbose_name='Business Name (Editable)'),
        ),
        # Add technical_name field (nullable initially)
        migrations.AddField(
            model_name='canvasnode',
            name='technical_name',
            field=models.CharField(max_length=255, null=True, blank=True, verbose_name='Technical Name (Read-only)'),
        ),
        # Populate the new fields from existing data
        migrations.RunPython(populate_node_names, migrations.RunPython.noop),
        # Make fields non-nullable after population
        migrations.AlterField(
            model_name='canvasnode',
            name='business_name',
            field=models.CharField(max_length=255, verbose_name='Business Name (Editable)'),
        ),
        migrations.AlterField(
            model_name='canvasnode',
            name='technical_name',
            field=models.CharField(max_length=255, verbose_name='Technical Name (Read-only)'),
        ),
        # Add node_name field for backward compatibility (originally was 'label')
        migrations.AddField(
            model_name='canvasnode',
            name='node_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Node Name (Legacy)'),
        ),
    ]

