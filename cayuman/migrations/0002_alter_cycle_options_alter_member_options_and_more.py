# Generated by Django 5.0.2 on 2024-02-29 16:46
from django.db import migrations
from django.db import models
from django.utils.translation import gettext as _


class Migration(migrations.Migration):
    dependencies = [
        ("cayuman", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="cycle",
            options={"verbose_name": _("Cycle"), "verbose_name_plural": _("Cycles")},
        ),
        migrations.AlterModelOptions(
            name="member",
            options={"verbose_name": _("Member"), "verbose_name_plural": _("Members")},
        ),
        migrations.AlterModelOptions(
            name="period",
            options={"verbose_name": _("Period"), "verbose_name_plural": _("Periods")},
        ),
        migrations.AlterModelOptions(
            name="schedule",
            options={
                "verbose_name": _("Schedule"),
                "verbose_name_plural": _("Schedules"),
            },
        ),
        migrations.AlterModelOptions(
            name="studentcycle",
            options={
                "get_latest_by": "date_joined",
                "ordering": ["date_joined"],
                "verbose_name": _("Students Cycle"),
                "verbose_name_plural": _("Students Cycles"),
            },
        ),
        migrations.AlterModelOptions(
            name="workshop",
            options={"verbose_name": _("Workshop"), "verbose_name_plural": _("Workshops")},
        ),
        migrations.AlterModelOptions(
            name="workshopperiod",
            options={
                "verbose_name": _("Workshop's Period"),
                "verbose_name_plural": _("Workshops' Periods"),
            },
        ),
        migrations.AlterUniqueTogether(
            name="workshopperiod",
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name="schedule",
            name="day",
            field=models.CharField(
                choices=[
                    ("monday", _("Monday")),
                    ("tuesday", _("Tuesday")),
                    ("wednesday", _("Wednesday")),
                    ("thursday", _("Thursday")),
                    ("friday", _("Friday")),
                ],
                max_length=10,
            ),
        ),
    ]
