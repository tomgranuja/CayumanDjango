#!/usr/bin/env python
"""Helper script for initial members load from ods file."""
import pandas as pd
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from cayuman.models import Member


class Command(BaseCommand):
    help = "Initial teacher load from ods file."

    def add_arguments(self, parser):
        parser.add_argument("filename")

    def handle(self, *args, **options):
        filename = options["filename"]
        try:
            t = pd.read_excel(filename, dtype={"active": "bool"})
        except FileNotFoundError:
            raise CommandError('File "%s" does not exist' % filename)

        self.stdout.write(self.style.SUCCESS(f"Read {len(t)} entries"))
        t = t[t.active]
        self.stdout.write(self.style.SUCCESS(f"Filtering to {len(t)} active entries"))
        teachers_group, _ = Group.objects.get_or_create(name=settings.TEACHERS_GROUP)
        for i, row in t.iterrows():
            member, created = Member.objects.get_or_create(username=row.rut)
            if created:
                member.first_name = row.gfname
                member.last_name = row.glname
                member.email = row.email
                member.set_password(row.rut.split("-")[0][-4:])
                member.save()
            else:
                self.stdout.write(self.style.WARNING(f"Preexisting Member object: {member.first_name}, {member.username}"))
            # Force to techers group
            member.groups.set([teachers_group])
