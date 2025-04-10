from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('employees/', views.employee_list, name='employee_list'),
    path('add_employee/', views.add_employee, name='add_employee'),
    path('edit_employee/<int:employee_id>/', views.edit_employee, name='edit_employee'),
    path('remove_employee/<int:employee_id>/', views.remove_employee, name='remove_employee'),
    path('employee/<int:employee_id>/update-status/', views.update_employee_status, name='update_employee_status'),
]