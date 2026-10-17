"""LOCAL DEMO ONLY: synthetic VC + two Deans (CSE, ECE). Refused unless DEBUG=1.

Passwords are random and written to the git-ignored .work/demo-credentials.txt, not printed to docs or git.
No achievements or report content are created.
"""
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.catalogue.models import Department

DEMO = (("demo.vc", "VC", None, "Demo Vice-Chancellor"),
        ("demo.dean.cse", "DEAN", "CSE", "Demo Dean CSE"),
        ("demo.dean.ece", "DEAN", "ECE", "Demo Dean ECE"))


class Command(BaseCommand):
    help = "Create synthetic local demo accounts (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("--credentials", help="Write credentials here instead of .work/demo-credentials.txt "
                                                  "(the isolated browser-test database uses its own file).")

    def handle(self, *args, **o):
        if not settings.DEBUG:
            raise CommandError("seed_demo is for local development only (DEBUG=1).")
        lines = []
        for username, role, dept, name in DEMO:
            password = secrets.token_urlsafe(10)
            user = User.objects.filter(username=username).first()
            if user is None:
                if role == "VC" and User.objects.filter(role="VC", is_active=True).exists():
                    raise CommandError("A non-demo VC is active; demo accounts not created.")
                user = User(username=username, role=role, first_name=name,
                            department=Department.objects.get(code=dept) if dept else None)
            user.must_change_password = False
            user.set_password(password)
            user.save()
            lines.append(f"{role:5} {username:16} {password}")
        out = Path(o["credentials"]) if o.get("credentials") else Path(settings.PROJECT_ROOT) / ".work" / "demo-credentials.txt"
        out.parent.mkdir(exist_ok=True)
        out.write_text("SYNTHETIC LOCAL DEMO ACCOUNTS — not for production\n" + "\n".join(lines) + "\n")
        self.stdout.write(f"Demo accounts ready; credentials written to {out}")
