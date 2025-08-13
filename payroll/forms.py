from django import forms
from .models import Company, Employee, Payroll
from django.utils import timezone

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'logo']

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = '__all__'

class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = ['employee', 'pay_period', 'total_allowances', 'total_deductions']
        widgets = {
            'pay_period': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'pay_date'}),
            'employee': forms.Select(attrs={'class': 'form-select select2', 'id': 'employee'}),
            'total_allowances': forms.NumberInput(attrs={'class': 'form-control', 'id': 'total_allowances'}),
            'total_deductions': forms.NumberInput(attrs={'class': 'form-control', 'id': 'total_deductions'}),
        }

    def clean_pay_period(self):
        pay_period = self.cleaned_data.get('pay_period')
        if pay_period and pay_period < timezone.now().date():
            raise forms.ValidationError("Pay date cannot be in the past.")
        return pay_period

    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get('employee')
        pay_period = cleaned_data.get('pay_period')

        if employee and pay_period:
            if Payroll.objects.filter(
                employee=employee,
                pay_period__year=pay_period.year,
                pay_period__month=pay_period.month
            ).exists():
                raise forms.ValidationError(
                    f'A payroll record already exists for {employee} for {pay_period.strftime("%B %Y")}.'
                )
        return cleaned_data
