from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import BankAccount


@receiver(post_save, sender=User)
def create_bank_account(sender, instance, created, **kwargs):
    """Auto-create a BankAccount with a unique 10-digit number for each new User."""
    if created:
        BankAccount.objects.create(user=instance)
