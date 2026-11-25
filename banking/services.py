from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from donate.models import Donation

from .models import BankAccount, Beneficiary, Transaction


class InsufficientFundsError(Exception):
    """Raised when an account lacks enough balance to cover a debit."""


def execute_transfer(
    *,
    sender_account_id: int,
    receiver_account_id: int,
    amount: Decimal,
    note: str = '',
    save_beneficiary: bool = False,
    beneficiary_nickname: str = '',
) -> Transaction:
    """Atomically transfer funds between two accounts using row-level locks."""
    if amount <= Decimal('0.00'):
        raise ValidationError('Transfer amount must be greater than zero.')
    if sender_account_id == receiver_account_id:
        raise ValidationError('You cannot transfer funds to your own account.')

    with transaction.atomic():
        # Lock rows in deterministic primary-key order to avoid deadlocks.
        locked_accounts = {
            acc.pk: acc
            for acc in BankAccount.objects.select_for_update()
            .filter(pk__in=[sender_account_id, receiver_account_id])
            .order_by('pk')
        }
        sender_locked = locked_accounts[sender_account_id]
        receiver_locked = locked_accounts[receiver_account_id]

        if sender_locked.balance < amount:
            raise InsufficientFundsError(
                f'Insufficient balance. Available balance is ${sender_locked.balance:,.2f}.'
            )

        sender_locked.balance -= amount
        receiver_locked.balance += amount
        sender_locked.save(update_fields=['balance'])
        receiver_locked.save(update_fields=['balance'])

        tx = Transaction.objects.create(
            sender=sender_locked,
            receiver=receiver_locked,
            amount=amount,
            note=note.strip(),
        )

        if save_beneficiary:
            nickname = beneficiary_nickname.strip() or receiver_locked.user.username
            Beneficiary.objects.get_or_create(
                owner=sender_locked,
                beneficiary_account=receiver_locked,
                defaults={'nickname': nickname},
            )

    return tx


def execute_donation(
    *,
    donor_account_id: int,
    charity_name: str,
    amount: Decimal,
    message: str = '',
) -> Donation:
    """Atomically deduct a donation amount and record a Donation entry."""
    if amount <= Decimal('0.00'):
        raise ValidationError('Donation amount must be greater than zero.')

    normalized_charity = charity_name.strip() or 'Animal Welfare Trust'

    with transaction.atomic():
        donor_locked = BankAccount.objects.select_for_update().get(pk=donor_account_id)

        if donor_locked.balance < amount:
            raise InsufficientFundsError(
                f'Insufficient balance. Available balance is ${donor_locked.balance:,.2f}.'
            )

        donor_locked.balance -= amount
        donor_locked.save(update_fields=['balance'])

        return Donation.objects.create(
            donor=donor_locked,
            charity_name=normalized_charity,
            amount=amount,
            message=message.strip(),
        )


def get_account_summary_and_activities(
    account: BankAccount,
    *,
    query: str = '',
    activity_type: str = 'all',
) -> tuple[dict, list[dict]]:
    """Build account totals and filtered reverse-chronological activity items."""
    transactions = (
        Transaction.objects.filter(Q(sender=account) | Q(receiver=account))
        .select_related('sender__user', 'receiver__user')
    )
    donations = Donation.objects.filter(donor=account)

    total_sent = Decimal('0.00')
    total_received = Decimal('0.00')
    total_donated = Decimal('0.00')
    all_activities: list[dict] = []

    for tx in transactions:
        is_sent = tx.sender_id == account.pk
        if is_sent:
            total_sent += tx.amount
        else:
            total_received += tx.amount

        counterparty = tx.receiver if is_sent else tx.sender
        all_activities.append({
            'kind': 'sent' if is_sent else 'received',
            'label': 'Sent Transfer' if is_sent else 'Received Transfer',
            'party': f'{counterparty.user.username} ({counterparty.account_number})',
            'note': tx.note or '—',
            'raw_note': tx.note or '',
            'amount': tx.amount,
            'direction': 'Debit' if is_sent else 'Credit',
            'signed_amount': f'-${tx.amount:,.2f}' if is_sent else f'+${tx.amount:,.2f}',
            'timestamp': tx.timestamp,
            'receipt_url': reverse('transaction_receipt', args=[tx.pk]),
        })

    for donation in donations:
        total_donated += donation.amount
        all_activities.append({
            'kind': 'donation',
            'label': 'Charity Donation',
            'party': donation.charity_name,
            'note': donation.message or '—',
            'raw_note': donation.message or '',
            'amount': donation.amount,
            'direction': 'Debit',
            'signed_amount': f'-${donation.amount:,.2f}',
            'timestamp': donation.timestamp,
            'receipt_url': reverse('donation_receipt', args=[donation.pk]),
        })

    summary = {
        'total_sent': total_sent,
        'total_received': total_received,
        'total_donated': total_donated,
        'beneficiaries_count': account.beneficiaries.count(),
    }

    normalized_type = activity_type if activity_type in {'sent', 'received', 'donation'} else 'all'
    normalized_query = query.strip().lower()

    filtered = [
        item
        for item in all_activities
        if (normalized_type == 'all' or item['kind'] == normalized_type)
        and (
            not normalized_query
            or normalized_query in item['party'].lower()
            or normalized_query in item['raw_note'].lower()
            or normalized_query in item['label'].lower()
            or normalized_query in item['signed_amount'].lower()
        )
    ]
    filtered.sort(key=lambda item: item['timestamp'], reverse=True)
    return summary, filtered
