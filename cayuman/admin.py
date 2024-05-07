from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q
from django.urls import path
from django.urls import reverse_lazy as reverse
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


# actions
def create_export_to_csv_action(fields):
    """Factory function to create an export_to_csv admin action for specified fields."""
    import csv
    import re
    from django.http import HttpResponse
    from django.utils.html import strip_tags

    def export_to_csv(modeladmin, request, queryset):
        meta = modeladmin.model._meta
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename={}.csv".format(meta)
        writer = csv.writer(response)

        # Fetch headers: use verbose_name from model field or short_description from admin methods
        headers = []
        for field in fields:
            try:
                if hasattr(modeladmin, field):
                    field_obj = getattr(modeladmin, field)
                    if callable(field_obj) and hasattr(field_obj, "short_description"):
                        headers.append(getattr(field_obj, "short_description"))
                    else:
                        headers.append(modeladmin.model._meta.get_field(field).verbose_name)
                else:
                    # This is used when field is neither a method nor directly available as a field
                    headers.append(modeladmin.model._meta.get_field(field).verbose_name)
            except Exception:
                # Fallback to field name if it's neither in model fields nor an annotated method
                headers.append(field)

        # Write a first row with header information
        writer.writerow(headers)

        for obj in queryset:
            row = []
            for field in fields:
                field_value = getattr(modeladmin, field, None)
                if callable(field_value):
                    value = field_value(obj)
                else:
                    value = getattr(obj, field, None)
                    if callable(value):
                        value = value()

                # Handle case where value might be HTML
                if isinstance(value, str) and ("<" in value and ">" in value):
                    # DIRTY HACK: turn </li><li> to ,
                    if re.search(r"\s*</li>\s*<li>\s*", value):
                        value = re.sub(r"\s*</li>\s*<li>\s*", ", ", value)
                    value = strip_tags(value)  # Strips HTML to plain text
                elif isinstance(value, bool):
                    value = 1 if value else 0

                row.append(value)
            writer.writerow(row)

        return response

    export_to_csv.short_description = _("Export Selected to CSV")
    return export_to_csv


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
        return obj.is_current()


admin.site.register(Period, PeriodAdmin)


class WorkshopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "full_name", "description")
    list_per_page = 20


admin.site.register(Workshop, WorkshopAdmin)


class WorkshopPeriodCyclesFilter(admin.SimpleListFilter):
    """Filter workshop periods by cycle"""

    title = _("Cycle")
    parameter_name = "cycle"

    def lookups(self, request, model_admin):
        return list(Cycle.objects.values_list("id", "name"))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(cycles__id=self.value())
        return queryset


