import csv

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BeneficiaryForm, RegistrationForm, StyledAuthenticationForm, TransferForm
from .models import Beneficiary, Transaction
from .pdf import generate_transaction_receipt_pdf
from .services import (
    InsufficientFundsError,
    execute_transfer,
    get_account_summary_and_activities,
)


def register_view(request):
    """Register a new user, automatically creating their BankAccount via signal."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            account = user.bank_account
            messages.success(
                request,
                f'Welcome to NK-Bank! Your account number is {account.account_number} '
                f'with an opening balance of ${account.balance:,.2f}.',
            )
            return redirect('dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'banking/register.html', {'form': form})


login_view = LoginView.as_view(
    template_name='banking/login.html',
    authentication_form=StyledAuthenticationForm,
    redirect_authenticated_user=True,
)

logout_view = LogoutView.as_view(next_page='login')


@login_required
def dashboard_view(request):
    """Display account summary cards, filters, quick actions, and unified activity."""
    account = request.user.bank_account
    query = request.GET.get('q', '').strip()
    activity_type = request.GET.get('type', 'all').strip()
    if activity_type not in {'all', 'sent', 'received', 'donation'}:
        activity_type = 'all'

    summary, activities = get_account_summary_and_activities(
        account,
        query=query,
        activity_type=activity_type,
    )

    return render(
        request,
        'banking/dashboard.html',
        {
            'account': account,
            'summary': summary,
            'activities': activities,
            'query': query,
            'activity_type': activity_type,
            'has_filters': bool(query or activity_type != 'all'),
        },
    )


@login_required
def export_activity_csv_view(request):
    """Export filtered or full account activity as a downloadable CSV statement."""
    account = request.user.bank_account
    query = request.GET.get('q', '').strip()
    activity_type = request.GET.get('type', 'all').strip()

    _, activities = get_account_summary_and_activities(
        account,
        query=query,
        activity_type=activity_type,
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="nkbank_statement_{account.account_number}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date & Time', 'Type', 'Counterparty / Charity', 'Note / Message', 'Direction', 'Amount'])
    for item in activities:
        local_ts = timezone.localtime(item['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        signed_decimal = f'-{item["amount"]:.2f}' if item['direction'] == 'Debit' else f'{item["amount"]:.2f}'
        writer.writerow([
            local_ts,
            item['label'],
            item['party'],
            item['raw_note'],
            item['direction'],
            signed_decimal,
        ])

    return response


@login_required
def transfer_view(request):
    """Handle peer-to-peer transfers with atomic balance updates and row locking."""
    account = request.user.bank_account

    if request.method == 'POST':
        form = TransferForm(request.POST, sender_account=account)
        if form.is_valid():
            receiver = form.cleaned_data['receiver_account']
            try:
                tx = execute_transfer(
                    sender_account_id=account.pk,
                    receiver_account_id=receiver.pk,
                    amount=form.cleaned_data['amount'],
                    note=form.cleaned_data['note'],
                    save_beneficiary=form.cleaned_data['save_beneficiary'],
                    beneficiary_nickname=form.cleaned_data['beneficiary_nickname'],
                )
            except InsufficientFundsError as exc:
                form.add_error('amount', str(exc))
            else:
                messages.success(
                    request,
                    f'Successfully transferred ${tx.amount:,.2f} to '
                    f'{receiver.user.username} ({receiver.account_number}).',
                )
                return redirect('dashboard')
    else:
        initial = {}
        beneficiary_id = request.GET.get('beneficiary')
        if beneficiary_id and beneficiary_id.isdigit():
            selected = Beneficiary.objects.filter(
                pk=int(beneficiary_id),
                owner=account,
            ).first()
            if selected:
                initial['beneficiary'] = selected
        form = TransferForm(sender_account=account, initial=initial)

    return render(
        request,
        'banking/transfer.html',
        {
            'account': account,
            'form': form,
        },
    )


@login_required
def beneficiaries_view(request):
    """List saved beneficiaries and allow adding new ones."""
    account = request.user.bank_account

    if request.method == 'POST':
        form = BeneficiaryForm(request.POST, owner_account=account)
        if form.is_valid():
            Beneficiary.objects.create(
                owner=account,
                beneficiary_account=form.cleaned_data['target_account'],
                nickname=form.cleaned_data['nickname'].strip(),
            )
            messages.success(request, 'Beneficiary added successfully.')
            return redirect('beneficiaries')
    else:
        form = BeneficiaryForm(owner_account=account)

    beneficiaries = Beneficiary.objects.filter(owner=account).select_related(
        'beneficiary_account__user'
    )
    return render(
        request,
        'banking/beneficiaries.html',
        {
            'account': account,
            'form': form,
            'beneficiaries': beneficiaries,
        },
    )


@login_required
@require_POST
def delete_beneficiary_view(request, pk):
    """Delete a saved beneficiary owned by the logged-in customer."""
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    if beneficiary.owner != request.user.bank_account:
        return HttpResponseForbidden('You do not have permission to delete this beneficiary.')

    nickname = beneficiary.nickname
    beneficiary.delete()
    messages.success(request, f'Removed "{nickname}" from your beneficiaries.')
    return redirect('beneficiaries')


@login_required
def transaction_receipt_view(request, pk):
    """Generate and serve a downloadable PDF receipt for a Transaction."""
    tx = get_object_or_404(
        Transaction.objects.select_related('sender__user', 'receiver__user'),
        pk=pk,
    )
    user_account = request.user.bank_account
    if user_account != tx.sender and user_account != tx.receiver:
        return HttpResponseForbidden('You do not have permission to access this receipt.')

    pdf_bytes = generate_transaction_receipt_pdf(tx)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="transaction_receipt_{tx.pk}.pdf"'
    return response
