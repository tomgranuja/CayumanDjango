from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Member
from .models import Period
from .models import Schedule


@login_required(login_url="/accounts/login/")
def home(request):
    """Cayuman home - Show the enrollment form"""
    # fetch current period based on now() >= enrollment_date and now() < end_date
    now = datetime.now().date()
    try:
        p = Period.objects.get(enrollment_start__lte=now, date_end__gt=now)
    except Period.DoesNotExist:
        p = None

    ss = Schedule.objects.all()

    m = Member.objects.get(id=request.user.id)
    current_cycle = m.current_cycle.cycle

    # Prepare form data fetching available workshop period for this student's cycle
    wps_by_schedule = {}
    for s in ss:
        for wp in s.workshopperiod_set.filter(period=p):
            if current_cycle in wp.cycles.all():
                if s not in wps_by_schedule:
                    wps_by_schedule[s] = []
                wps_by_schedule[s].append(wp)

    return render(request, "home.html", {"period": p, "schedules": wps_by_schedule, "member": m})
