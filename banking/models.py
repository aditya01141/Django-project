import secrets
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


def generate_unique_account_number() -> str:
    """Generate a unique 10-digit numeric account number."""
    while True:
        candidate = str(10**9 + secrets.randbelow(9 * 10**9))
        if not BankAccount.objects.filter(account_number=candidate).exists():
            return candidate


class BankAccount(models.Model):
    """Represents a customer's NK-Bank account tied one-to-one with a User."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='bank_account',
    )
    account_number = models.CharField(
        max_length=10,
        unique=True,
        validators=[RegexValidator(r'^\d{10}$', 'Account number must be exactly 10 digits.')],
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('1000.00'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = generate_unique_account_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username} ({self.account_number})'


class Transaction(models.Model):
    """Represents an atomic peer-to-peer transfer between two bank accounts."""

    sender = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='sent_transactions',
    )
    receiver = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='received_transactions',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    note = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'TX#{self.pk}: {self.sender.account_number} -> {self.receiver.account_number} (${self.amount})'


class Beneficiary(models.Model):
    """Represents a saved transfer recipient for a bank account owner."""

    owner = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='beneficiaries',
    )
    beneficiary_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='beneficiary_of',
    )
    nickname = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Beneficiaries'
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'beneficiary_account'],
                name='unique_owner_beneficiary',
            ),
        ]

    def __str__(self):
        return f'{self.nickname} ({self.beneficiary_account.account_number})'
