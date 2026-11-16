from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from giving.forms import DonationReportFilterForm, PayPalCSVUploadForm
from giving.models import DonationTransaction
from giving.services import PayPalImportError, import_paypal_csv


@staff_member_required(login_url="admin:login")
def paypal_import(request):
    form = PayPalCSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded_file = form.cleaned_data["file"]
        try:
            result = import_paypal_csv(uploaded_file.read())
        except PayPalImportError as error:
            form.add_error("file", str(error))
        else:
            messages.success(
                request,
                f"Imported {result.imported} donation(s); skipped {result.duplicates} duplicate(s) "
                f"and {result.ignored} unrelated or incomplete transaction(s).",
            )
    return render(request, "giving/import.html", {"form": form})


@staff_member_required(login_url="admin:login")
def donation_report(request):
    form = DonationReportFilterForm(request.GET or None)
    transactions = DonationTransaction.objects.select_related("donor").all()
    if form.is_valid():
        filters = form.cleaned_data
        if filters["start_date"]:
            transactions = transactions.filter(
                transaction_date__gte=filters["start_date"]
            )
        if filters["end_date"]:
            transactions = transactions.filter(
                transaction_date__lte=filters["end_date"]
            )
        if filters["donor_name"]:
            transactions = transactions.filter(
                donor__name__icontains=filters["donor_name"]
            )
        if filters["minimum_amount"] is not None:
            transactions = transactions.filter(amount__gte=filters["minimum_amount"])
        if filters["maximum_amount"] is not None:
            transactions = transactions.filter(amount__lte=filters["maximum_amount"])
        if filters["donation_type"]:
            transactions = transactions.filter(
                donation_type__icontains=filters["donation_type"]
            )
        if filters["is_recurring"]:
            transactions = transactions.filter(is_recurring=True)
    return render(
        request, "giving/report.html", {"form": form, "transactions": transactions}
    )
