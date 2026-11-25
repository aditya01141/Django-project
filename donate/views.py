from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from banking.pdf import generate_donation_receipt_pdf
from banking.services import InsufficientFundsError, execute_donation

from .forms import DonationForm
from .models import Donation

PRESET_AMOUNTS = [100, 250, 500, 1000]


@login_required
def donate_view(request):
    """Allow customers to donate atomically to a charity with preset or custom amounts."""
    account = request.user.bank_account

    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
            try:
                donation = execute_donation(
                    donor_account_id=account.pk,
                    charity_name=form.cleaned_data['charity_name'],
                    amount=form.cleaned_data['amount'],
                    message=form.cleaned_data['message'],
                )
            except InsufficientFundsError as exc:
                form.add_error('amount', str(exc))
            else:
                messages.success(
                    request,
                    f'Thank you! Donated ${donation.amount:,.2f} to {donation.charity_name}.',
                )
                return redirect('dashboard')
    else:
        form = DonationForm()

    return render(
        request,
        'banking/donate.html',
        {
            'account': account,
            'form': form,
            'preset_amounts': PRESET_AMOUNTS,
        },
    )


@login_required
def donation_receipt_view(request, pk):
    """Generate and serve a downloadable PDF receipt for a Donation."""
    donation = get_object_or_404(Donation.objects.select_related('donor__user'), pk=pk)
    if request.user.bank_account != donation.donor:
        return HttpResponseForbidden('You do not have permission to access this receipt.')

    pdf_bytes = generate_donation_receipt_pdf(donation)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="donation_receipt_{donation.pk}.pdf"'
    return response
