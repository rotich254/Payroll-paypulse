from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid

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
    reference_id = models.CharField(
        max_length=50,  # Increased length to accommodate UUID
        unique=True,
        help_text="Unique reference ID for this payroll",
        editable=False  # Prevent manual editing
    )

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
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    health_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    retirement_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    retirement_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['-pay_period', 'employee__first_name']
        unique_together = ['employee', 'pay_period']

    def save(self, *args, **kwargs):
        # Generate unique reference ID if not set
        if not self.reference_id:
            year = self.pay_period.year if self.pay_period else timezone.now().year
            month = self.pay_period.month if self.pay_period else timezone.now().month
            employee_id = str(self.employee.id).zfill(4)  # Pad employee ID with zeros
            unique_id = str(uuid.uuid4())[:6]  # Use first 6 chars of UUID
            self.reference_id = f"PAY-{year}{month:02d}-{employee_id}-{unique_id}"

        # Set initial values if not provided
        if not self.pay_period and self.employee:
            self.pay_period = self.employee.hire_date

        # Always sync gross_salary with employee's current salary
        if self.employee and not self.gross_salary:
            self.gross_salary = self.employee.salary

        # Convert all values to Decimal to avoid float operations
        gross_salary = Decimal(str(self.gross_salary))
        total_allowances = Decimal(str(self.total_allowances))
        total_deductions = Decimal(str(self.total_deductions))
        tax_rate = Decimal(str(self.tax_rate))
        health_insurance = Decimal(str(self.health_insurance))
        retirement_rate = Decimal(str(self.retirement_rate))

        # Calculate tax amount
        self.tax_amount = (gross_salary * tax_rate / Decimal('100'))
        
        # Calculate retirement amount
        self.retirement_amount = (gross_salary * retirement_rate / Decimal('100'))
        
        # Calculate net salary with all deductions
        self.net_salary = (
            gross_salary 
            + total_allowances 
            - total_deductions 
            - self.tax_amount 
            - health_insurance 
            - self.retirement_amount
        )
        
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