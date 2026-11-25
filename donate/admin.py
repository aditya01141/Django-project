from django.contrib import admin

from .models import Donation


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('id', 'donor', 'charity_name', 'amount', 'message', 'timestamp')
    search_fields = ('donor__account_number', 'donor__user__username', 'charity_name', 'message')
    readonly_fields = ('timestamp',)
