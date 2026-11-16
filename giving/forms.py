from django import forms


class PayPalCSVUploadForm(forms.Form):
    file = forms.FileField(
        label="PayPal activity CSV",
        help_text="Upload an English-language PayPal activity export in CSV format.",
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Choose a .csv file.")
        return uploaded_file


class DonationReportFilterForm(forms.Form):
    start_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    donor_name = forms.CharField(required=False, label="Donor name", max_length=200)
    minimum_amount = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    maximum_amount = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    donation_type = forms.CharField(
        required=False, label="Donation type", max_length=100
    )
    is_recurring = forms.BooleanField(required=False, label="Recurring")

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "End date must be on or after the start date.")
        minimum = cleaned_data.get("minimum_amount")
        maximum = cleaned_data.get("maximum_amount")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error(
                "maximum_amount", "Maximum amount must be at least the minimum amount."
            )
        return cleaned_data
