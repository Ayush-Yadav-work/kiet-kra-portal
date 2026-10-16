"""Operator account provisioning (plan 10, 13.6). Prints a one-time random password; forces change at first login.

  python manage.py provision_user --role DEAN --department CSE --username dean.cse --name "Full Name"
  python manage.py provision_user --role VC --username vc --name "Full Name"
  python manage.py provision_user --reset --username dean.cse      # new one-time password, ends sessions
  python manage.py provision_user --deactivate --username dean.cse
"""
import secrets

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.catalogue.models import Department


def end_sessions(user):
    for s in Session.objects.all():
        if s.get_decoded().get("_auth_user_id") == str(user.pk):
            s.delete()


class Command(BaseCommand):
    help = "Create, reset or deactivate a VC/Dean account."

    def add_arguments(self, p):
        p.add_argument("--username", required=True)
        p.add_argument("--role", choices=["VC", "DEAN"])
        p.add_argument("--department")
        p.add_argument("--name", default="")
        p.add_argument("--reset", action="store_true")
        p.add_argument("--deactivate", action="store_true")

    @transaction.atomic
    def handle(self, *args, **o):
        password = secrets.token_urlsafe(12)
        if o["reset"] or o["deactivate"]:
            try:
                user = User.objects.get(username=o["username"])
            except User.DoesNotExist:
                raise CommandError("No such user")
            if o["deactivate"]:
                user.is_active = False
                user.save(update_fields=["is_active"])
                end_sessions(user)
                self.stdout.write(f"Deactivated {user.username}; sessions ended.")
                return
            user.set_password(password)
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])
            end_sessions(user)
        else:
            if not o["role"]:
                raise CommandError("--role is required")
            dept = None
            if o["role"] == "DEAN":
                try:
                    dept = Department.objects.get(code=o["department"])
                except Department.DoesNotExist:
                    raise CommandError("--department must be an existing department code")
                if User.objects.filter(role="DEAN", department=dept, is_active=True).exists():
                    raise CommandError(f"{dept.code} already has an active Dean; deactivate them first.")
            elif User.objects.filter(role="VC", is_active=True).exists():
                raise CommandError("An active VC already exists; deactivate them first.")
            first, _, last = o["name"].partition(" ")
            user = User(username=o["username"], role=o["role"], department=dept, first_name=first, last_name=last,
                        must_change_password=True)
            user.set_password(password)
            user.save()
        # Shown once on the operator's terminal; never logged or stored.
        self.stdout.write(f"{user.username}: one-time password {password} (must be changed at first login)")
