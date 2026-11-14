# Masjid Donations

An initial Django application for maintaining donor contact details and PayPal donation history. A donor is matched by email, and recurrence is recorded per transaction so one donor can have both recurring and one-off donations.

## Getting started

Install the project dependencies, apply migrations, and create a staff account:

```powershell
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Sign in at `/admin/` to manage donors and transactions. The staff-only CSV import page is at `/imports/paypal/`.

## PayPal CSV import

Upload an English-language PayPal activity CSV. The importer accepts these common column names (case-insensitive):

| Data | Accepted headers |
| --- | --- |
| Transaction ID | `Transaction ID`, `Txn ID`, `transaction_id` |
| Date | `Date`, `Transaction Date` |
| Amount | `Gross`, `Amount` |
| Currency | `Currency` |
| Status | `Status` |
| Activity type | `Type`, `Transaction Type` |
| Donor email | `From Email Address`, `Payer Email`, `Sender Email`, `Email` |
| Donor name | `Name`, `Payer Name`, `From Name` |
| Phone (optional) | `Contact Phone Number`, `Phone Number`, `Phone` |
| Subscription (optional) | `Subscription ID`, `Subscr ID`, `subscription_id` |
| Direction (optional) | `Direction` |

The required transaction columns must be present. Dates may be ISO (`2025-01-15`) or use common English formats such as `01/15/2025`. Only completed donation, recurring-payment, and subscription-payment rows are imported; refunds, outgoing activity, pending activity, and unrelated types are ignored. An explicit subscription ID or recurring/subscription activity type marks that transaction recurring. Repeated donations alone do not imply recurrence.

Eligible rows must have a valid donor name and email, a positive amount with at most two decimal places, a three-letter currency code, a date, and a PayPal transaction ID. Rows with an existing transaction ID are skipped without changing stored data. If an eligible row is malformed, the entire file import is rolled back; the upload page reports the row-specific issue so the CSV can be corrected and retried.