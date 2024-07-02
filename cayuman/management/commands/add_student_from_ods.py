#!/usr/bin/env python
"""Helper script for initial members load from ods file."""
import csv

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


# Convert csv table to row-dict list, fix time coordinates and teacher
def from_csv_table(fname):
    with open(fname, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        t = [row for row in reader]
        # for row in t:
        return t


class Command(BaseCommand):
    help = "Initial members load from ods file."

    def add_arguments(self, parser):
        parser.add_argument("filename")

    def handle(self, *args, **options):
        filename = options["filename"]
        try:
            t = from_csv_table(filename)
        except FileNotFoundError:
            raise CommandError('File "%s" does not exist' % filename)

        self.stdout.write(self.style.SUCCESS(f"Read {len(t)} entries"))
        t = [row for row in t if row["cycle"] in cycle_name]
        self.stdout.write(self.style.SUCCESS(f"Filtering to {len(t)} entries"))
        students_group, _ = Group.objects.get_or_create(name=settings.STUDENTS_GROUP)
        for row in t:
            member, created = Member.objects.get_or_create(username=row["rut"])
            if created:
                member.first_name = row["sfname"]
                member.last_name = row["slname"]
                member.email = row["email"]
                member.set_password(row["rut"].split("-")[0][-4:])
                member.save()
            else:
                self.stdout.write(self.style.WARNING(f"Updating preexisting Member object groups: {member.first_name}, {member.username}"))
            # Force to student group
            member.groups.set([students_group])

            # Create student cycle relation if does not exist.
            cycle, created = Cycle.objects.get_or_create(name=cycle_name[row["cycle"]])
            try:
                StudentCycle.objects.get(student=member, cycle=cycle)
            except StudentCycle.DoesNotExist:
                StudentCycle.objects.create(student=member, cycle=cycle)
            else:
                self.stdout.write(f"{member.first_name}, {member.username} is already at {cycle.name}")
