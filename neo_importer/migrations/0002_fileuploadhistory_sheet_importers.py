# Generated by Django 2.0 on 2019-01-03 17:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('neo_importer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='fileuploadhistory',
            name='sheet_importers',
            field=models.ManyToManyField(blank=True, null=True, to='neo_importer.FileUploadHistory', verbose_name='sheet importers'),
        ),
    ]