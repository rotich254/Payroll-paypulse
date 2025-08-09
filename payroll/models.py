from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Function to generate a default avatar path or handle missing avatars
def default_avatar_path():
    return 'avatars/default_avatar.png' # Make sure this default image exists in your media/avatars/ directory

class Company(models.Model):
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)

    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(default=default_avatar_path, upload_to='avatars/')
    bio = models.TextField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    # Add any other profile-specific fields you need

    def __str__(self):
        return f'{self.user.username} Profile'

    # Optional: Method to get avatar URL, handling cases where avatar might be missing
    @property
    def avatar_url(self):
        try:
            url = self.avatar.url
        except ValueError: # Catches if self.avatar is None or has no file associated
            url = default_avatar_path() # Or link to a static default avatar if preferred
            # If using static, ensure default_avatar.png is in your staticfiles dirs
            # from django.templatetags.static import static
            # url = static('images/default_avatar.png')
        return url

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    # Use get_or_create to ensure a profile exists or is created.
    # This handles new user creation and updates to existing users (e.g. during login)
    # where a profile might be missing.
    Profile.objects.get_or_create(user=instance)

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


# Add after your existing models
class Report(models.Model):
    REPORT_TYPES = [
        ('payroll', 'Payroll Summary'),
        ('department', 'Department Summary'),
        ('employee', 'Employee Summary'),
        ('tax', 'Tax Summary'),
    ]

    REPORT_STATUS = [
        ('generated', 'Generated'),
        ('failed', 'Failed'),
        ('processing', 'Processing'),
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=REPORT_TYPES)
    generated_date = models.DateTimeField(auto_now_add=True)
    period_start = models.DateField()
    period_end = models.DateField()
    department = models.CharField(max_length=20, choices=Employee.DEPARTMENT_CHOICES, null=True, blank=True)
    file = models.FileField(upload_to='reports/')
    status = models.CharField(max_length=20, choices=REPORT_STATUS, default='processing')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.generated_date.strftime('%Y-%m-%d')}"
