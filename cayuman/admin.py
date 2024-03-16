from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.admin import UserChangeForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.urls import path
from django.utils.html import format_html
from django.utils.translation import gettext as _

from .models import Cycle
from .models import Member
from .models import Period
from .models import Schedule
from .models import StudentCycle
from .models import Workshop
from .models import WorkshopPeriod


# Setting the name of the django admin panel
admin.site.site_header = "Cayuman"


class MemberChangeForm(UserChangeForm):
    def clean_groups(self):
        try:
            is_student = Group.objects.get(name=settings.STUDENTS_GROUP) in self.cleaned_data["groups"]
        except Group.DoesNotExist:
            is_student = False
        try:
            is_teacher = Group.objects.get(name=settings.TEACHERS_GROUP) in self.cleaned_data["groups"]
        except Group.DoesNotExist:
            is_teacher = False

        if not self.cleaned_data["is_staff"]:
            if not is_student and not is_teacher:
                raise ValidationError(_("User must be either Student or Teacher, or a staff member"))
        else:
            if is_student:
                raise ValidationError(_("Student cannot be staff member"))

        if is_student and is_teacher:
            raise ValidationError(_("User must not be both Student and Teacher"))

        return self.cleaned_data["groups"]


class MemberAdmin(UserAdmin):
    ordering = ("-date_joined",)
    list_display = ("id", "name", "cycle", "date_joined", "is_student", "is_teacher", "is_staff", "is_active")
    filter_horizontal = ("groups", "user_permissions")
    list_per_page = 20

    form = MemberChangeForm

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
    list_display = ("id", "name", "enrollment_start", "date_start", "date_end")
    list_per_page = 20


admin.site.register(Period, PeriodAdmin)


class WorkshopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "full_name", "description")
    list_per_page = 20


admin.site.register(Workshop, WorkshopAdmin)


class WorkshopPeriodAdminForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(WorkshopPeriodAdminForm, self).__init__(*args, **kwargs)
        teachers_group = Group.objects.get(name=settings.TEACHERS_GROUP)
        if "teacher" in self.fields:
            self.fields["teacher"].queryset = Member.objects.filter(groups=teachers_group)

    def clean_schedules(self):
        # Get schedules for same teacher and period
        if self.cleaned_data["teacher"] and self.cleaned_data["period"]:
            other_wps = WorkshopPeriod.objects.filter(teacher=self.cleaned_data["teacher"], period=self.cleaned_data["period"])
            other_schedules = set()
            for wp in other_wps:
                if self.instance:
                    if self.instance.id == wp.id:
                        continue
                for sched in wp.schedules.all():
                    other_schedules.add(sched)

            # check overlapping due to schedules
            if any(sched in other_schedules for sched in self.cleaned_data["schedules"]):
                raise ValidationError(_("There's already another workshop period overlapping with current one"))

        return self.cleaned_data["schedules"]

    class Meta:
        fields = "__all__"
        model = WorkshopPeriod


class WorkshopPeriodAdmin(admin.ModelAdmin):
    list_display = ("id", "workshop", "teacher", "period", "cycles_list", "schedules_list", "num_students", "max_students")
    list_per_page = 20
    filter_horizontal = ("cycles", "schedules")
    list_filter = [
        ("teacher", admin.RelatedOnlyFieldListFilter),
    ]

    form = WorkshopPeriodAdminForm

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


class StudentCycleAdminForm(ModelForm):
    def clean_workshop_periods(self):
        # clean workshop_periods m2m relation
        # this breaks DRY principle with respect to m2m_changed signal handler for model StudentCycle
        # but it's necessary so validation works ok in django admin as well as directly using the model
        # {'student': Member(...), 'cycle': <Cycle: ...>, 'workshop_periods': <QuerySet [<WorkshopPeriod: ...>, <WorkshopPeriod: ...>]>}
        for wp in self.cleaned_data["workshop_periods"]:
            # Count students in this cycle without counting current student
            curr_count = wp.studentcycle_set.exclude(student__id=self.cleaned_data["student"].id).count()
            # curr_count = wp.studentcycle_set.filter(student__id__ne=self.cleaned_data['student'].id).count()
            if wp.max_students > 0 and wp.max_students <= curr_count:
                raise ValidationError(_("Workshop period `%s` has reached its quota of students") % (wp.workshop.name))

            if self.cleaned_data["cycle"] not in wp.cycles.all():
                raise ValidationError(
                    _("Student `%(st)s` cannot be associated with workshop period `%(wp)s` because they belong to the same cycle.")
                    % {"st": self.cleaned_data["student"].get_full_name(), "wp": wp.workshop.name}
                )

            for wp_2 in self.cleaned_data["workshop_periods"]:
                if wp == wp_2:
                    continue

                if wp & wp_2:
                    raise ValidationError(
                        _("Workshop periods `%(w1)s` and `%(w2)s` have colliding schedules.") % {"w1": wp.workshop.name, "w2": wp_2.workshop.name}
                    )

        return self.cleaned_data["workshop_periods"]

    def __init__(self, *args, **kwargs):
        super(StudentCycleAdminForm, self).__init__(*args, **kwargs)
        students_group = Group.objects.get(name=settings.STUDENTS_GROUP)
        if "student" in self.fields:
            self.fields["student"].queryset = Member.objects.filter(groups=students_group)

    class Meta:
        fields = "__all__"
        model = StudentCycle


class StudentCycleAdmin(admin.ModelAdmin):
    ordering = ("-date_joined",)
    list_display = ("id", "student", "cycle", "workshop_periods_list", "date_joined")
    list_per_page = 20
    list_filter = ["cycle"]
    search_fields = ["student__first_name", "student__last_name", "cycle__name"]
    filter_horizontal = ("workshop_periods",)

    form = StudentCycleAdminForm

    @admin.display(description=_("Workshop Periods List"))
    def workshop_periods_list(self, obj):
        wps = obj.workshop_periods.all()
        return format_html("<ul><li>{}</li></ul>".format("</li><li>".join([str(period) for period in wps]))) if wps else None


admin.site.register(StudentCycle, StudentCycleAdmin)
