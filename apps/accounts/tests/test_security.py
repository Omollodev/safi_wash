"""Access-control and sign-up tests. Read these to learn what the site protects against."""
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services import verify_email
from apps.accounts.tokens import make_verification_token
from apps.core.testing import PASSWORD, make_customer, make_service, make_user
from apps.jobs import services as job_services


class SignupTests(TestCase):
    data = {
        "username": "newbie", "first_name": "New", "last_name": "Bie", "email": "newbie@example.com",
        "phone": "0712345678", "password1": "Strong-pass-98765", "password2": "Strong-pass-98765",
    }

    def test_signup_requires_email_verification(self):
        res = self.client.post(reverse("portal:signup"), self.data)
        self.assertEqual(res.status_code, 200)
        user = User.objects.get(username="newbie")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(self.client.login(username="newbie", password=self.data["password1"]))
        token = make_verification_token(user)
        self.assertEqual(verify_email(token), user)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_signup_cannot_choose_a_role(self):
        self.client.post(reverse("portal:signup"), {**self.data, "role": "admin", "is_staff": "on", "is_superuser": "on"})
        user = User.objects.get(username="newbie")
        self.assertEqual(user.role, "customer")
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertTrue(user.customer)  # linked customer record was created

    def test_bad_verification_token(self):
        self.assertIsNone(verify_email("not-a-real-token"))

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="taken", email="newbie@example.com", password=PASSWORD)
        res = self.client.post(reverse("portal:signup"), self.data)
        self.assertFalse(User.objects.filter(username="newbie").exists())
        self.assertContains(res, "already exists")


class LoginTests(TestCase):
    def setUp(self):
        self.user = make_user("manager")

    def test_open_redirect_is_blocked(self):
        res = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": PASSWORD, "next": "https://evil.example/phish"},
        )
        self.assertRedirects(res, reverse("dashboard:home"), fetch_redirect_response=False)

    def test_safe_next_is_followed(self):
        res = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": PASSWORD, "next": reverse("jobs:list")},
        )
        self.assertRedirects(res, reverse("jobs:list"), fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.login(username=self.user.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(self.client.get(reverse("jobs:list")).status_code, 302)


class RoleAccessTests(TestCase):
    """Every row says: this role requesting this URL must get this status code."""

    def setUp(self):
        self.users = {r: make_user(r) for r in ("admin", "manager", "worker", "customer")}
        self.customer, self.vehicle = make_customer()
        self.job = job_services.create_job(
            customer=self.customer, vehicle=self.vehicle, services=[make_service()], created_by=self.users["manager"]
        )

    def get(self, role, url):
        self.client.logout()
        if role:
            self.client.login(username=self.users[role].username, password=PASSWORD)
        return self.client.get(url).status_code

    def test_matrix(self):
        cases = [
            # (url name, args, {role: expected status})
            ("customers:list", [], {None: 302, "customer": 403, "worker": 403, "manager": 200, "admin": 200}),
            ("catalog:list", [], {None: 302, "customer": 403, "worker": 403, "manager": 200}),
            ("workforce:list", [], {None: 302, "customer": 403, "worker": 403, "manager": 200}),
            ("dashboard:reports", [], {None: 302, "customer": 403, "worker": 403, "manager": 200}),
            ("accounts:user_list", [], {None: 302, "customer": 403, "worker": 403, "manager": 403, "admin": 200}),
            ("jobs:list", [], {None: 302, "customer": 403, "worker": 200, "manager": 200}),
            ("jobs:detail", [self.job.pk], {None: 302, "customer": 403, "worker": 200, "manager": 200}),
            ("jobs:create", [], {None: 302, "customer": 403, "worker": 403, "manager": 200}),
            ("jobs:api_board", [], {None: 302, "customer": 403, "worker": 200}),
            ("customers:vehicle_detail", [self.vehicle.pk], {None: 302, "customer": 403, "worker": 200}),
            ("customers:api_customers", [], {None: 302, "customer": 403, "worker": 403, "manager": 200}),
            ("workforce:my_jobs", [], {None: 302, "customer": 403, "manager": 403, "worker": 200}),
            ("portal:home", [], {None: 302, "worker": 403, "customer": 200}),
        ]
        for name, args, expectations in cases:
            for role, expected in expectations.items():
                with self.subTest(url=name, role=role):
                    self.assertEqual(self.get(role, reverse(name, args=args)), expected)

    def test_state_changing_urls_reject_get(self):
        self.client.login(username=self.users["manager"].username, password=PASSWORD)
        for name in ("jobs:change_status", "jobs:cancel", "jobs:assign_worker", "jobs:add_service"):
            self.assertEqual(self.client.get(reverse(name, args=[self.job.pk])).status_code, 405, name)


class CustomerIsolationTests(TestCase):
    """Customer A must never see customer B's data (no IDOR)."""

    def setUp(self):
        self.manager = make_user("manager")
        self.alice, self.alice_car = make_customer(with_login=True)
        self.bob, self.bob_car = make_customer(with_login=True)
        self.alice_job = job_services.create_job(
            customer=self.alice, vehicle=self.alice_car, services=[make_service()], created_by=self.manager)
        self.client.login(username=self.bob.user.username, password=PASSWORD)

    def test_bob_cannot_open_alices_job(self):
        self.assertEqual(self.client.get(reverse("portal:job_detail", args=[self.alice_job.pk])).status_code, 404)

    def test_bob_cannot_use_staff_job_pages(self):
        self.assertEqual(self.client.get(reverse("jobs:detail", args=[self.alice_job.pk])).status_code, 403)

    def test_bob_cannot_book_with_alices_vehicle(self):
        res = self.client.post(reverse("portal:book"), {"vehicle": self.alice_car.pk, "services": [make_service().pk]})
        self.assertEqual(res.status_code, 200)  # form re-rendered with an error
        self.assertEqual(self.bob.jobs.count(), 0)

    def test_bob_cannot_start_a_workflow_change(self):
        res = self.client.post(reverse("jobs:change_status", args=[self.alice_job.pk]), {"status": "in_progress"})
        self.assertEqual(res.status_code, 403)
        self.alice_job.refresh_from_db()
        self.assertEqual(self.alice_job.status, "waiting")


class PrivacyTests(TestCase):
    def test_customers_never_see_internal_notes(self):
        manager = make_user("manager")
        customer, vehicle = make_customer(with_login=True)
        job = job_services.create_job(customer=customer, vehicle=vehicle, services=[make_service()], created_by=manager)
        job.internal_notes = "TOP-SECRET-STAFF-NOTE"
        job.save()
        self.client.login(username=customer.user.username, password=PASSWORD)
        self.assertNotContains(self.client.get(reverse("portal:job_detail", args=[job.pk])), "TOP-SECRET-STAFF-NOTE")
