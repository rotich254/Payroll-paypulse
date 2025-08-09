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
    path('payrolls/', views.payroll_list, name='payroll_list'),
    path('payrolls/paid/', views.paid_payroll_list, name='paid_payroll_list'),
    path('payrolls/pending/', views.pending_payroll_list, name='pending_payroll_list'),
    path('payroll/<int:payroll_id>/mark_paid/', views.mark_payroll_paid, name='mark_payroll_paid'),
    path('delete_report/<int:report_id>/', views.delete_report, name='delete_report'),
    path('get-employee-salary/<int:employee_id>/', views.get_employee_salary, name='get_employee_salary'),
    path('search-employees/', views.search_employees, name='search_employees'),
    path('company-settings/', views.company_settings, name='company_settings'),
    
    # Reports URLs
    path('reports/', views.reports, name='reports'),
    path('generate-report/', views.generate_report, name='generate_report'),
    path('reports/<int:report_id>/download/', views.download_report, name='download_report'), # Added download URL
    path('reports/<int:report_id>/delete/', views.delete_report, name='delete_report'),     # Added delete URL
]
