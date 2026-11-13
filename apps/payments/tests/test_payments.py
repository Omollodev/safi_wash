from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.testing import PASSWORD, make_customer, make_service, make_user
from apps.jobs import services as job_services
from apps.payments import services
from apps.payments.models import MpesaRequest, Payment
from apps.payments.services import PaymentError


class PaymentBase(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.customer, self.vehicle = make_customer(with_login=True)
        self.job = job_services.create_job(
            customer=self.customer, vehicle=self.vehicle, services=[make_service(price="1000")],
            created_by=self.manager,
        )


class CashTests(PaymentBase):
    def test_partial_then_full_payment(self):
        self.assertEqual(self.job.payment_status, "pending")
        services.record_cash_payment(self.job, "400", self.manager)
        self.assertEqual(self.job.payment_status, "partial")
        self.assertEqual(self.job.balance_due, Decimal("600"))
        services.record_cash_payment(self.job, "600", self.manager)
        self.assertEqual(self.job.payment_status, "paid")

    def test_overpayment_and_bad_amounts_rejected(self):
        for bad in ["1001", "0", "-5", "abc", ""]:
            with self.assertRaises(PaymentError, msg=bad):
                services.record_cash_payment(self.job, bad, self.manager)
        self.assertEqual(Payment.objects.count(), 0)

    def test_refund(self):
        services.record_cash_payment(self.job, "1000", self.manager)
        with self.assertRaises(PaymentError):
            services.record_refund(self.job, "1500", self.manager)
        services.record_refund(self.job, "1000", self.manager)
        self.assertEqual(self.job.payment_status, "refunded")

    def test_cancelled_job_takes_no_payment(self):
        job_services.cancel_job(self.job, self.manager)
        with self.assertRaises(PaymentError):
            services.record_cash_payment(self.job, "100", self.manager)


@override_settings(MPESA_MODE="fake", MPESA_CALLBACK_TOKEN="s3cret-token")
class MpesaTests(PaymentBase):
    def start(self, amount="1000"):
        return services.start_mpesa_payment(self.job, "0712345678", amount, self.customer.user)

    def test_phone_is_normalised_and_validated(self):
        self.assertEqual(self.start().phone, "254712345678")
        with self.assertRaises(PaymentError):
            services.start_mpesa_payment(self.job, "12345", "100", self.customer.user)

    def test_success_creates_one_payment_even_if_callback_repeats(self):
        req = self.start()
        for _ in range(3):
            services.handle_mpesa_result(req.checkout_request_id, 0, "ok", receipt="ABC123", paid_amount=1000)
        self.assertEqual(Payment.objects.filter(method="mpesa").count(), 1)
        self.assertEqual(self.job.payment_status, "paid")

    def test_failed_payment_changes_nothing(self):
        req = self.start()
        services.handle_mpesa_result(req.checkout_request_id, 1032, "Cancelled")
        req.refresh_from_db()
        self.assertEqual(req.status, "failed")
        self.assertEqual(Payment.objects.count(), 0)

    def test_amount_mismatch_is_rejected(self):
        req = self.start()
        services.handle_mpesa_result(req.checkout_request_id, 0, "ok", receipt="XYZ", paid_amount=1)
        req.refresh_from_db()
        self.assertEqual(req.status, "failed")
        self.assertEqual(Payment.objects.count(), 0)

    def test_replayed_receipt_cannot_pay_twice(self):
        first, second = self.start("400"), self.start("400")
        services.handle_mpesa_result(first.checkout_request_id, 0, "ok", receipt="SAME", paid_amount=400)
        services.handle_mpesa_result(second.checkout_request_id, 0, "ok", receipt="SAME", paid_amount=400)
        self.assertEqual(Payment.objects.count(), 1)

    def test_callback_url_requires_secret_token(self):
        req = self.start()
        body = {"Body": {"stkCallback": {
            "CheckoutRequestID": req.checkout_request_id, "ResultCode": 0, "ResultDesc": "ok",
            "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": 1000}, {"Name": "MpesaReceiptNumber", "Value": "REAL1"}]},
        }}}
        bad = self.client.post(reverse("payments:mpesa_callback", args=["wrong"]), body, content_type="application/json")
        self.assertEqual(bad.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)
        good = self.client.post(reverse("payments:mpesa_callback", args=["s3cret-token"]), body, content_type="application/json")
        self.assertEqual(good.status_code, 200)
        self.assertEqual(Payment.objects.get().reference, "REAL1")

    @override_settings(MPESA_CALLBACK_TOKEN="")
    def test_callback_disabled_when_no_token_configured(self):
        res = self.client.post(reverse("payments:mpesa_callback", args=["anything"]), {}, content_type="application/json")
        self.assertEqual(res.status_code, 404)

    def test_other_customer_cannot_pay_or_poll_my_job(self):
        stranger = make_user("customer")
        self.client.login(username=stranger.username, password=PASSWORD)
        res = self.client.post(reverse("payments:mpesa_start", args=[self.job.pk]), {"phone": "0712345678", "amount": "100"})
        self.assertEqual(res.status_code, 404)
        req = self.start()
        self.assertEqual(self.client.get(reverse("payments:mpesa_status", args=[req.pk])).status_code, 404)

    def test_owner_can_simulate_in_fake_mode(self):
        req = self.start()
        self.client.login(username=self.customer.user.username, password=PASSWORD)
        self.client.post(reverse("payments:mpesa_simulate", args=[req.pk]), {"outcome": "ok"})
        req.refresh_from_db()
        self.assertEqual(req.status, MpesaRequest.Status.SUCCESS)

    @override_settings(MPESA_MODE="sandbox")
    def test_simulator_is_disabled_outside_fake_mode(self):
        req = self.job.mpesa_requests.create(
            checkout_request_id="x1", phone="254712345678", amount=Decimal("100")
        )
        self.client.login(username=self.customer.user.username, password=PASSWORD)
        res = self.client.post(reverse("payments:mpesa_simulate", args=[req.pk]), {"outcome": "ok"})
        self.assertEqual(res.status_code, 404)
