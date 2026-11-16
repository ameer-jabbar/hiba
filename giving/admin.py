from django.contrib import admin

from giving.models import (DonationTransaction, Donor,
                           PaypalTransactionsUploadFile)


class DonationTransactionInline(admin.TabularInline):
    model = DonationTransaction
    extra = 0
    fields = (
        "paypal_transaction_id",
        "transaction_date",
        "amount",
        "currency",
        "is_recurring",
        "subscription_id",
    )


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "has_active_recurrent_donation",
        "notes",
    )
    search_fields = ("name", "email", "phone")
    inlines = (DonationTransactionInline,)


@admin.register(DonationTransaction)
class DonationTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "paypal_transaction_id",
        "donor",
        "transaction_date",
        "amount",
        "currency",
        "is_recurring",
    )
    list_filter = ("is_recurring", "currency", "transaction_date")
    search_fields = (
        "paypal_transaction_id",
        "donor__name",
        "donor__email",
        "subscription_id",
    )
    autocomplete_fields = ("donor",)


@admin.register(PaypalTransactionsUploadFile)
class PaypalTransactionsUploadFileAdmin(admin.ModelAdmin):
    list_display = (
        "check_sum",
        "upload_date",
        "from_date",
        "to_date",
        "total_donations",
        "total_donations_count",
    )
    list_filter = ("upload_date",)
    search_fields = ("check_sum",)
