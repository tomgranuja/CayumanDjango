from django.contrib import admin
from django.db import models as django_models
from django_json_widget.widgets import JSONEditorWidget

from smiles.models import Group
from smiles.models import Subject
from smiles.models import SubjectOffering
from smiles.models import Term


class TermAdmin(admin.ModelAdmin):
    formfield_overrides = {
        django_models.JSONField: {"widget": JSONEditorWidget},
    }


# Register with custom admin classes
admin.site.register(Term, TermAdmin)
admin.site.register(Group, TermAdmin)  # Reusing the same admin class for simplicity
admin.site.register(Subject, TermAdmin)
admin.site.register(SubjectOffering, TermAdmin)
# Register other models as needed
