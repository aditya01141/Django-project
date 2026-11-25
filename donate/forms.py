from decimal import Decimal

from django import forms


class DonationForm(forms.Form):
    """Charitable donation form with default charity and custom amount validation."""

    charity_name = forms.CharField(
        max_length=150,
        required=False,
        initial='Animal Welfare Trust',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Animal Welfare Trust',
        }),
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': '0.00',
        }),
    )
    message = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional message for the charity',
        }),
    )

    def clean_charity_name(self):
        name = (self.cleaned_data.get('charity_name') or '').strip()
        return name or 'Animal Welfare Trust'
