from django.contrib import admin
from django.utils.html import format_html

from .models import Cycle
from .models import Member
from .models import Schedule
from .models import StudentCycle
from .models import Workshop
from .models import WorkshopPeriod


class MemberAdmin(admin.ModelAdmin):
    date_hierarchy = "user__date_joined"
    list_display = ("id", "name", "user", "cycle", "date_joined", "is_student", "is_teacher", "is_staff", "is_active")
    # exclude = ["shared"]
    # search_fields = ['url', 'entity_url', 'entity_ancestor_url', 'entity_url_type', 'entity_ancestor_url_type', 'entity', 'session']
    list_per_page = 20
    # list_filter = ["entity_url_type", "entity_ancestor_url_type"]

    def name(self, obj):
        return format_html(f'<a href="/admin/auth/user/{obj.user.id}/change/">{obj.user.first_name} {obj.user.last_name}</a>')

    def date_joined(self, obj):
        return format_html(str(obj.user.date_joined.strftime("%B %d, %Y"))) if obj.user.date_joined else "-"

    def is_student(self, obj):
        return format_html(
            '<img src="/static/admin/img/icon-yes.svg" alt="True">' if obj.is_student else '<img src="/static/admin/img/icon-no.svg" alt="False">'
        )

    def is_teacher(self, obj):
        return format_html(
            '<img src="/static/admin/img/icon-yes.svg" alt="True">' if obj.is_teacher else '<img src="/static/admin/img/icon-no.svg" alt="False">'
        )

    def is_staff(self, obj):
        return format_html(
            '<img src="/static/admin/img/icon-yes.svg" alt="True">' if obj.user.is_staff else '<img src="/static/admin/img/icon-no.svg" alt="False">'
        )

    def is_active(self, obj):
        return format_html(
            '<img src="/static/admin/img/icon-yes.svg" alt="True">' if obj.user.is_active else '<img src="/static/admin/img/icon-no.svg" alt="False">'
        )

    def cycle(self, obj):
        return format_html(obj.current_cycle.cycle.name if obj.current_cycle else "-")


admin.site.register(Member, MemberAdmin)


class CycleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    list_per_page = 20


admin.site.register(Cycle, CycleAdmin)


class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "day", "time_start", "time_end")
    list_per_page = 20


admin.site.register(Schedule, ScheduleAdmin)


class WorkshopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    list_per_page = 20


admin.site.register(Workshop, WorkshopAdmin)


class WorkshopPeriodAdmin(admin.ModelAdmin):
    list_display = ("id", "workshop", "teacher", "date_start", "date_end", "cycles_list", "schedules_list", "max_students")
    list_per_page = 20
    filter_horizontal = ("cycles", "schedules")

    def cycles_list(self, obj):
        return ", ".join([cycle.name for cycle in obj.cycles.all()])

    def schedules_list(self, obj):
        return ", ".join([str(schedule) for schedule in obj.schedules.all()])


admin.site.register(WorkshopPeriod, WorkshopPeriodAdmin)


class StudentCycleAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "cycle", "workshop_periods_list", "date_joined")
    list_per_page = 20
    filter_horizontal = ("workshop_periods",)

    def workshop_periods_list(self, obj):
        return format_html("<ul><li>{}</li></ul>".format("</li><li>".join([str(period) for period in obj.workshop_periods.all()])))


admin.site.register(StudentCycle, StudentCycleAdmin)
