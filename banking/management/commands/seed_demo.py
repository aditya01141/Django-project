from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from banking.models import Beneficiary, Transaction
from banking.services import execute_donation, execute_transfer


def _ensure_user(
    username: str,
    password: str,
    email: str,
    *,
    first_name: str = '',
    last_name: str = '',
    is_superuser: bool = False,
) -> tuple[User, bool]:
    """Create or refresh a demo user idempotently."""
    user = User.objects.filter(username=username).first()
    if user is None:
        if is_superuser:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
        return user, True

    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.set_password(password)
    if is_superuser:
        user.is_staff = True
        user.is_superuser = True
    user.save()
    return user, False


class Command(BaseCommand):
    """Seed demo customer and admin login credentials with sample activity."""

    help = 'Seed demo NK-Bank users (alice, bob, admin) and sample transactions.'

    def handle(self, *args, **options):
        alice, _ = _ensure_user(
            'alice',
            'DemoUser123!',
            'alice@nkbank.local',
            first_name='Alice',
            last_name='Carter',
        )
        bob, _ = _ensure_user(
            'bob',
            'DemoUser123!',
            'bob@nkbank.local',
            first_name='Bob',
            last_name='Patel',
        )
        admin_user, _ = _ensure_user(
            'admin',
            'AdminUser123!',
            'admin@nkbank.local',
            first_name='NK',
            last_name='Admin',
            is_superuser=True,
        )

        alice_acc = alice.bank_account
        bob_acc = bob.bank_account

        has_history = Transaction.objects.filter(sender__in=[alice_acc, bob_acc]).exists()
        if not has_history:
            execute_transfer(
                sender_account_id=alice_acc.pk,
                receiver_account_id=bob_acc.pk,
                amount=Decimal('175.00'),
                note='Project dinner split',
                save_beneficiary=True,
                beneficiary_nickname='Bob Checking',
            )
            execute_transfer(
                sender_account_id=bob_acc.pk,
                receiver_account_id=alice_acc.pk,
                amount=Decimal('60.00'),
                note='Shared cab reimbursement',
                save_beneficiary=True,
                beneficiary_nickname='Alice Main',
            )
            execute_donation(
                donor_account_id=alice_acc.pk,
                charity_name='Animal Welfare Trust',
                amount=Decimal('100.00'),
                message='Monthly shelter support',
            )
        else:
            Beneficiary.objects.get_or_create(
                owner=alice_acc,
                beneficiary_account=bob_acc,
                defaults={'nickname': 'Bob Checking'},
            )

        self.stdout.write(self.style.SUCCESS('NK-Bank demo credentials ready:'))
        self.stdout.write(f'  Customer 1 -> username: alice | password: DemoUser123! | account: {alice_acc.account_number}')
        self.stdout.write(f'  Customer 2 -> username: bob   | password: DemoUser123! | account: {bob_acc.account_number}')
        self.stdout.write(f'  Admin      -> username: {admin_user.username} | password: AdminUser123! | url: /admin/')
