"""Landing page, gallery and photo-access tests."""
import shutil
import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.catalog.models import GalleryPhoto
from apps.core.testing import PASSWORD, make_customer, make_service, make_user
from apps.jobs import services as job_services

TMP_MEDIA = tempfile.mkdtemp(prefix="carwash-test-media-")


def jpeg_bytes():
    buf = BytesIO()
    Image.new("RGB", (8, 8), "teal").save(buf, "JPEG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class LandingTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def photo(self, title, **kw):
        p = GalleryPhoto(title=title, **kw)
        p.image.save(f"{title}.jpg", ContentFile(jpeg_bytes()), save=False)
        p.save()
        return p

    def get(self):
        return self.client.get(reverse("dashboard:landing"))

    def test_empty_database_renders_without_fake_content(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Our price list is coming soon")
        self.assertNotContains(response, 'id="gallery"')
        self.assertNotContains(response, "lp-stats")  # no invented numbers

    def test_default_hero_image_is_used_when_no_photo_is_featured(self):
        response = self.get()
        self.assertContains(response, "img/hero-800.webp")
        self.assertContains(response, 'fetchpriority="high"', count=1)
        self.assertContains(response, "Safi Wash")

    def test_service_tabs_and_cards_use_category_icons(self):
        make_service("Wash", "exterior")
        make_service("Vacuum", "interior")
        response = self.get()
        self.assertContains(response, "icons.svg#droplets")
        self.assertContains(response, "icons.svg#wind")

    def test_services_grouped_into_tabs_with_prices(self):
        make_service("Basic wash", "exterior", "500")
        make_service("Vacuum", "interior", "400")
        response = self.get()
        self.assertContains(response, 'role="tab"', count=2)
        self.assertContains(response, "Basic wash")
        self.assertContains(response, "KES 400.00")

    def test_inactive_services_are_hidden(self):
        s = make_service("Secret")
        s.is_active = False
        s.save()
        self.assertNotContains(self.get(), "Secret")

    def test_stats_only_show_real_values_and_singular_labels(self):
        make_service()
        make_customer()
        response = self.get()
        self.assertContains(response, "Happy customer<")
        self.assertContains(response, "Service on offer<")
        self.assertNotContains(response, "Cars washed")  # zero -> dropped

    def test_hero_is_newest_featured_and_prioritised(self):
        self.photo("older", is_featured=True)
        newest = self.photo("newest", is_featured=True)
        self.photo("plain")
        response = self.get()
        self.assertEqual(response.context["hero_photo"], newest)
        self.assertContains(response, 'fetchpriority="high"', count=1)
        self.assertContains(response, 'loading="lazy"', count=4)  # 3 gallery photos + the footer logo, never the hero

    def test_inactive_photo_not_shown(self):
        self.photo("hidden", is_active=False)
        self.assertNotContains(self.get(), 'id="gallery"')

    def test_logged_in_users_are_redirected_away(self):
        user = make_user("manager")
        self.client.login(username=user.username, password=PASSWORD)
        self.assertRedirects(self.get(), reverse("dashboard:home"))

    def test_jsonld_cannot_break_out_of_script_tag(self):
        with self.settings(BUSINESS={**__import__("django.conf").conf.settings.BUSINESS, "name": "</script><b>x"}):
            body = self.get().content.decode()
        self.assertNotIn("</script><b>", body)

    def test_gallery_media_is_public_but_job_photos_are_not_routed(self):
        p = self.photo("pub")
        self.assertEqual(self.client.get(p.image.url).status_code, 200)
        self.assertEqual(self.client.get("/media/job_photos/2026/01/x.jpg").status_code, 404)

    def test_photo_size_validator(self):
        big = SimpleUploadedFile("big.jpg", b"0" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            GalleryPhoto._meta.get_field("image").run_validators(big)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class JobPhotoAccessTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.worker = make_user("worker")
        self.owner, vehicle = make_customer(with_login=True)
        self.stranger, _ = make_customer(with_login=True)
        job = job_services.create_job(
            customer=self.owner, vehicle=vehicle, services=[make_service()], created_by=self.manager,
            assigned_worker=self.worker.worker_profile,
        )
        self.line = job.job_services.first()
        self.line.photo.save("car.jpg", ContentFile(jpeg_bytes()))
        self.url = reverse("jobs:service_photo", args=[job.pk, self.line.pk])

    def status_for(self, user):
        self.client.logout()
        if user:
            self.client.login(username=user.username, password=PASSWORD)
        return self.client.get(self.url).status_code

    def test_allowed(self):
        for user in (self.manager, self.worker, self.owner.user):
            with self.subTest(user=user.role):
                self.assertEqual(self.status_for(user), 200)

    def test_other_customer_gets_404(self):
        self.assertEqual(self.status_for(self.stranger.user), 404)

    def test_anonymous_is_sent_to_login(self):
        self.assertEqual(self.status_for(None), 302)
