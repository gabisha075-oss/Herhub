from datetime import time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from services.models import Area, Booking, Category, Provider, Review, Service

User = get_user_model()
DEMO_PASSWORD = "Demo@12345"

CATEGORIES = [
    ("Tailoring", "tailoring"),
    ("Boutique", "boutique"),
    ("Mehndi", "mehndi"),
    ("Aari Work", "aari-work"),
    ("Makeup Artist", "makeup-artist"),
    ("Nail Art", "nail-art"),
]

AREAS = ["Vadasery", "Kottar", "Chettikulam", "Parvathipuram", "Nagercoil Town"]

CUSTOMERS = [
    ("demo_priya", "Priya", "9000000101"),
    ("demo_divya", "Divya", "9000000102"),
    ("demo_anusha", "Anusha", "9000000103"),
]

PROVIDERS = [
    {
        "username": "demo_nila", "first_name": "Nila", "phone": "9000000001",
        "business_name": "Nila's Bridal Studio", "area": "Vadasery", "years": 6,
        "categories": ["makeup-artist"], "home_service": True, "bridal": True, "approved": True,
        "about": "I create natural, long-lasting bridal looks that feel like you. Every booking includes a personal consultation, skin prep and complete styling support.",
        "services": [
            ("Bridal Makeup", "Makeup, hair & saree draping", 8000, "makeup-artist"),
            ("Party Makeup", "Makeup & basic hairstyling", 2500, "makeup-artist"),
        ],
    },
    {
        "username": "demo_thendral", "first_name": "Thendral", "phone": "9000000002",
        "business_name": "Thendral Tailoring", "area": "Chettikulam", "years": 9,
        "categories": ["tailoring", "aari-work"], "home_service": False, "bridal": False, "approved": True,
        "about": "Perfect-fit blouses and detailed aari work, delivered on time.",
        "services": [
            ("Blouse Stitching", "Plain and princess-cut blouses", 450, "tailoring"),
            ("Aari Work Blouse", "Hand embroidered bridal and festive blouses", 1800, "aari-work"),
            ("Saree Falls & Pico", "Quick service", 120, "tailoring"),
        ],
    },
    {
        "username": "demo_malar", "first_name": "Malar", "phone": "9000000003",
        "business_name": "Malar Boutique", "area": "Kottar", "years": 5,
        "categories": ["boutique", "tailoring"], "home_service": True, "bridal": False, "approved": True,
        "about": "Custom stitching and designer wear for every occasion.",
        "services": [
            ("Custom Blouse", "Designer blouse with lining", 750, "boutique"),
            ("Lehenga Stitching", "Made to measure", 3500, "boutique"),
        ],
    },
    {
        "username": "demo_kayal", "first_name": "Kayal", "phone": "9000000004",
        "business_name": "Kayal Beauty Lounge", "area": "Kottar", "years": 4,
        "categories": ["makeup-artist", "nail-art"], "home_service": False, "bridal": True, "approved": True,
        "about": "Makeup, hair styling and nail art in a relaxed women-only studio.",
        "services": [
            ("Bridal Makeup", "Full bridal package", 6500, "makeup-artist"),
            ("Nail Extensions", "Gel extensions with nail art", 1200, "nail-art"),
        ],
    },
    {
        "username": "demo_sahana", "first_name": "Sahana", "phone": "9000000005",
        "business_name": "Sahana Mehndi Art", "area": "Parvathipuram", "years": 7,
        "categories": ["mehndi"], "home_service": True, "bridal": True, "approved": True,
        "about": "Traditional and modern mehndi designs for weddings and festivals.",
        "services": [
            ("Bridal Mehndi", "Full hands and feet", 3000, "mehndi"),
            ("Simple Mehndi", "One hand, quick design", 300, "mehndi"),
        ],
    },
    {
        "username": "demo_pending", "first_name": "Revathi", "phone": "9000000006",
        "business_name": "Pending Studio (awaiting approval)", "area": "Nagercoil Town", "years": 1,
        "categories": ["nail-art"], "home_service": False, "bridal": False, "approved": False,
        "about": "Shows what an unapproved provider looks like. Not visible to the public.",
        "services": [("Basic Manicure", "", 400, "nail-art")],
    },
]

