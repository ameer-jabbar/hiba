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
