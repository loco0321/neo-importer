# Generated by Django 2.0 on 2019-01-22 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('neo_importer', '0002_fileuploadhistory_sheet_importers'),
    ]

    operations = [
        migrations.AddField(
            model_name='fileuploadhistory',
            name='celery_tasks',
            field=models.CharField(blank=True, max_length=250, null=True),
        ),
        migrations.AddField(
            model_name='fileuploadhistory',
            name='validate_end',
            field=models.NullBooleanField(),
        ),
    ]