# provider, customer, service index, status, day offset, hour, rating, comment
BOOKINGS = [
    ("demo_nila", "demo_priya", 0, "completed", -20, 9, 5, "Nila understood exactly what I wanted. The makeup stayed fresh through the whole wedding."),
    ("demo_nila", "demo_divya", 1, "completed", -12, 16, 5, "Quick, neat and very friendly. Booked her again for my sister."),
    ("demo_nila", "demo_anusha", 0, "completed", -35, 8, 4, "Lovely work. She arrived a little late but the result was worth it."),
    ("demo_thendral", "demo_priya", 1, "completed", -15, 11, 5, "The aari work on my blouse is beautiful and was delivered on time."),
    ("demo_thendral", "demo_divya", 0, "completed", -9, 10, 4, "Perfect fitting. Will order again."),
    ("demo_malar", "demo_anusha", 0, "completed", -18, 15, 5, "Great stitching quality and a fair price."),
    ("demo_sahana", "demo_divya", 1, "completed", -7, 17, 5, "Beautiful design and the colour lasted nearly a week."),
    ("demo_nila", "demo_priya", 0, "pending", 10, 9, None, ""),
    ("demo_nila", "demo_divya", 1, "accepted", 5, 16, None, ""),
    ("demo_kayal", "demo_anusha", 0, "pending", 14, 10, None, ""),
]


class Command(BaseCommand):
    help = "Create demo categories, providers, customers, bookings and reviews (safe to run again)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Run even when DEBUG is False. Creates accounts with a publicly known password!",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError(
                "DEBUG is False. Demo accounts use a known password, so this is blocked "
                "by default. Use --allow-production only if you really want demo data here."
            )

        categories = {
            slug: Category.objects.get_or_create(slug=slug, defaults={"name": name})[0]
            for name, slug in CATEGORIES
        }
        areas = {name: Area.objects.get_or_create(name=name)[0] for name in AREAS}

        customers = {}
        for username, first_name, phone in CUSTOMERS:
            customers[username] = self.get_user(username, first_name, phone, User.Role.CUSTOMER)

        providers, services = {}, {}
        for spec in PROVIDERS:
            user = self.get_user(spec["username"], spec["first_name"], spec["phone"], User.Role.PROVIDER)
            provider, _ = Provider.objects.get_or_create(
                user=user,
                defaults={
                    "business_name": spec["business_name"],
                    "area": areas[spec["area"]],
                    "about": spec["about"],
                    "years_experience": spec["years"],
                    "home_service": spec["home_service"],
                    "bridal_specialist": spec["bridal"],
                    "is_approved": spec["approved"],
                },
            )
            provider.categories.set([categories[slug] for slug in spec["categories"]])
            providers[spec["username"]] = provider
            services[spec["username"]] = []
            for name, description, price, slug in spec["services"]:
                service, _ = Service.objects.get_or_create(
                    provider=provider, name=name,
                    defaults={"category": categories[slug], "description": description, "price": price},
                )
                services[spec["username"]].append(service)

        if Booking.objects.filter(customer__username__startswith="demo_").exists():
            self.stdout.write("Demo bookings already exist, skipping them.")
        else:
            today = timezone.localdate()
            for p_name, c_name, index, status, offset, hour, rating, comment in BOOKINGS:
                provider = providers[p_name]
                booking = Booking.objects.create(
                    customer=customers[c_name],
                    provider=provider,
                    service=services[p_name][index],
                    date=today + timedelta(days=offset),
                    time=time(hour, 0),
                    venue=Booking.Venue.HOME if provider.home_service else Booking.Venue.STUDIO,
                    status=status,
                )
                if rating:
                    Review.objects.create(booking=booking, rating=rating, comment=comment)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"Password for every demo_* account: {DEMO_PASSWORD}")
        self.stdout.write("Customer: demo_priya   Provider: demo_nila")

    def get_user(self, username, first_name, phone, role):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first_name, "phone": phone, "role": role},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        return user