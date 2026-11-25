from django.urls import path

from . import views

urlpatterns = [
    path('', views.donate_view, name='donate'),
    path('receipt/<int:pk>/', views.donation_receipt_view, name='donation_receipt'),
]
