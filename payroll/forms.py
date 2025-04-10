from django import forms
from .models import Employee

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = '__all__'
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'id': 'firstName'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'id': 'lastName'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'id': 'email'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'id': 'phoneNumber'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'id': 'hireDate', 'type': 'date'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'id': 'position'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control', 'id': 'salary'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'id': 'notes', 'rows': 2}),
        }