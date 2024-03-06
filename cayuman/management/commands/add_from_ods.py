#!/usr/bin/env python
"""Helper script for initial members load from ods file."""
import pandas as pd
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from cayuman.models import Cycle
from cayuman.models import Member
from cayuman.models import StudentCycle

cycle_name = {
    "ulmos": "Ulmos",
    "canelos": "Canelos",
    "manios": "Mañios",
    "coihues": "Coigües",
    "avellanos": "Avellanos",
}


class Command(BaseCommand):
    help = "Initial members load from ods file."

    def add_arguments(self, parser):
        parser.add_argument("filename")

    def handle(self, *args, **options):
        filename = options["filename"]
        try:
            t = pd.read_excel(filename)
        except FileNotFoundError:
            raise CommandError('File "%s" does not exist' % filename)

        self.stdout.write(self.style.SUCCESS(f"Read {len(t)} entries"))
        t = t[t.cycle.isin(cycle_name)]
        self.stdout.write(self.style.SUCCESS(f"Filtering to {len(t)} entries"))
        students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        for i, row in t.iterrows():
            q = Member.objects.filter(username=row.rut)
            if q.exists():
                member = q.first()
                self.stdout.write(self.style.WARNING(f"Preexisting Member object: {member.first_name}, {member.username}"))
            else:
                member = Member.objects.create(
                    username=row.rut,
                    first_name=row.sfname,
                    last_name=row.slname,
                    email=row.email,
                )
                member.set_password(row.rut.split("-")[0][-4:])
                member.save()
            # Force to student group
            member.groups.set([students_group])

            # Update student cycle relation
            cycle, _ = Cycle.objects.get_or_create(name=cycle_name[row.cycle])
            if member.studentcycle_set.exists():
                member.studentcycle_set.first().cycle = cycle
            else:
                StudentCycle.objects.create(student=member, cycle=cycle)
