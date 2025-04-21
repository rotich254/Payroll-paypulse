from django.contrib import admin
from .models import Employee, Payroll, Report

# Register your models here.
admin.site.register(Employee)
admin.site.register(Payroll)
admin.site.register(Report)
