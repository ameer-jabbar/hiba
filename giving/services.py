import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from django.core.exceptions import ValidationError
from django.db import transaction

from giving.models import DonationTransaction, Donor, PaypalTransactionsUploadFile

log = logging.getLogger(__name__)


class PayPalImportError(Exception):
    pass


@dataclass(frozen=True)
class PayPalImportResult:
    imported: int
    duplicates: int
    ignored: int


@dataclass(frozen=True)
class DonationEntry:
    transaction_id: str
    email: str
    name: str
    phone: str
    date: date
    amount: Decimal
    currency: str
    transaction_type: str
    subscription_id: str
    is_recurring: bool


FIELD_ALIASES = {
    "transaction_id": ("transaction id", "txn id", "transaction_id"),
    "date": ("date", "transaction date"),
    "amount": ("gross", "amount"),
    "currency": ("currency",),
    "status": ("status",),
    "type": ("type", "transaction type"),
    "email": ("from email address", "payer email", "sender email", "email"),
    "name": ("name", "payer name", "from name"),
    "phone": ("contact phone number", "phone number", "phone"),
    "subscription_id": ("subscription id", "subscr id", "subscription_id"),
    "direction": ("direction",),
}
REQUIRED_FIELDS = ("transaction_id", "date", "amount", "currency", "status", "type")
DONATION_TYPES = {"subscription payment", "donation payment"}
NON_DONATION_MARKERS = (
    "refund",
    "reversal",
    "chargeback",
    "sent",
    "payout",
    "withdrawal",
)


def _column_map(headers):
    normalized_headers = {
        header.strip().casefold(): header for header in headers if header
    }
    columns = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized_headers:
                columns[field] = normalized_headers[alias]
                break

    missing = [field for field in REQUIRED_FIELDS if field not in columns]
    if missing:
        raise PayPalImportError(
            "CSV is missing required PayPal columns: " + ", ".join(missing) + "."
        )
    return columns


def _value(row, columns, field) -> str:
    column = columns.get(field)
    return (row.get(column) or "").strip() if column else ""


def _is_donation(row, columns) -> bool:
    status = _value(row, columns, "status").casefold()
    if status != "completed":
        return False

    direction = _value(row, columns, "direction").casefold()
    if direction in {"outgoing", "outbound", "sent", "payment sent"}:
        return False

    transaction_type = _value(row, columns, "type").casefold()
    if any(marker in transaction_type for marker in NON_DONATION_MARKERS):
        return False
    return transaction_type in DONATION_TYPES


def _parse_date(value, row_number) -> date:
    value = value.strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise PayPalImportError(
        f"Row {row_number}: unsupported transaction date {value!r}."
    )


def _parse_amount(value, row_number) -> Decimal:
    try:
        amount = Decimal(value.strip().replace(",", "").replace("$", ""))
    except (InvalidOperation, AttributeError):
        raise PayPalImportError(
            f"Row {row_number}: invalid gross amount {value!r}."
        ) from None
    if (
        not amount.is_finite()
        or amount <= 0
        or amount.as_tuple().exponent < -2
        or amount.adjusted() > 9
    ):
        raise PayPalImportError(
            f"Row {row_number}: gross amount must be positive with at most two decimals."
        )
    return amount


