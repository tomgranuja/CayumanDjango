# Generated manually
from django.db import migrations
from django.utils.translation import gettext_lazy as _


def create_activity_types(apps, schema_editor):
    """
    Create default activity types needed for the system.
    """
    ActivityType = apps.get_model("smiles", "ActivityType")

    # Create activity types
    activity_types = [
        {"name": _("Workshop Session"), "description": _("Regular workshop session"), "is_selectable": True, "requires_attendance": True},
        {
            "name": _("Academic Subject Session"),
            "description": _("Regular academic subject session"),
            "is_selectable": False,
            "requires_attendance": True,
        },
        {"name": _("Recess"), "description": _("Break time between classes"), "is_selectable": False, "requires_attendance": False},
        {"name": _("Lunch"), "description": _("Lunch period"), "is_selectable": False, "requires_attendance": False},
    ]

    for at_data in activity_types:
        ActivityType.objects.get_or_create(
            name=at_data["name"],
            defaults={
                "description": at_data["description"],
                "is_selectable": at_data["is_selectable"],
                "requires_attendance": at_data["requires_attendance"],
            },
        )


def reverse_activity_types(apps, schema_editor):
    """
    Remove created activity types.
    """
    ActivityType = apps.get_model("smiles", "ActivityType")
    ActivityType.objects.filter(name__in=[_("Workshop Session"), _("Academic Subject Session"), _("Recess"), _("Lunch")]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("smiles", "0012_alter_attendance_options_alter_activity_created_at_and_more"),
    ]

    operations = [
        migrations.RunPython(create_activity_types, reverse_activity_types),
    ]
