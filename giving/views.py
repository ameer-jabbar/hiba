from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from giving.forms import PayPalCSVUploadForm
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