class WorkshopPeriodAdmin(admin.ModelAdmin):
    list_display = ("id", "workshop", "teacher", "period", "cycles_list", "schedules_list", "num_students", "max_students", "external_link", "active")
    list_per_page = 20
    filter_horizontal = ("cycles", "schedules")
    list_filter = [
        ("period", admin.RelatedOnlyFieldListFilter),
        ("teacher", admin.RelatedOnlyFieldListFilter),
        WorkshopPeriodCyclesFilter,
    ]

    form = AdminWorkshopPeriodForm
    actions = [
        create_export_to_csv_action(["workshop", "teacher", "period", "cycles_list", "schedules_list", "num_students", "max_students", "active"])
    ]

    def changelist_view(self, request, extra_context=None):
        # Check if the URL already has any filters set, if not set period to the current one
        from django.urls import reverse_lazy as reverse
        from django.http import HttpResponseRedirect

        if not request.GET and Period.objects.current():
            # Construct the URL for the filtered view
            current_period_id = Period.objects.current().id
            base_url = reverse("admin:%s_%s_changelist" % (self.model._meta.app_label, self.model._meta.model_name))
            query_string = f"period__id__exact={current_period_id}"
            return HttpResponseRedirect(f"{base_url}?{query_string}")

        # If the parameter is already there or there is no current period, just render the default view
        return super().changelist_view(request, extra_context)

    @admin.display(boolean=True, description=_("Active"))
    def active(self, obj):
        return obj.period.is_current()

    @admin.display(description=_("Link"))
    def external_link(self, obj):
        return format_html(f'<a href="{obj.get_absolute_url()}" target="_blank">{_("View on site")}</a>')

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
        return format_html(
            f'<a href="{reverse("admin:cayuman_workshopperiod_student_cycles", kwargs={"object_id": obj.id})}">{obj.count_students()}</a>'
        )

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
                "<path:object_id>/student_cycles/",
                wrap(self.workshop_period_students_view),
                name="%s_%s_student_cycles" % info,  # cayuman_workshopperiod_student_cycles
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
        students_list = obj.studentcycle_set.filter(student__is_active=True)

        paginator = self.get_paginator(request, students_list, 100)
        page_number = request.GET.get(PAGE_VAR, 1)
        page_obj = paginator.get_page(page_number)
        page_range = paginator.get_elided_page_range(page_obj.number)

        context = {
            **self.admin_site.each_context(request),
            "title": _("Student Cycles: %s") % (obj),
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
    list_display = ("id", "student", "cycle", "date_joined", "this_period_workshops_html", "previous_periods_workshops", "active")
    list_per_page = 20
    list_filter = ["cycle"]
    search_fields = ["student__first_name", "student__last_name", "cycle__name"]
    filter_horizontal = ("workshop_periods",)
    readonly_fields = ["student", "cycle"]

    form = AdminStudentCycleForm
    actions = [create_export_to_csv_action(["student", "cycle", "date_joined", "this_period_workshops_list", "active"])]

    def get_form(self, request, obj=None, **kwargs):
        form = super(StudentCycleAdmin, self).get_form(request, obj, **kwargs)
        current_period = Period.objects.current()
        if obj:
            # if obj exists then show only workshop_periods chosen in the past and workshop_periods corresponding to current period and cycle
            existing_workshop_period_ids = obj.workshop_periods.values_list("id", flat=True)

            form.base_fields["workshop_periods"].queryset = WorkshopPeriod.objects.filter(
                Q(period=current_period, cycles=obj.cycle) | Q(id__in=existing_workshop_period_ids)
            ).distinct()
        else:
            # if creating a new obj show workshop_periods only for current period
            form.base_fields["workshop_periods"].queryset = WorkshopPeriod.objects.filter(period=current_period)
        return form

    def get_readonly_fields(self, request, obj=None):
        # Fields student and cycle are readonly if the object exists
        if obj:
            return ["student", "cycle"]
        else:
            # if we are adding a new object, then the fields are writable
            return []

    def get_queryset(self, request):
        """By default remove students that are inactive"""
        queryset = super().get_queryset(request)
        return queryset.filter(student__is_active=True)

    @admin.display(description=_("Workshops %s") % (Period.objects.current()))
    def this_period_workshops_html(self, obj):
        """Display function to use in Django admin list for this model"""
        wps = obj.workshop_periods_by_period(Period.objects.current())
        if wps:
            if obj.is_schedule_full(Period.objects.current()):
                text = _("Full schedule")
            else:
                text = _("Partial schedule")
            url = reverse("admin:cayuman_studentcycle_workshops", kwargs={"object_id": obj.id, "period_id": Period.objects.current().id})
            return format_html(f'<a href="{url}">{text} ({len(wps)})</a>')
        else:
            return _("No workshops yet")

    @admin.display(description=_("Workshops %s") % (Period.objects.current()))
    def this_period_workshops_list(self, obj):
        """Display function to use when exporting these entries to CSV"""
        wps = obj.workshop_periods_by_period(Period.objects.current())
        if wps:
            return ", ".join([wp.workshop.name for wp in wps])
        else:
            return ""

    @admin.display(description=_("Previous Periods Workshops"))
    def previous_periods_workshops(self, obj):
        current_period = Period.objects.current()
        period = Period.objects.exclude(id=current_period.id).order_by("-id").first()
        if period:
            return format_html(
                f'<a href="{reverse("admin:cayuman_studentcycle_workshops", kwargs={"object_id": obj.id, "period_id": 1})}">'
                f'{_("Workshops %s") % (period)}'
                "</a>"
            )

    @admin.display(boolean=True, description=_("Active"))
    def active(self, obj):
        return obj.is_current()

    def get_urls(self):
        """Add url for custom `students_cycle` view"""
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
                "<path:object_id>/workshop_periods/<path:period_id>",
                wrap(self.student_cycle_workshop_periods_view),
                name="%s_%s_workshops" % info,  # cayuman_studentcycle_workshops
            ),
        ]
        return new_urls + urls

    def student_cycle_workshop_periods_view(self, request, object_id, period_id, extra_context=None):
        """Admin view workshop periods per student cycle"""
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

        period = Period.objects.get(id=period_id)

        # Then get students for this object.
        workshop_periods_list = list(obj.workshop_periods_by_period(period))

        paginator = self.get_paginator(request, workshop_periods_list, 100)
        page_number = request.GET.get(PAGE_VAR, 1)
        page_obj = paginator.get_page(page_number)
        page_range = paginator.get_elided_page_range(page_obj.number)

        context = {
            **self.admin_site.each_context(request),
            "title": _("Workshop Periods %s for: %s") % (period, obj),
            "subtitle": None,
            "workshop_periods_list": page_obj,
            "period": period,
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
            "admin/student_cycle_workshop_periods.html",
            context,
        )


admin.site.register(StudentCycle, StudentCycleAdmin)
