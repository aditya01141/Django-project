from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Donation(models.Model):
    """Represents a charitable donation deducted from a customer's bank account."""

    donor = models.ForeignKey(
        'banking.BankAccount',
        on_delete=models.CASCADE,
        related_name='donations',
    )
    charity_name = models.CharField(max_length=150, default='Animal Welfare Trust')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    message = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'Donation#{self.pk}: {self.donor.account_number} -> {self.charity_name} (${self.amount})'
