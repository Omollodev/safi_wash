"""
python manage.py seed_demo

Creates sample services plus one demo user per role so you can click around
straight away. Passwords come from the DEMO_PASSWORD environment variable or
are generated randomly and printed ONCE -- nothing is hard-coded.
"""
import io
import os
import random
import secrets
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.catalog.models import GalleryPhoto, Service
from apps.customers.models import Customer, Vehicle
from apps.workforce.services import ensure_worker_profile

SERVICES = [
    ("Exterior wash", "exterior", 500, 20), ("Wheel & tyre clean", "exterior", 300, 15),
    ("Interior vacuum", "interior", 400, 20), ("Dashboard & seats wipe", "interior", 350, 20),
    ("Engine bay clean", "detailing", 800, 30), ("Wax & polish", "detailing", 1500, 45),
    ("Headlight restoration", "detailing", 1200, 40), ("Air freshener", "additional", 150, 5),
    ("Underbody wash", "additional", 600, 25),
]


SAMPLE_PHOTOS = [
    ("Sample: exterior shine", (14, 116, 144), (8, 47, 73)),
    ("Sample: interior detail", (30, 64, 175), (15, 23, 42)),
    ("Sample: wheels & tyres", (21, 94, 117), (12, 25, 38)),
    ("Sample: foam wash", (3, 105, 161), (7, 89, 133)),
    ("Sample: polish & wax", (55, 48, 163), (23, 37, 84)),
    ("Sample: engine bay", (22, 78, 99), (8, 51, 68)),
]


def make_sample_image(label, top, bottom, seed):
    """A clearly-labelled placeholder picture (soft gradient + bokeh). Replace with real photos in the admin."""
    from PIL import Image, ImageDraw, ImageFilter

    w, h = 960, 720
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(26):
        r = rnd.randint(18, 90)
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        c = rnd.randint(40, 120)
        gd.ellipse([x - r, y - r, x + r, y + r], fill=(c // 2, c, c + 40))
    img = Image.blend(img, Image.composite(glow.filter(ImageFilter.GaussianBlur(14)), img, glow.convert("L")), 0.55)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, h - 110, w - 40, h - 40], radius=18, fill=(0, 0, 0))
    d.text((70, h - 88), label + "  (replace in admin)", fill=(255, 255, 255))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=82)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Create demo services and demo users (one per role)."

    def add_arguments(self, parser):
        parser.add_argument("--sample-photos", action="store_true", help="Also add placeholder gallery photos")

    def handle(self, *args, **options):
        User = get_user_model()
        for i, (name, cat, price, mins) in enumerate(SERVICES):
            Service.objects.get_or_create(
                name=name,
                defaults={"category": cat, "price": Decimal(price), "estimated_duration": mins, "display_order": i},
            )

        password = os.environ.get("DEMO_PASSWORD") or secrets.token_urlsafe(10)
        created = []
        for username, role in [("admin_demo", "admin"), ("manager_demo", "manager"),
                               ("worker_demo", "worker"), ("customer_demo", "customer")]:
            user, was_new = User.objects.get_or_create(
                username=username,
                defaults={"role": role, "first_name": role.title(), "email": f"{username}@example.com", "phone": "0700000000"},
            )
            if was_new:
                user.set_password(password)
                user.save()
                created.append(username)
            if role == "worker":
                ensure_worker_profile(user)
            if role == "customer":
                customer, _ = Customer.objects.get_or_create(
                    user=user, defaults={"name": "Demo Customer", "phone": "0700000000", "email": user.email}
                )
                Vehicle.objects.get_or_create(
                    plate_number="KAA123A", defaults={"customer": customer, "make": "Toyota", "model": "Axio"}
                )
        if options["sample_photos"] and not GalleryPhoto.objects.exists():
            # First photo: the real interior-steam-cleaning shot shipped with the project (also the landing page default).
            hero = Path(settings.BASE_DIR) / "static" / "img" / "hero.webp"
            if hero.exists():
                photo = GalleryPhoto(title="Interior steam clean", alt_text="A detailer steam-cleans the dashboard of a red car", display_order=0, is_featured=True)
                photo.image.save("interior-steam-clean.webp", ContentFile(hero.read_bytes()), save=False)
                photo.save()
            for i, (label, top, bottom) in enumerate(SAMPLE_PHOTOS[1:], start=1):
                photo = GalleryPhoto(title=label.replace("Sample: ", "").capitalize(), display_order=i)
                photo.image.save(f"sample-{i + 1}.jpg", ContentFile(make_sample_image(label, top, bottom, i)), save=False)
                photo.save()
            self.stdout.write(self.style.WARNING("Added one real photo and placeholder gallery photos - replace the placeholders in /admin/."))
        self.stdout.write(self.style.SUCCESS(f"Services ready ({Service.objects.count()})."))
        if created:
            self.stdout.write(f"Created users: {', '.join(created)}")
            self.stdout.write(self.style.WARNING(f"Their password (shown once): {password}"))
        else:
            self.stdout.write("Demo users already existed; passwords unchanged.")
