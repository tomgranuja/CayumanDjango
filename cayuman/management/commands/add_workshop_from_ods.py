#!/usr/bin/env python
"""Helper script for initial members load from ods file."""
import datetime

import pandas as pd
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import Period
from cayuman.models import Schedule
from cayuman.models import Workshop
from cayuman.models import WorkshopPeriod

DAYS_LIST = [t[0] for t in Schedule.CHOICES]
TIMES_LIST = [("10:15", "11:15"), ("12:30", "13:30")]

# Not used, period is created manually.
# Period number is readed from second command line argument.
# PERIOD = 1
# DATE_START = "2024-04-01"
# DATE_END = "2024-05-10"
# ENROLLMENT_START = "2024-03-01"


teacher_username = {
    "Paula": "8325281-2",
    "Marcelo": "9405393-5",
    "Alejandro": "17801870-1",
    "Francisca U.": "18059647-k",
    "Grace": "17838740-5",
    "Carla": "16440581-8",
    "Cristina": "16994402-4",
    "Francisca G.": "20638262-7",
    "Javiera": "17788558-4",
    "Paulina": "15696924-9",
    "Salvador": "15971521-3",
}

cycle_pairs = {"ulmos": ["Ulmos"], "canelos y manios": ["Canelos", "Mañíos"], "coihues y avellanos": ["Coigües", "Avellanos"]}


# Convert ods table to dataframe and fix time coordinates
def ws_table(filename, drop_c=False, nan_names=None):
    t = pd.read_excel(filename, dtype={"period": "int"})
    if nan_names is not None:
        t.loc[t["name"].isna(), "name"] = nan_names
    t["coords"] = t.loc[:, "c1":"c3"].apply(row_coords, axis=1)
    t.teacher = t.teacher.apply(lambda x: teacher_username[x])
    if drop_c:
        t = t.drop(columns=t.loc[:, "c1":"c3"].columns)
    return t


def tup_from_cell_coord(s):
    assert isinstance(s, str)
    day_idx = {
        "lu": 0,
        "ma": 1,
        "mi": 2,
        "ju": 3,
        "vi": 4,
    }
    d, h = s[:2], s[2:]
    return (int(h) - 1, day_idx[d.lower()])


def row_coords(row):
    r = row[row.notna()]
    return r.apply(tup_from_cell_coord).to_list()


def coord_to_dict(coord):
    t_idx, d_idx = coord
    from_iso = datetime.time.fromisoformat
    time_start = from_iso(TIMES_LIST[t_idx][0])
    time_end = from_iso(TIMES_LIST[t_idx][1])
    return {
        "day": DAYS_LIST[d_idx],
        "time_start__hour": time_start.hour,
        "time_start__minute": time_start.minute,
        "time_end__hour": time_end.hour,
        "time_end__minute": time_end.minute,
    }


class Command(BaseCommand):
    help = "Initial workshop load from ods file."

    def add_arguments(self, parser):
        parser.add_argument("filename")
        parser.add_argument("period_n", type=int)

    def handle(self, *args, **options):
        filename = options["filename"]
        period_n = options["period_n"]
        try:
            t = ws_table(filename, drop_c=True, nan_names="Not defined")
        except FileNotFoundError:
            raise CommandError('File "%s" does not exist' % filename)

        self.stdout.write(self.style.SUCCESS(f"Read {len(t)} entries"))
        t = t[t.period == period_n]
        self.stdout.write(self.style.SUCCESS(f"Filtering to {len(t)} entries of period {period_n}."))

        teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)

        try:
            period = Period.objects.get(name=f"Periodo {period_n}")
            print(f"Selecting period {period}.")
        except Period.DoesNotExist:
            message = f"Period {period_n} doesn't exist, " "stopping without touching database."
            raise CommandError(message)

        for i, row in t.iloc[:].iterrows():
            print(f"Adding entry at index {i}, {row['name']}...")
            # Find database workshopperiod with same workshop, period and teacher

            # Teacher
            teacher, created = Member.objects.get_or_create(username=row.teacher)
            if created:
                teacher.first_name = "No name"
                teacher.last_name = "workshop teacher"
                teacher.save()
                teacher.groups.set([teachers_group])
                print(f"    {repr(teacher)} created.")

            # Workshop
            defaults = {}
            if pd.notna(row["description"]):
                defaults["description"] = row["description"]
            if pd.notna(row["full_name"]):
                defaults["full_name"] = row["full_name"]
            ws, created = Workshop.objects.update_or_create(name=row["name"], defaults=defaults)
            if not created:
                print(f"    {repr(ws)} updated.")

            # Schedules

            schedules = [Schedule.objects.get_or_create(**coord_to_dict(coord)) for coord in row.coords]
            for sc, created in schedules:
                if created:
                    print(f"    {repr(sc)} created.")
            schedules = [sc[0] for sc in schedules]

            # Cycle
            cycles = [Cycle.objects.get_or_create(name=name) for name in cycle_pairs[row.cycle]]
            for cycle, created in cycles:
                if created:
                    print(f"    {repr(cycle)} created.")
            cycles = [t[0] for t in cycles]

            # WorkshopPeriod
            try:
                q = WorkshopPeriod.objects.filter(workshop=ws, period=period, teacher=teacher, cycles__in=cycles)
                # cycles_in creates duplicates
                wp = q.distinct().get()
                print(f"    Find preexisting: {wp}...")
                wp.cycles.clear()
                wp.schedules.clear()
                print("    Schedules and cycles cleared:")
                print(f"        Schedules: {wp.schedules.all()}")
                print(f"        Cycles: {wp.cycles.all()}")
            except WorkshopPeriod.DoesNotExist:
                wp = WorkshopPeriod.objects.create(workshop=ws, period=period, teacher=teacher)
            finally:
                wp.max_students = row.quota
                wp.save()
            wp.cycles.add(*cycles)
            wp.schedules.add(*schedules)

            print()
