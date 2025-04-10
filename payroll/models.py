from django.db import models

class Employee(models.Model):
    ACTIVE_STATUS = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('probation', 'Probation'),
    ]

    DEPARTMENT_CHOICES = [
        ('engineering', 'Engineering'),
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('human_resource', 'Human Resource'),
        ('finance', 'Finance'),
        ('design', 'Design'),
    ]

    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    hire_date = models.DateField()
    department = models.CharField(
        max_length=20,
        choices=DEPARTMENT_CHOICES,
        null=True,
        blank=True,
    )
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.CharField(
        max_length=10,
        choices=ACTIVE_STATUS,
        default='active',
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"