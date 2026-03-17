from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create the single staff admin user (role=admin, is_staff=True). Use for initial setup only."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Admin email (login)")
        parser.add_argument("--password", required=True, help="Admin password")
        parser.add_argument("--first-name", default="Admin", help="First name")
        parser.add_argument("--last-name", default="Staff", help="Last name")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        first_name = (options.get("first_name") or "Admin").strip()
        last_name = (options.get("last_name") or "Staff").strip()

        if User.objects.filter(role="admin", is_staff=True).exists():
            self.stdout.write(self.style.WARNING("An admin user already exists. Skipping creation."))
            return

        if User.objects.filter(email__iexact=email).exists():
            user = User.objects.get(email__iexact=email)
            user.role = "admin"
            user.is_staff = True
            user.set_password(password)
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Updated existing user {email} to admin."))
        else:
            User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role="admin",
                is_staff=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Admin user created: {email}. Log in at /staff/login/"))
