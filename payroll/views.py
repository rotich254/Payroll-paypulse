from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import models  # Add this import
from .models import Employee, Payroll
from .forms import EmployeeForm
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from decimal import Decimal, InvalidOperation  # Add InvalidOperation
from django.utils import timezone
from datetime import datetime
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.urls import reverse
import tempfile
from django.db.models import Sum, Count
import json

# Replace WeasyPrint imports with ReportLab
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO


def index(request):
    # Get counts for all employee statuses
    total_employees = Employee.objects.count()
    active_employees = Employee.objects.filter(is_active='active').count()
    on_leave_employees = Employee.objects.filter(is_active='on_leave').count()
    probation_employees = Employee.objects.filter(is_active='probation').count()

    # Get the 5 most recently PAID payroll records, ordered by payment date
    recent_payrolls = Payroll.objects.filter(payment_status='paid').select_related('employee').order_by('-payment_date')[:5]

    # Get the 6 nearest upcoming PENDING payrolls
    today = timezone.now().date()
    upcoming_pending_payrolls = Payroll.objects.filter(
        payment_status='pending',
        pay_period__gte=today  # Filter for pay periods today or in the future
    ).exclude(payment_status='paid').select_related('employee').order_by('pay_period')[:5]

    context = {
        'total_employees': total_employees,
        'upcoming_pending_payrolls': upcoming_pending_payrolls,  # Renamed context variable
        'recent_payrolls': recent_payrolls,  # Add recent payrolls to context
        'active_employees': active_employees,
        'on_leave_employees': on_leave_employees,
        'probation_employees': probation_employees,
        'upcoming_periods': get_payroll_periods(),
    }

    # Departmental Payroll Distribution
    department_data = {}
    for employee in Employee.objects.filter(is_active='active'):
        department = employee.get_department_display()
        payroll_records = Payroll.objects.filter(employee=employee, payment_status='paid')
        total_salary = sum(record.net_salary for record in payroll_records)
        if department in department_data:
            department_data[department] += total_salary
        else:
            department_data[department] = total_salary

    context['department_data'] = department_data
    # Get department data for charts
    department_data = Employee.objects.values('department').annotate(
    total_payroll=Sum('salary'),
    employee_count=Count('id')
    )
    
    # Prepare data for charts
    departments = [dict(Employee.DEPARTMENT_CHOICES)[dept['department']] for dept in department_data]
    payroll_by_department = [float(dept['total_payroll'] or 0) for dept in department_data]
    employees_by_department = [dept['employee_count'] for dept in department_data]
    
    context.update({
    'total_employees': total_employees,
    'active_employees': active_employees,
    'on_leave_employees': on_leave_employees,
    'probation_employees': probation_employees,
    'upcoming_pending_payrolls': upcoming_pending_payrolls,
    'recent_payrolls': recent_payrolls,
    'upcoming_periods': get_payroll_periods(),
    # Add chart data to context
    'departments': json.dumps(departments),
    'payroll_by_department': json.dumps(payroll_by_department),
    'employees_by_department': json.dumps(employees_by_department),
    })

    return render(request, 'index.html', context)

def employee_list(request):
    status_filter = request.GET.get('status', 'all')
    department_filter = request.GET.get('department', 'all')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'id')  # Changed default from 'name' to 'id'
    page = request.GET.get('page', 1)
    
    employees = Employee.objects.all()
    
    # Apply search filter
    if search_query:
        employees = employees.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    # Apply sorting - modified to always sort by ID first
    if sort_by == 'salary':
        employees = employees.order_by('id', '-salary')
    elif sort_by == 'name':
        employees = employees.order_by('id', 'first_name', 'last_name')
    elif sort_by == 'department':
        employees = employees.order_by('id', 'department', 'first_name')
    else:
        employees = employees.order_by('id')  # Default sort by ID
    
    # Apply additional filters
    if status_filter != 'all':
        employees = employees.filter(is_active=status_filter)
    
    if department_filter != 'all':
        employees = employees.filter(department=department_filter)

    # Pagination
    paginator = Paginator(employees, 10)  # Show 10 employees per page
    try:
        employees_page = paginator.page(page)
    except PageNotAnInteger:
        employees_page = paginator.page(1)
    except EmptyPage:
        employees_page = paginator.page(paginator.num_pages)

    context = {
        'employees': employees_page,
        'current_status': status_filter,
        'current_department': department_filter,
        'search_query': search_query,
        'current_sort': sort_by,
        'status_choices': Employee.ACTIVE_STATUS,
        'department_choices': Employee.DEPARTMENT_CHOICES,
        'total_employees': employees.count(),
        'title': 'Employee List'
    }
    
    return render(request, 'payroll/employees.html', context)

