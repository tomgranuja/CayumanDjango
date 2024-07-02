#!/usr/bin/env python
"""Helper script for initial members load from ods file."""
import csv

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from cayuman.models import Member


def g_email_sanation(email):
    host_list = ["gmail.com", "yahoo.com", "hotmail.com", "msn.com"]
    email = str(email).strip()
    if email != "" and "@" not in email:
        email += "@comunidadeducativacayuman.cl"
    if email.split("@")[-1].lower() in host_list:
        email = email.lower()
    return email


# Convert csv table to row-dict list, fix email and active to boolean
def from_csv_table(fname):
    with open(fname, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        t = [row for row in reader]
        for row in t:
            if row["active"] == "1":
                row["active"] = bool(row["active"])
            else:
                row["active"] = False
            row["email"] = g_email_sanation(row["email"])
        return t


class Command(BaseCommand):
    help = "Initial teacher load from ods file."

    def add_arguments(self, parser):
        parser.add_argument("filename")

    def handle(self, *args, **options):
        filename = options["filename"]
        try:
            t = from_csv_table(filename)
        except FileNotFoundError:
            raise CommandError('File "%s" does not exist' % filename)

        self.stdout.write(self.style.SUCCESS(f"Read {len(t)} entries"))
        t = [row for row in t if row["active"]]
        self.stdout.write(self.style.SUCCESS(f"Filtering to {len(t)} active entries"))
        teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
        for row in t:
            member, created = Member.objects.get_or_create(username=row["rut"])
            if created:
                member.first_name = row["gfname"]
                member.last_name = row["glname"]
                member.email = row["email"]
                member.is_staff = True
                member.set_password(row["rut"].split("-")[0][-4:])
                member.save()
            else:
                self.stdout.write(self.style.WARNING(f"Updating matching Member groups: {member.first_name}, {member.username}"))
            # Force to teachers group
            member.groups.set([teachers_group])
