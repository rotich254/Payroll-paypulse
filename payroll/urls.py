from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('employees/', views.employee_list, name='employee_list'),
    path('add_employee/', views.add_employee, name='add_employee'),
    path('edit_employee/<int:employee_id>/', views.edit_employee, name='edit_employee'),
    path('remove_employee/<int:employee_id>/', views.remove_employee, name='remove_employee'),
    path('employee/<int:employee_id>/update-status/', views.update_employee_status, name='update_employee_status'),
    path('payroll/', views.payroll, name='payroll'),
    path('generate-payroll/', views.generate_payroll, name='generate_payroll'), # Added URL for generating payroll
    path('payroll/<int:payroll_id>/pdf/', views.generate_payroll_pdf, name='generate_payroll_pdf'),
    path('payroll/<int:payroll_id>/', views.payroll_detail, name='payroll_detail'),
    # Removed duplicate pdf url
    path('payroll/<int:payroll_id>/mark_paid/', views.mark_payroll_paid, name='mark_payroll_paid'),
    path('paid-payrolls/', views.paid_payroll_list, name='paid_payroll_list'), # New URL for paid payrolls
    path('pending-payrolls/', views.pending_payroll_list, name='pending_payroll_list'), # Renamed URL and view
    
    # Reports URLs
    path('reports/', views.reports, name='reports'),
    path('reports/<int:report_id>/download/', views.download_report, name='download_report'), # Added download URL
    path('reports/<int:report_id>/delete/', views.delete_report, name='delete_report'),     # Added delete URL
]

