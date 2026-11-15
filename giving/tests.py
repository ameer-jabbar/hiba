import csv
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from giving.models import DonationTransaction, Donor
from giving.services import PayPalImportError, import_paypal_csv

HEADERS = [
    "Date",
    "Name",
    "Type",
    "Status",
    "Currency",
    "Gross",
    "Transaction ID",
    "From Email Address",
    "Contact Phone Number",
    "Subscription ID",
    "Direction",
]


def csv_content(*rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADERS)
    writer.writerows(rows)
    return output.getvalue()


def donation_row(
    transaction_id="TX-1",
    name="Sam Donor",
    email="sam@example.com",
    transaction_type="Donation",
    status="Completed",
    amount="25.00",
    date="01/15/2025",
    subscription_id="",
    phone="555-0100",
    direction="Incoming",
):
    return [
        date,
        name,
        transaction_type,
        status,
        "USD",
        amount,
        transaction_id,
        email,
        phone,
        subscription_id,
        direction,
    ]


class PayPalImportTests(TestCase):
    def test_imports_recurring_and_one_off_transactions_for_one_donor(self):
        content = csv_content(
            donation_row(transaction_id="ONCE", amount="15.00"),
            donation_row(
                transaction_id="MONTHLY",
                email="SAM@example.com",
                transaction_type="Subscription Payment",
                date="2025-02-15",
                subscription_id="I-SUBSCRIPTION",
            ),
        )

        result = import_paypal_csv(content.encode("utf-8-sig"))

        donor = Donor.objects.get()
        transactions = list(
            DonationTransaction.objects.order_by("paypal_transaction_id")
        )
        self.assertEqual(result.imported, 2)
        self.assertEqual(Donor.objects.count(), 1)
        self.assertEqual(donor.email, "sam@example.com")
        self.assertEqual([item.is_recurring for item in transactions], [True, False])
        self.assertEqual(transactions[0].amount, Decimal("25.00"))
        self.assertEqual(transactions[1].amount, Decimal("15.00"))

    def test_existing_duplicate_is_skipped_without_updating_donor_or_transaction(self):
        import_paypal_csv(csv_content(donation_row()).encode())
        content = csv_content(
            donation_row(
                name="Changed Name",
                email="changed@example.com",
                amount="not-an-amount",
                phone="555-9999",
            ),
            donation_row(
                transaction_id="TX-2", email="SAM@example.com", amount="10.00"
            ),
        )

        result = import_paypal_csv(content.encode())

        self.assertEqual(result.imported, 1)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(Donor.objects.count(), 1)
        self.assertEqual(Donor.objects.get().name, "Sam Donor")
        self.assertEqual(DonationTransaction.objects.count(), 2)

    def test_duplicate_transaction_id_within_file_is_only_imported_once(self):
        result = import_paypal_csv(
            csv_content(donation_row(), donation_row(amount="invalid")).encode()
        )

        self.assertEqual(result.imported, 1)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(DonationTransaction.objects.count(), 1)

    def test_invalid_eligible_row_rolls_back_the_entire_file(self):
        content = csv_content(
            donation_row(transaction_id="VALID"),
            donation_row(transaction_id="INVALID", amount="not-an-amount"),
        )

        with self.assertRaises(PayPalImportError):
            import_paypal_csv(content.encode())

        self.assertEqual(Donor.objects.count(), 0)
        self.assertEqual(DonationTransaction.objects.count(), 0)

    def test_skips_outgoing_non_completed_and_non_donation_activity(self):
        content = csv_content(
            donation_row(transaction_id="OUT", direction="Outgoing"),
            donation_row(transaction_id="PENDING", status="Pending"),
            donation_row(transaction_id="PAYMENT", transaction_type="Payment Sent"),
            donation_row(transaction_id="DONATION", amount="5.00"),
        )

        result = import_paypal_csv(content.encode())

        self.assertEqual(result.imported, 1)
        self.assertEqual(result.ignored, 3)
        self.assertEqual(
            DonationTransaction.objects.get().paypal_transaction_id, "DONATION"
        )

    def test_rejects_missing_donor_email_on_an_eligible_row(self):
        with self.assertRaisesRegex(PayPalImportError, "donor email is required"):
            import_paypal_csv(csv_content(donation_row(email="")).encode())
        self.assertEqual(Donor.objects.count(), 0)

    def test_rejects_unsupported_csv_headers(self):
        with self.assertRaisesRegex(
            PayPalImportError, "missing required PayPal columns"
        ):
            import_paypal_csv("Name,Email\nSam,sam@example.com".encode())


class PayPalUploadViewTests(TestCase):
    def setUp(self):
        self.url = reverse("paypal-import")

    def test_upload_requires_staff_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

        user = get_user_model().objects.create_user(
            username="member", password="password"
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_can_upload_csv(self):
        staff_user = get_user_model().objects.create_user(
            username="staff", password="password", is_staff=True
        )
        self.client.force_login(staff_user)
        upload = SimpleUploadedFile(
            "paypal.csv", csv_content(donation_row()).encode(), content_type="text/csv"
        )

        response = self.client.post(self.url, {"file": upload})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Imported 1 donation(s)")
        self.assertEqual(DonationTransaction.objects.count(), 1)
