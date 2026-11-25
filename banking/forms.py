import re
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import BankAccount, Beneficiary


class RegistrationForm(UserCreationForm):
    """Customer registration form with Bootstrap 5 styling."""

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address (optional)'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Create a password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm your password',
        })


class StyledAuthenticationForm(AuthenticationForm):
    """Login form with Bootstrap 5 widget classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
        })


class TransferForm(forms.Form):
    """Peer-to-peer transfer form supporting saved beneficiaries or 10-digit account input."""

    beneficiary = forms.ModelChoiceField(
        queryset=Beneficiary.objects.none(),
        required=False,
        empty_label='-- Select a saved beneficiary --',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    recipient_account_number = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 10-digit account number',
            'maxlength': '10',
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
    note = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'What is this transfer for? (optional)',
        }),
    )
    save_beneficiary = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    beneficiary_nickname = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nickname if saving beneficiary (optional)',
        }),
    )

    def __init__(self, *args, sender_account: BankAccount | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender_account = sender_account
        if sender_account is not None:
            self.fields['beneficiary'].queryset = Beneficiary.objects.filter(
                owner=sender_account
            ).select_related('beneficiary_account__user')

    def clean(self):
        cleaned_data = super().clean()
        beneficiary = cleaned_data.get('beneficiary')
        manual_account_number = (cleaned_data.get('recipient_account_number') or '').strip()

        if beneficiary and manual_account_number:
            if beneficiary.beneficiary_account.account_number != manual_account_number:
                raise ValidationError(
                    'Selected beneficiary and entered account number do not match. '
                    'Please use only one recipient option.'
                )
            receiver = beneficiary.beneficiary_account
        elif beneficiary:
            receiver = beneficiary.beneficiary_account
        elif manual_account_number:
            if not re.fullmatch(r'\d{10}', manual_account_number):
                self.add_error('recipient_account_number', 'Enter a valid 10-digit account number.')
                return cleaned_data
            receiver = BankAccount.objects.filter(account_number=manual_account_number).first()
            if receiver is None:
                self.add_error(
                    'recipient_account_number',
                    'No account exists with that 10-digit account number.',
                )
                return cleaned_data
        else:
            raise ValidationError(
                'Select a saved beneficiary or enter a 10-digit recipient account number.'
            )

        if self.sender_account and receiver.pk == self.sender_account.pk:
            raise ValidationError('You cannot transfer money to your own account.')

        cleaned_data['receiver_account'] = receiver
        return cleaned_data


class BeneficiaryForm(forms.Form):
    """Form to add a new saved beneficiary by 10-digit account number."""

    account_number = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10-digit account number',
            'maxlength': '10',
        }),
    )
    nickname = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Friendly nickname',
        }),
    )

    def __init__(self, *args, owner_account: BankAccount | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner_account = owner_account

    def clean_account_number(self):
        account_number = self.cleaned_data['account_number'].strip()
        if not re.fullmatch(r'\d{10}', account_number):
            raise ValidationError('Enter a valid 10-digit account number.')
        target_account = BankAccount.objects.filter(account_number=account_number).first()
        if target_account is None:
            raise ValidationError('No NK-Bank account found with that account number.')
        if self.owner_account and target_account.pk == self.owner_account.pk:
            raise ValidationError('You cannot add your own account as a beneficiary.')
        if self.owner_account and Beneficiary.objects.filter(
            owner=self.owner_account,
            beneficiary_account=target_account,
        ).exists():
            raise ValidationError('This account is already saved in your beneficiaries.')
        self.cleaned_data['target_account'] = target_account
        return account_number
