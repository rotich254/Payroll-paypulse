from django import forms
from .models import Employee, Profile
from django.contrib.auth.models import User

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'readonly': 'readonly'})
        self.fields['first_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['last_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'bio', 'phone_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['avatar'].widget.attrs.update({'class': 'form-control'})
        self.fields['bio'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        self.fields['phone_number'].widget.attrs.update({'class': 'form-control'})

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