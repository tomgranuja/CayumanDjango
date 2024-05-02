from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import path
from django.utils.html import format_html
from django.utils.translation import gettext as _

from .forms import AdminMemberChangeForm
from .forms import AdminStudentCycleForm
from .forms import AdminWorkshopPeriodForm
from .models import Cycle
from .models import Member
from .models import Period
from .models import Schedule
from .models import StudentCycle
from .models import Workshop
from .models import WorkshopPeriod


# Setting the name of the django admin panel
admin.site.site_header = "Cayuman"


class MemberAdmin(UserAdmin):
    ordering = ("-date_joined",)
    list_display = ("id", "name", "cycle", "date_joined", "is_student", "is_teacher", "is_staff", "is_active")
    filter_horizontal = ("groups", "user_permissions")
    list_per_page = 20

    form = AdminMemberChangeForm

    @admin.display(description=_("Full Name"))
    def name(self, obj):
        return obj.get_full_name()

    def date_joined(self, obj):
        return format_html(str(obj.date_joined.strftime("%B %d, %Y"))) if obj.date_joined else None

    @admin.display(boolean=True, description=_("Is Student"))
    def is_student(self, obj):
        return obj.is_student

    @admin.display(boolean=True, description=_("Is Teacher"))
    def is_teacher(self, obj):
        return obj.is_teacher

    @admin.display(description=_("Cycle"))
    def cycle(self, obj):
        return format_html(obj.current_student_cycle.cycle.name if obj.is_student and obj.current_student_cycle else "-")


admin.site.register(Member, MemberAdmin)


class CycleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    list_per_page = 20


admin.site.register(Cycle, CycleAdmin)


class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "day", "time_start", "time_end")
    list_per_page = 20
    list_filter = ("day",)


admin.site.register(Schedule, ScheduleAdmin)


class PeriodAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "preview_date", "enrollment_start", "enrollment_end", "date_start", "date_end", "active")
    list_per_page = 20

    @admin.display(boolean=True, description=_("Active"))
    def active(self, obj):
        return obj == Period.objects.current()


admin.site.register(Period, PeriodAdmin)


class WorkshopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "full_name", "description")
    list_per_page = 20


admin.site.register(Workshop, WorkshopAdmin)


class WorkshopPeriodAdmin(admin.ModelAdmin):
    list_display = ("id", "workshop", "teacher", "period", "cycles_list", "schedules_list", "num_students", "max_students")
    list_per_page = 20
    filter_horizontal = ("cycles", "schedules")
    list_filter = [
        ("teacher", admin.RelatedOnlyFieldListFilter),
    ]

    form = AdminWorkshopPeriodForm

    @admin.display(description=_("Cycles"))
    def cycles_list(self, obj):
        return ", ".join([cycle.name for cycle in obj.cycles.all()])

    @admin.display(description=_("Schedules"))
    def schedules_list(self, obj):
        output = "<ul>"
        for sched in obj.schedules.all():
            output += f"<li>{str(sched)}</li>"
        output += "</ul>"
        return format_html(output)

    @admin.display(description=_("Enrolled Students"))
    def num_students(self, obj):
        return format_html(f'<a href="{obj.id}/students/">{obj.count_students()}</a>')

    def get_urls(self):
        """Add url for custom `students` view"""
        from functools import update_wrapper

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        info = self.opts.app_label, self.opts.model_name
        urls = super().get_urls()
        new_urls = [
            path(
                "<path:object_id>/students/",
                wrap(self.workshop_period_students_view),
                name="%s_%s_students" % info,
            ),
        ]
        return new_urls + urls

    def workshop_period_students_view(self, request, object_id, extra_context=None):
        """Admin view student cycles per workshop period"""
        from django.contrib.admin.views.main import PAGE_VAR
        from django.contrib.admin.utils import unquote
        from django.core.exceptions import PermissionDenied
        from django.utils.text import capfirst
        from django.template.response import TemplateResponse

        # Check permissions
        model = self.model
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, model._meta, object_id)

        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied

        # Then get students for this object.
        students_list = obj.studentcycle_set.all()

        paginator = self.get_paginator(request, students_list, 100)
        page_number = request.GET.get(PAGE_VAR, 1)
        page_obj = paginator.get_page(page_number)
        page_range = paginator.get_elided_page_range(page_obj.number)

        context = {
            **self.admin_site.each_context(request),
            "title": _("Students: %s") % obj,
            "subtitle": None,
            "students_list": page_obj,
            "page_range": page_range,
            "page_var": PAGE_VAR,
            "pagination_required": paginator.count > 100,
            "module_name": str(capfirst(self.opts.verbose_name_plural)),
            "object": obj,
            "opts": self.opts,
            "preserved_filters": self.get_preserved_filters(request),
            **(extra_context or {}),
        }

        request.current_app = self.admin_site.name

        return TemplateResponse(
            request,
            "admin/workshop_period_students.html",
            context,
        )


admin.site.register(WorkshopPeriod, WorkshopPeriodAdmin)


class StudentCycleAdmin(admin.ModelAdmin):
    ordering = ("-date_joined",)
    list_display = ("id", "student", "cycle", "workshop_periods_list", "date_joined")
    list_per_page = 20
    list_filter = ["cycle"]
    search_fields = ["student__first_name", "student__last_name", "cycle__name"]
    filter_horizontal = ("workshop_periods",)

    form = AdminStudentCycleForm

    @admin.display(description=_("Workshop Periods List"))
    def workshop_periods_list(self, obj):
        wps = obj.workshop_periods_by_period()
        return format_html("<ul><li>{}</li></ul>".format("</li><li>".join([str(wp) for wp in wps]))) if wps else None


admin.site.register(StudentCycle, StudentCycleAdmin)
