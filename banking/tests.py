from decimal import Decimal
import io

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from donate.models import Donation

from .models import BankAccount, Beneficiary, Transaction


class NKBankTests(TestCase):
    """Comprehensive tests for NK-Bank auth, accounts, transfers, donations, and PDF receipts."""

    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='StrongPassword123!')
        self.bob = User.objects.create_user(username='bob', password='StrongPassword123!')
        self.charlie = User.objects.create_user(username='charlie', password='StrongPassword123!')
        self.alice_account = self.alice.bank_account
        self.bob_account = self.bob.bank_account
        self.charlie_account = self.charlie.bank_account

    def test_user_registration_creates_unique_ten_digit_bank_account(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password1': 'StrongPassword123!',
                'password2': 'StrongPassword123!',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))

        user = User.objects.get(username='newuser')
        account = BankAccount.objects.get(user=user)
        self.assertRegex(account.account_number, r'^\d{10}$')
        self.assertEqual(account.balance, Decimal('1000.00'))
        self.assertNotEqual(account.account_number, self.alice_account.account_number)

    def test_protected_routes_require_login(self):
        protected_urls = [
            reverse('dashboard'),
            reverse('export_csv'),
            reverse('transfer'),
            reverse('beneficiaries'),
            reverse('donate'),
            reverse('transaction_receipt', args=[1]),
            reverse('donation_receipt', args=[1]),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('login'), response.url)

    def test_valid_transfer_updates_balances_atomically_and_saves_beneficiary(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('transfer'),
            {
                'recipient_account_number': self.bob_account.account_number,
                'amount': '250.50',
                'note': 'Dinner split',
                'save_beneficiary': 'on',
                'beneficiary_nickname': 'Bob Checking',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))

        self.alice_account.refresh_from_db()
        self.bob_account.refresh_from_db()
        self.assertEqual(self.alice_account.balance, Decimal('749.50'))
        self.assertEqual(self.bob_account.balance, Decimal('1250.50'))

        tx = Transaction.objects.get(sender=self.alice_account, receiver=self.bob_account)
        self.assertEqual(tx.amount, Decimal('250.50'))
        self.assertEqual(tx.note, 'Dinner split')

        beneficiary = Beneficiary.objects.get(
            owner=self.alice_account,
            beneficiary_account=self.bob_account,
        )
        self.assertEqual(beneficiary.nickname, 'Bob Checking')

    def test_transfer_via_saved_beneficiary_dropdown(self):
        beneficiary = Beneficiary.objects.create(
            owner=self.alice_account,
            beneficiary_account=self.bob_account,
            nickname='Bob',
        )
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('transfer'),
            {
                'beneficiary': beneficiary.pk,
                'amount': '100.00',
                'note': 'Rent share',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))

        self.alice_account.refresh_from_db()
        self.bob_account.refresh_from_db()
        self.assertEqual(self.alice_account.balance, Decimal('900.00'))
        self.assertEqual(self.bob_account.balance, Decimal('1100.00'))

    def test_insufficient_balance_transfer_is_rejected(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('transfer'),
            {
                'recipient_account_number': self.bob_account.account_number,
                'amount': '1500.00',
                'note': 'Too much',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Insufficient balance')

        self.alice_account.refresh_from_db()
        self.bob_account.refresh_from_db()
        self.assertEqual(self.alice_account.balance, Decimal('1000.00'))
        self.assertEqual(self.bob_account.balance, Decimal('1000.00'))
        self.assertEqual(Transaction.objects.count(), 0)

    def test_self_transfer_is_rejected(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('transfer'),
            {
                'recipient_account_number': self.alice_account.account_number,
                'amount': '50.00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cannot transfer money to your own account')
        self.assertEqual(Transaction.objects.count(), 0)

    def test_beneficiary_management_and_ownership_protection(self):
        self.client.force_login(self.alice)
        add_resp = self.client.post(
            reverse('beneficiaries'),
            {
                'account_number': self.bob_account.account_number,
                'nickname': 'Bobby',
            },
        )
        self.assertRedirects(add_resp, reverse('beneficiaries'))
        beneficiary = Beneficiary.objects.get(
            owner=self.alice_account,
            beneficiary_account=self.bob_account,
        )

        # Duplicate beneficiary should fail validation cleanly
        dup_resp = self.client.post(
            reverse('beneficiaries'),
            {
                'account_number': self.bob_account.account_number,
                'nickname': 'Bobby Duplicate',
            },
        )
        self.assertEqual(dup_resp.status_code, 200)
        self.assertContains(dup_resp, 'already saved in your beneficiaries')

        # Another user cannot delete Alice's beneficiary
        self.client.force_login(self.charlie)
        forbidden_del = self.client.post(reverse('delete_beneficiary', args=[beneficiary.pk]))
        self.assertEqual(forbidden_del.status_code, 403)
        self.assertTrue(Beneficiary.objects.filter(pk=beneficiary.pk).exists())

        # Owner can delete
        self.client.force_login(self.alice)
        ok_del = self.client.post(reverse('delete_beneficiary', args=[beneficiary.pk]))
        self.assertRedirects(ok_del, reverse('beneficiaries'))
        self.assertFalse(Beneficiary.objects.filter(pk=beneficiary.pk).exists())

    def test_valid_donation_and_insufficient_balance_rejection(self):
        self.client.force_login(self.alice)
        ok_resp = self.client.post(
            reverse('donate'),
            {
                'charity_name': 'Animal Welfare Trust',
                'amount': '250.00',
                'message': 'Help shelter animals',
            },
        )
        self.assertRedirects(ok_resp, reverse('dashboard'))

        self.alice_account.refresh_from_db()
        self.assertEqual(self.alice_account.balance, Decimal('750.00'))
        donation = Donation.objects.get(donor=self.alice_account)
        self.assertEqual(donation.charity_name, 'Animal Welfare Trust')
        self.assertEqual(donation.amount, Decimal('250.00'))

        # Attempt donation exceeding remaining $750.00 balance
        fail_resp = self.client.post(
            reverse('donate'),
            {
                'charity_name': 'Animal Welfare Trust',
                'amount': '900.00',
            },
        )
        self.assertEqual(fail_resp.status_code, 200)
        self.assertContains(fail_resp, 'Insufficient balance')
        self.alice_account.refresh_from_db()
        self.assertEqual(self.alice_account.balance, Decimal('750.00'))
        self.assertEqual(Donation.objects.count(), 1)

    def test_dashboard_displays_unified_chronological_history(self):
        tx_sent = Transaction.objects.create(
            sender=self.alice_account,
            receiver=self.bob_account,
            amount=Decimal('50.00'),
            note='Coffee',
        )
        tx_received = Transaction.objects.create(
            sender=self.charlie_account,
            receiver=self.alice_account,
            amount=Decimal('120.00'),
            note='Refund',
        )
        donation = Donation.objects.create(
            donor=self.alice_account,
            charity_name='Animal Welfare Trust',
            amount=Decimal('100.00'),
            message='For pets',
        )

        self.client.force_login(self.alice)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.alice_account.account_number)
        self.assertContains(response, 'Sent Transfer')
        self.assertContains(response, 'Received Transfer')
        self.assertContains(response, 'Charity Donation')
        self.assertContains(response, reverse('transaction_receipt', args=[tx_sent.pk]))
        self.assertContains(response, reverse('transaction_receipt', args=[tx_received.pk]))
        self.assertContains(response, reverse('donation_receipt', args=[donation.pk]))

    def test_transaction_receipt_access_control_and_pdf_output(self):
        tx = Transaction.objects.create(
            sender=self.alice_account,
            receiver=self.bob_account,
            amount=Decimal('75.00'),
            note='Book payment',
        )
        receipt_url = reverse('transaction_receipt', args=[tx.pk])

        # Sender can download valid PDF
        self.client.force_login(self.alice)
        sender_resp = self.client.get(receipt_url)
        self.assertEqual(sender_resp.status_code, 200)
        self.assertEqual(sender_resp['Content-Type'], 'application/pdf')
        self.assertTrue(sender_resp.content.startswith(b'%PDF-'))

        # Receiver can download valid PDF
        self.client.force_login(self.bob)
        receiver_resp = self.client.get(receipt_url)
        self.assertEqual(receiver_resp.status_code, 200)
        self.assertEqual(receiver_resp['Content-Type'], 'application/pdf')
        self.assertTrue(receiver_resp.content.startswith(b'%PDF-'))

        # Unrelated user receives 403 Forbidden
        self.client.force_login(self.charlie)
        outsider_resp = self.client.get(receipt_url)
        self.assertEqual(outsider_resp.status_code, 403)

    def test_donation_receipt_access_control_and_pdf_output(self):
        donation = Donation.objects.create(
            donor=self.alice_account,
            charity_name='Animal Welfare Trust',
            amount=Decimal('100.00'),
            message='Keep up the great work',
        )
        receipt_url = reverse('donation_receipt', args=[donation.pk])

        # Donor can download valid PDF
        self.client.force_login(self.alice)
        donor_resp = self.client.get(receipt_url)
        self.assertEqual(donor_resp.status_code, 200)
        self.assertEqual(donor_resp['Content-Type'], 'application/pdf')
        self.assertTrue(donor_resp.content.startswith(b'%PDF-'))

        # Another user receives 403 Forbidden
        self.client.force_login(self.bob)
        other_resp = self.client.get(receipt_url)
        self.assertEqual(other_resp.status_code, 403)

    def test_dashboard_search_filter_summary_and_csv_export(self):
        Transaction.objects.create(
            sender=self.alice_account,
            receiver=self.bob_account,
            amount=Decimal('50.00'),
            note='Coffee meetup',
        )
        Transaction.objects.create(
            sender=self.charlie_account,
            receiver=self.alice_account,
            amount=Decimal('200.00'),
            note='Freelance payout',
        )
        Donation.objects.create(
            donor=self.alice_account,
            charity_name='Animal Welfare Trust',
            amount=Decimal('100.00'),
            message='Shelter gift',
        )

        self.client.force_login(self.alice)

        # Summary totals appear on dashboard
        dash_resp = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, '+$200.00')
        self.assertContains(dash_resp, '-$50.00')
        self.assertContains(dash_resp, '-$100.00')

        # Search query filters matching records only
        search_resp = self.client.get(reverse('dashboard'), {'q': 'Coffee'})
        self.assertContains(search_resp, 'Coffee meetup')
        self.assertNotContains(search_resp, 'Freelance payout')
        self.assertNotContains(search_resp, 'Shelter gift')

        # Type filter shows donations only
        type_resp = self.client.get(reverse('dashboard'), {'type': 'donation'})
        self.assertContains(type_resp, 'Shelter gift')
        self.assertNotContains(type_resp, 'Coffee meetup')

        # CSV export respects filters and returns text/csv attachment
        csv_resp = self.client.get(reverse('export_csv'), {'q': 'Freelance'})
        self.assertEqual(csv_resp.status_code, 200)
        self.assertTrue(csv_resp['Content-Type'].startswith('text/csv'))
        csv_body = csv_resp.content.decode('utf-8')
        self.assertIn('Date & Time,Type,Counterparty / Charity', csv_body)
        self.assertIn('Freelance payout', csv_body)
        self.assertNotIn('Coffee meetup', csv_body)

    def test_seed_demo_command_creates_working_credentials_idempotently(self):
        out = io.StringIO()
        call_command('seed_demo', stdout=out)
        call_command('seed_demo', stdout=out)

        self.assertTrue(self.client.login(username='alice', password='DemoUser123!'))
        self.client.logout()
        self.assertTrue(self.client.login(username='bob', password='DemoUser123!'))
        self.client.logout()
        self.assertTrue(self.client.login(username='admin', password='AdminUser123!'))
        self.assertTrue(User.objects.get(username='admin').is_superuser)
