from django.db import models


class Donor(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["name", "email"]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class DonationTransaction(models.Model):
    donor = models.ForeignKey(
        Donor, on_delete=models.PROTECT, related_name="transactions"
    )
    paypal_transaction_id = models.CharField(max_length=100, unique=True)
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    transaction_type = models.CharField(max_length=100)
    is_recurring = models.BooleanField(default=False)
    subscription_id = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]

    def __str__(self):
        return f"{self.amount} {self.currency} on {self.transaction_date} ({self.paypal_transaction_id})"
