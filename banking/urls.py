from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('export/csv/', views.export_activity_csv_view, name='export_csv'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('transfer/', views.transfer_view, name='transfer'),
    path('beneficiaries/', views.beneficiaries_view, name='beneficiaries'),
    path('beneficiaries/<int:pk>/delete/', views.delete_beneficiary_view, name='delete_beneficiary'),
    path('receipt/transaction/<int:pk>/', views.transaction_receipt_view, name='transaction_receipt'),
]