def add_employee(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            try:
                employee = form.save()
                messages.success(request, f'Employee {employee.first_name} {employee.last_name} added successfully.')
                return redirect('employee_list')
            except Exception as e:
                messages.error(request, f'Error saving employee: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = EmployeeForm()
    
    context = {
        'form': form,
        'title': 'Add Employee',
        'department_choices': Employee.DEPARTMENT_CHOICES,
        'status_choices': Employee.ACTIVE_STATUS,
    }
    return render(request, 'payroll/add_employee.html', context)

def edit_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employee {employee.first_name} {employee.last_name} updated successfully.')
            return redirect('employee_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EmployeeForm(instance=employee)
        
    context = {
        'form': form,
        'employee': employee,
        'title': 'Edit Employee'
    }
    return render(request, 'payroll/edit_employee.html', context)

@require_POST
@csrf_protect
def remove_employee(request, employee_id):
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        employee.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    
@require_POST
@csrf_protect
def update_employee_status(request, employee_id):
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        new_status = request.POST.get('status')
        
        if new_status in dict(Employee.ACTIVE_STATUS):
            employee.is_active = new_status
            employee.save()
            return JsonResponse({
                'status': 'success',
                'new_status': new_status
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid status value'
            }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
        
        
def payroll(request):
    show_all = request.GET.get('show_all', False)
    search_query = request.GET.get('search', '').strip()
    active_employees = Employee.objects.filter(is_active='active').order_by('first_name', 'last_name')
    
    # Get base payroll queryset, ordered by creation date (newest first)
    payroll_history = Payroll.objects.select_related('employee').order_by('-created_at')
    
    # Apply search filter if query exists
    if search_query:
        # First try exact reference ID match
        reference_match = payroll_history.filter(
            Q(reference_id__iexact=search_query) |  # Exact match (case-insensitive)
            Q(reference_id__icontains=search_query)  # Partial match (case-insensitive)
        )
        
        if reference_match.exists():
            payroll_history = reference_match
        else:
            # If no reference ID match, try name search
            name_parts = search_query.split()
            if len(name_parts) > 1:
                # Multiple words - search first and last name
                payroll_history = payroll_history.filter(
                    Q(employee__first_name__icontains=name_parts[0]) & 
                    Q(employee__last_name__icontains=name_parts[1]) |
                    Q(employee__first_name__icontains=name_parts[1]) & 
                    Q(employee__last_name__icontains=name_parts[0])
                )
            else:
                # Single word - search in first name or last name
                payroll_history = payroll_history.filter(
                    Q(employee__first_name__icontains=search_query) |
                    Q(employee__last_name__icontains=search_query)
                )
    
    # Apply pagination if not showing all
    if not show_all:
        payroll_history = payroll_history[:10]
    
    # Calculate summary statistics
    total_payroll = Payroll.objects.aggregate(total=models.Sum('gross_salary'))['total'] or 0
    total_employees = Employee.objects.filter(is_active='active').count()
    paid_count = Payroll.objects.filter(payment_status='paid').count()
    pending_count = Payroll.objects.filter(payment_status='pending').count()
    
    context = {
        'active_employees': active_employees,
        'payroll_history': payroll_history,
        'show_all': show_all,
        'search_query': search_query,
        'total_payrolls': Payroll.objects.count(),
        'total_payroll': "{:,.2f}".format(total_payroll),
        'total_employees': total_employees,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'today_date': timezone.now().strftime('%Y-%m-%d'), # Add today's date for min attribute
    }
    return render(request, 'payroll/payroll.html', context)

def generate_payroll(request):
    if request.method == 'POST':
        try:
            employee_id = request.POST.get('employee')
            pay_date_str = request.POST.get('pay_date')

            if not employee_id or not pay_date_str:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Employee and pay date are required.'
                }, status=400)

            # Parse the date string to a datetime object
            try:
                pay_date = datetime.strptime(pay_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid date format. Use YYYY-MM-DD'
                }, status=400)

            # Validate that the pay date is not in the past
            today = timezone.now().date()
            if pay_date < today:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Pay date cannot be in the past.'
                }, status=400)

            # Check if payroll already exists for this employee in the same month
            existing_payroll = Payroll.objects.filter(
                employee_id=employee_id,
                pay_period__year=pay_date.year,
                pay_period__month=pay_date.month
            ).first()

            if existing_payroll:
                return JsonResponse({
                    'status': 'error',
                    'message': f'A payroll record already exists for this employee for {pay_date.strftime("%B %Y")}.'
                }, status=400)

            employee = get_object_or_404(Employee, id=employee_id)
            allowances = Decimal(request.POST.get('total_allowances', '0.00'))

            # Create payroll record with defaults
            payroll = Payroll.objects.create(
                employee=employee,
                pay_period=pay_date,
                gross_salary=employee.salary,
                total_allowances=allowances,
                tax_rate=Decimal('16.00'),
                health_insurance=Decimal('2000.00'),
                retirement_rate=Decimal('5.00'),
                payment_status='pending'
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Payroll created successfully',
                'data': {
                    'detail_url': reverse('payroll_detail', args=[payroll.id]),
                    'reference_id': payroll.reference_id
                }
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error creating payroll: {str(e)}'
            }, status=400)

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)

