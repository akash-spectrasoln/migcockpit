from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_delete_objectmap'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE TABLE objectmap (
                object_id VARCHAR(100) NOT NULL,
                tecname VARCHAR(100) NOT NULL,
                object_nme VARCHAR(100),
                tname VARCHAR(100),
                PRIMARY KEY (object_id, tecname)
            );
            """,
            reverse_sql="DROP TABLE objectmap;"
        )
    ]