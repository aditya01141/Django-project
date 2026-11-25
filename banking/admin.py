from django.contrib import admin

from .models import BankAccount, Beneficiary, Transaction


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'account_number', 'balance', 'created_at')
    search_fields = ('user__username', 'user__email', 'account_number')
    readonly_fields = ('created_at',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'amount', 'note', 'timestamp')
    search_fields = (
        'sender__account_number',
        'sender__user__username',
        'receiver__account_number',
        'receiver__user__username',
        'note',
    )
    readonly_fields = ('timestamp',)


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'owner', 'beneficiary_account', 'created_at')
    search_fields = (
        'nickname',
        'owner__user__username',
        'owner__account_number',
        'beneficiary_account__account_number',
    )
    readonly_fields = ('created_at',)