def get_payroll_periods():
    """Generate payroll periods for the next few months"""
    today = timezone.now().date()
    periods = []
    for month in range(3):  # Next 3 months
        date = today.replace(day=1) + timezone.timedelta(days=32*month)
        periods.extend([
            {
                'value': f"{date.year}-{date.month}-1",
                'label': f"{date.strftime('%B')} 1-15, {date.year}"
            },
            {
                'value': f"{date.year}-{date.month}-2",
                'label': f"{date.strftime('%B')} 16-{(date.replace(day=1) + timezone.timedelta(days=32)).replace(day=1).day-1}, {date.year}"
            }
        ])
    return periods

def payroll_detail(request, payroll_id):
    """View for displaying detailed payroll information"""
    payroll = get_object_or_404(Payroll.objects.select_related('employee'), id=payroll_id)
    
    context = {
        'payroll': payroll,
        'title': f'Payroll Detail - {payroll.pay_period.strftime("%B %Y")}',
        'employee': payroll.employee,
        'department': dict(Employee.DEPARTMENT_CHOICES).get(payroll.employee.department, ''),
        'status': dict(Payroll.PAYMENT_STATUS_CHOICES).get(payroll.payment_status, ''),
        'today': timezone.now().date(),  # Add today's date to context
    }
    return render(request, 'payroll/payroll_detail.html', context)

def generate_payroll_pdf(request, payroll_id):
    """Generate PDF for a specific payroll record using ReportLab"""
    try:
        payroll = get_object_or_404(Payroll.objects.select_related('employee'), id=payroll_id)
        
        response = HttpResponse(content_type='application/pdf')
        filename = f"payroll_{payroll.employee.last_name}_{payroll.pay_period.strftime('%Y_%m')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Create PDF document
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        header_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Add company header
        elements.append(Paragraph('Your Company Name', title_style))
        elements.append(Paragraph('Payroll Statement', header_style))
        elements.append(Spacer(1, 20))
        
        # Employee information table
        employee_data = [
            ['Employee Information', '', '', ''],
            ['Name:', f"{payroll.employee.first_name} {payroll.employee.last_name}", 'Payment Status:', 
             f"{payroll.payment_status_display.upper()}" if not payroll.is_paid else 'PAID'],
            ['Employee ID:', str(payroll.employee.id), 'Pay Period:', 
             payroll.pay_period.strftime("%B %d, %Y")],
            ['Status:', payroll.payment_status_display, 'Payment Date:', 
             payroll.payment_date.strftime("%B %d, %Y") if payroll.payment_date else 'Pending']
        ]
        
        employee_table = Table(employee_data, colWidths=[100, 150, 100, 150])
        employee_table.setStyle(TableStyle([
            ('GRID', (0, 1), (-1, -1), 1, colors.black),
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTWEIGHT', (0, 0), (-1, 0), 'BOLD'),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('TEXTCOLOR', (3, 1), (3, 1), colors.red if not payroll.is_paid else colors.green),
            ('FONTWEIGHT', (3, 1), (3, 1), 'BOLD'),
        ]))
        elements.append(employee_table)
        elements.append(Spacer(1, 20))
        
        # Salary breakdown table
        salary_data = [
            ['Earnings & Deductions', 'Amount'],
            ['Basic Salary', f"KSh {payroll.gross_salary:,.2f}"],
            ['Allowances', f"KSh {payroll.total_allowances:,.2f}"],
            ['Subtotal (Gross)', f"KSh {(payroll.gross_salary + payroll.total_allowances):,.2f}"],
            ['', ''],
            ['Deductions:', ''],
            ['Tax ({:.1f}%)'.format(float(payroll.tax_rate)), f"KSh {payroll.tax_amount:,.2f}"],
            ['Health Insurance', f"KSh {payroll.health_insurance:,.2f}"],
            ['Retirement ({:.1f}%)'.format(float(payroll.retirement_rate)), f"KSh {payroll.retirement_amount:,.2f}"],
            ['Other Deductions', f"KSh {payroll.total_deductions:,.2f}"],
            ['Total Deductions', f"KSh {(payroll.tax_amount + payroll.health_insurance + payroll.retirement_amount + payroll.total_deductions):,.2f}"],
            ['', ''],
            ['Net Salary', f"KSh {payroll.net_salary:,.2f}"]
        ]
        
        salary_table = Table(salary_data, colWidths=[300, 200])
        salary_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, 0), 1, colors.black),
            ('GRID', (0, -1), (-1, -1), 1, colors.black),
            ('LINEBELOW', (0, 2), (-1, 2), 1, colors.black),
            ('LINEBELOW', (0, -3), (-1, -3), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('BACKGROUND', (0, 5), (-1, 5), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTWEIGHT', (0, 0), (-1, 0), 'BOLD'),
            ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
            ('NOSPLIT', (0, 0), (-1, -1)),
        ]))
        elements.append(salary_table)
        
        # Add footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}", normal_style))
        
        if not payroll.is_paid:
            # Add a prominent watermark
            elements.append(Paragraph(
                "*** DRAFT - NOT YET PAID ***",
                ParagraphStyle(
                    'watermark',
                    parent=normal_style,
                    textColor=colors.red,
                    fontSize=16,
                    alignment=1,  # Center alignment
                    spaceBefore=20,
                    spaceAfter=20
                )
            ))
            elements.append(Paragraph("*** This is not a payment confirmation ***", 
                ParagraphStyle('warning', parent=normal_style, textColor=colors.red)))
        
        # Build and return PDF
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response
        
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('payroll_detail', payroll_id=payroll_id)

