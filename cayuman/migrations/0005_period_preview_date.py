# Generated by Django 5.0.2 on 2024-05-01 15:50
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("cayuman", "0004_period_enrollment_end"),
    ]

    operations = [
        migrations.AddField(
            model_name="period",
            name="preview_date",
            field=models.DateField(blank=True, null=True, verbose_name="Preview date"),
        ),
    ]