def _validated_donation(row, columns, row_number):
    transaction_id = _value(row, columns, "transaction_id")
    email = _value(row, columns, "email").casefold()
    name = _value(row, columns, "name")
    currency = _value(row, columns, "currency").upper()
    subscription_id = _value(row, columns, "subscription_id")
    transaction_type = _value(row, columns, "type")

    if not transaction_id:
        raise PayPalImportError(f"Row {row_number}: transaction ID is required.")
    if len(transaction_id) > 100:
        raise PayPalImportError(
            f"Row {row_number}: transaction ID must be at most 100 characters."
        )
    if not email:
        raise PayPalImportError(
            f"Row {row_number}: donor email is required to match transactions safely."
        )
    if not name:
        raise PayPalImportError(f"Row {row_number}: donor name is required.")
    if len(currency) != 3 or not currency.isalpha():
        raise PayPalImportError(
            f"Row {row_number}: currency must be a three-letter code."
        )
    if len(transaction_type) > 100:
        raise PayPalImportError(
            f"Row {row_number}: transaction type must be at most 100 characters."
        )
    if len(subscription_id) > 100:
        raise PayPalImportError(
            f"Row {row_number}: subscription ID must be at most 100 characters."
        )
    try:
        Donor(name=name, email=email, phone=_value(row, columns, "phone")).full_clean()
    except ValidationError as error:
        details = "; ".join(
            f'{field}: {", ".join(field_messages)}'
            for field, field_messages in error.message_dict.items()
        )
        raise PayPalImportError(
            f"Row {row_number}: invalid donor details ({details})."
        ) from None

    return {
        "transaction_id": transaction_id,
        "email": email,
        "name": name,
        "phone": _value(row, columns, "phone"),
        "date": _parse_date(_value(row, columns, "date"), row_number),
        "amount": _parse_amount(_value(row, columns, "amount"), row_number),
        "currency": currency,
        "transaction_type": transaction_type,
        "subscription_id": subscription_id,
        "is_recurring": bool(subscription_id)
        or "subscription" in transaction_type.casefold(),
    }


@transaction.atomic
def import_paypal_csv(content):
    """Import completed PayPal donation rows; any invalid eligible row rolls back the file."""
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise PayPalImportError("CSV must be encoded as UTF-8.") from None

    # Calculate the checksum of the content and check if we already have upload file
    checksum = sha256(content.encode("utf-8")).hexdigest()
    if PaypalTransactionsUploadFile.objects.filter(check_sum=checksum).exists():
        log.warning("CSV file has already been uploaded.")

    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise PayPalImportError("CSV is empty or has no header row.")
    columns = _column_map(reader.fieldnames)

    unique_donors = set()
    new_donor_count = 0
    total_donation_amount: Decimal = Decimal("0.0")
    from_date = None
    to_date = None
    imported = duplicates = ignored = 0
    seen_transaction_ids = set()
    for row_number, row in enumerate(reader, start=2):
        if not _is_donation(row, columns):
            ignored += 1
            continue

        transaction_id = _value(row, columns, "transaction_id")
        if not transaction_id:
            raise PayPalImportError(f"Row {row_number}: transaction ID is required.")
        if (
            transaction_id in seen_transaction_ids
            or DonationTransaction.objects.filter(
                paypal_transaction_id=transaction_id
            ).exists()
        ):
            duplicates += 1
            continue

        values = _validated_donation(row, columns, row_number)
        donation_entry = DonationEntry(**values)
        from_date = (
            min(from_date, donation_entry.date) if from_date else donation_entry.date
        )
        to_date = max(to_date, donation_entry.date) if to_date else donation_entry.date
        values.pop("transaction_id")
        seen_transaction_ids.add(transaction_id)

        donor, created = Donor.objects.get_or_create(
            email__iexact=donation_entry.email,
            defaults={
                "name": donation_entry.name,
                "email": donation_entry.email,
                "phone": donation_entry.phone,
            },
        )
        if created:
            new_donor_count += 1
        elif not donor.phone and donation_entry.phone:
            donor.phone = donation_entry.phone
            donor.save(update_fields=["phone"])

        unique_donors.add(str(donor))
        total_donation_amount += donation_entry.amount

        DonationTransaction.objects.create(
            donor=donor,
            paypal_transaction_id=transaction_id,
            transaction_date=donation_entry.date,
            amount=donation_entry.amount,
            currency=donation_entry.currency,
            transaction_type=donation_entry.transaction_type,
            is_recurring=donation_entry.is_recurring,
            subscription_id=donation_entry.subscription_id,
        )
        imported += 1

    transaction_file, created = PaypalTransactionsUploadFile.objects.get_or_create(
        check_sum=checksum,
        upload_date=datetime.now(),
        from_date=from_date,
        to_date=to_date,
        total_donations=total_donation_amount,
        total_donations_count=imported,
        total_donors=len(unique_donors),
        total_new_donors=new_donor_count,
    )

    if not created:
        PaypalTransactionsUploadFile.objects.update(
            from_date=from_date,
            to_date=to_date,
            total_donations=total_donation_amount,
            total_donations_count=imported,
            total_donors=len(unique_donors),
            total_new_donors=new_donor_count,
        )

    return PayPalImportResult(imported=imported, duplicates=duplicates, ignored=ignored)
