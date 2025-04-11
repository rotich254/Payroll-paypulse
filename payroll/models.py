from django.db import models
from django.utils import timezone

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

class Payroll(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls')
    pay_period = models.DateField(
        default=timezone.now,
        help_text="Period for which this payroll is generated"
    )
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2)
    total_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES, 
        default='pending'
    )
    payment_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pay_period', 'employee__first_name']
        unique_together = ['employee', 'pay_period']

    def save(self, *args, **kwargs):
        # Set initial values if not provided
        if not self.pay_period and self.employee:
            self.pay_period = self.employee.hire_date

        # Always sync gross_salary with employee's current salary
        if self.employee and not self.gross_salary:
            self.gross_salary = self.employee.salary

        # Calculate net salary
        self.net_salary = (self.gross_salary + self.total_allowances) - self.total_deductions
        
        # Set payment date when status changes to paid
        if self.payment_status == 'paid' and not self.payment_date:
            self.payment_date = timezone.now().date()
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payroll for {self.employee} - {self.pay_period.strftime('%B %Y')}"

    @property
    def is_paid(self):
        return self.payment_status == 'paid'

    @property
    def payment_status_display(self):
        return dict(self.PAYMENT_STATUS_CHOICES)[self.payment_status]