@require_POST
@csrf_protect
def mark_payroll_paid(request, payroll_id):
    try:
        payroll = get_object_or_404(Payroll, id=payroll_id)
        today = timezone.now().date()
        
        # Check if we're trying to pay before the pay date
        if payroll.pay_period > today:
            return JsonResponse({
                'status': 'error',
                'message': f'Cannot mark as paid before the pay date ({payroll.pay_period.strftime("%B %d, %Y")})'
            }, status=400)
            
        if payroll.payment_status == 'pending':
            payroll.payment_status = 'paid'
            payroll.payment_date = today
            payroll.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payroll marked as paid successfully'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Payroll is already paid'
        }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

def paid_payroll_list(request):
    """View to display a list of all paid payrolls with pagination."""
    paid_payrolls_list = Payroll.objects.filter(payment_status='paid').select_related('employee').order_by('-payment_date')
    
    paginator = Paginator(paid_payrolls_list, 15)  # Show 15 paid payrolls per page
    page = request.GET.get('page')
    
    try:
        paid_payrolls = paginator.page(page)
    except PageNotAnInteger:
        paid_payrolls = paginator.page(1)
    except EmptyPage:
        paid_payrolls = paginator.page(paginator.num_pages)
        
    context = {
        'paid_payrolls': paid_payrolls,
        'title': 'Paid Payroll History'
    }
    return render(request, 'payroll/paid_payroll_list.html', context)

def pending_payroll_list(request):
    """View to display a list of all pending payrolls with pagination."""
    today = timezone.now().date()
    show_all = request.GET.get('show_all', False)
    pending_payrolls_list = Payroll.objects.filter(
        payment_status='pending',
        pay_period__gte=today  # Optional: Only show pending for today or future pay periods
    ).select_related('employee').order_by('pay_period')  # Order by nearest pay period first

    if not show_all:
        paginator = Paginator(pending_payrolls_list, 15)  # Show 15 pending payrolls per page
        page = request.GET.get('page')

        try:
            pending_payrolls = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            pending_payrolls = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            pending_payrolls = paginator.page(paginator.num_pages)
    else:
        pending_payrolls = pending_payrolls_list

    context = {
        'pending_payrolls': pending_payrolls,
        'title': 'Pending Payroll List',
        'show_all': show_all,
    }
    return render(request, 'payroll/pending_payroll_list.html', context) # Render renamed template
