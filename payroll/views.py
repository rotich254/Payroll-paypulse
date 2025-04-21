from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import models  # Add this import
from .models import Employee, Payroll, Report
from .forms import EmployeeForm
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from decimal import Decimal, InvalidOperation  # Add InvalidOperation
from django.utils import timezone
from datetime import datetime, timedelta
from django.template.loader import render_to_string
from django.urls import reverse
import tempfile
from django.db.models import Sum, Count
import json
from django.db.models import Sum

# Replace WeasyPrint imports with ReportLab
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter # Keep letter for potential reference, but remove landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# Remove ReportLab platypus imports
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak 
from io import BytesIO
from django.core.files.base import ContentFile  # Add this import
import logging # Add logging import

# +++ Add Openpyxl imports +++
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# Configure basic logging (consider moving to settings.py for production)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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


def reports(request):
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        date_range = request.POST.get('date_range')
        department = request.POST.get('department')
        
        # Calculate date range
        today = timezone.now().date()
        if date_range == 'this_month':
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        elif date_range == 'last_month':
            end_date = today.replace(day=1) - timedelta(days=1)
            start_date = end_date.replace(day=1)
        elif date_range == 'this_quarter':
            quarter = (today.month - 1) // 3
            start_date = today.replace(month=quarter * 3 + 1, day=1)
            end_date = today
        elif date_range == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today
        else:
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')

        # Generate report based on type
        if report_type == 'payroll':
            return generate_payroll_report(request, start_date, end_date, department)
        elif report_type == 'department':
            return generate_department_report(request, start_date, end_date, department)
        elif report_type == 'employee':
            return generate_employee_report(request, start_date, end_date, department)
        elif report_type == 'tax':
            return generate_tax_report(request, start_date, end_date, department)

    # Get all reports for display
    recent_reports = Report.objects.all().order_by('-generated_date')[:10]
    departments = Employee.DEPARTMENT_CHOICES

    return render(request, 'reports.html', {
        'recent_reports': recent_reports,
        'departments': departments,
    })

def generate_payroll_report(request, start_date, end_date, department=None):
    logging.info(f"Generating Full Excel Payroll Report for period {start_date} to {end_date}, department: {department}")
    try:
        # --- Date Validation ---
        if isinstance(start_date, str):
            try: start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid start date format."); return redirect('reports')
        if isinstance(end_date, str):
            try: end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid end date format."); return redirect('reports')
        if not start_date or not end_date: messages.error(request, "Start/End date required."); return redirect('reports')
        if start_date > end_date: messages.error(request, "Start date cannot be after end date."); return redirect('reports')

        # --- Query Payroll Data (No initial aggregation) ---
        payrolls_query = Payroll.objects.filter(
            pay_period__range=[start_date, end_date]
        ).select_related('employee').order_by('employee__first_name', 'employee__last_name', 'pay_period') # Order results

        if department and department != 'all':
            payrolls_query = payrolls_query.filter(employee__department=department)

        logging.info(f"Found {payrolls_query.count()} individual payroll records matching criteria.")

        if not payrolls_query.exists():
            messages.warning(request, "No payroll records found for the selected criteria.")
            return redirect('reports')

        # --- Generate Excel Workbook ---
        wb = Workbook()
        ws = wb.active
        ws.title = "Payroll Details"

        # --- Styles ---
        title_font = Font(bold=True, name='Calibri', size=14)
        period_font = Font(name='Calibri', size=11)
        table_header_font = Font(bold=True, name='Calibri', size=11)
        total_font = Font(bold=True, name='Calibri', size=11)
        currency_format = '"KSh"#,##0.00;[Red]"KSh"-#,##0.00'
        date_format = 'yyyy-mm-dd' # Excel date format string
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        right_alignment = Alignment(horizontal='right', vertical='center')
        left_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        header_fill = PatternFill(start_color='FFC0C0C0', end_color='FFC0C0C0', fill_type='solid') # Header grey
        total_fill = PatternFill(start_color='FFE0E0E0', end_color='FFE0E0E0', fill_type='solid') # Lighter grey for totals
        thin_border_side = Side(style='thin')
        thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

        # --- Write Main Title and Info ---
        current_row = 1
        # Adjust column span based on headers list length below
        max_cols = 9 # Number of columns in the headers list
        ws.cell(row=current_row, column=1, value="Payroll Detail Report")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=max_cols)
        ws.cell(row=current_row, column=1).font = title_font; ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 1
        ws.cell(row=current_row, column=1, value=f"Period: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=max_cols)
        ws.cell(row=current_row, column=1).font = period_font; ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 1
        if department and department != 'all':
             ws.cell(row=current_row, column=1, value=f"Department: {dict(Employee.DEPARTMENT_CHOICES).get(department, 'N/A')}")
             ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=max_cols)
             ws.cell(row=current_row, column=1).font = period_font; ws.cell(row=current_row, column=1).alignment = center_alignment
             current_row += 1
        current_row += 1 # Spacer row

        # --- Write Table Header ---
        headers = ['Employee', 'Department', 'Pay Period', 'Reference ID', 'Gross Salary', 'Allowances', 'Total Deductions', 'Net Salary', 'Status']
        header_row_num = current_row
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=header_row_num, column=col_idx, value=header_text)
            cell.font = table_header_font; cell.fill = header_fill; cell.alignment = center_alignment; cell.border = thin_border
        current_row += 1
        data_start_row = current_row

        # --- Write Payroll Data Rows ---
        total_gross = Decimal('0.00'); total_allowances = Decimal('0.00')
        total_deductions_sum = Decimal('0.00'); total_net = Decimal('0.00')

        for payroll in payrolls_query:
            # Calculate total deductions for this specific payroll record
            current_payroll_deductions = (payroll.tax_amount + payroll.health_insurance +
                                       payroll.retirement_amount + payroll.total_deductions)

            row_data = [
                f"{payroll.employee.first_name} {payroll.employee.last_name}",
                payroll.employee.get_department_display(),
                payroll.pay_period, # Keep as date object for formatting
                payroll.reference_id,
                float(payroll.gross_salary),
                float(payroll.total_allowances),
                float(current_payroll_deductions),
                float(payroll.net_salary),
                payroll.get_payment_status_display()
            ]
            data_row_num = current_row
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=data_row_num, column=col_idx, value=value)
                cell.border = thin_border
                # Apply formatting based on column index
                if col_idx == 3: # Pay Period
                    cell.number_format = date_format
                    cell.alignment = center_alignment
                elif col_idx in [5, 6, 7, 8]: # Currency columns
                    cell.number_format = currency_format
                    cell.alignment = right_alignment
                elif col_idx in [1, 2, 4]: # Text columns (Employee, Dept, Ref ID)
                    cell.alignment = left_alignment
                elif col_idx == 9: # Status
                    cell.alignment = center_alignment
            current_row += 1

            # Accumulate totals
            total_gross += payroll.gross_salary
            total_allowances += payroll.total_allowances
            total_deductions_sum += current_payroll_deductions
            total_net += payroll.net_salary

        # --- Write Grand Total Row ---
        total_row_data = [
            'Grand Total', '', '', '', # Span first 4 columns conceptually
            float(total_gross), float(total_allowances),
            float(total_deductions_sum), float(total_net), '' # Blank for status col
        ]
        total_row_num = current_row
        # Apply styles to the total row
        for col_idx, value in enumerate(total_row_data, 1):
            cell = ws.cell(row=total_row_num, column=col_idx, value=value)
            cell.font = total_font; cell.fill = total_fill; cell.border = thin_border
            if col_idx in [5, 6, 7, 8]: # Currency columns
                cell.number_format = currency_format
                cell.alignment = right_alignment
            elif col_idx == 1: # 'Grand Total' label
                 # Merge first few cells for the label if desired, or just align right in first cell
                 # ws.merge_cells(start_row=total_row_num, start_column=1, end_row=total_row_num, end_column=4)
                 # For simplicity, just align label right in first cell:
                 cell.alignment = right_alignment
            else: # Other blank cells in total row
                cell.alignment = center_alignment

        # --- Adjust Column Widths ---
        ws.column_dimensions[get_column_letter(1)].width = 25 # Employee
        ws.column_dimensions[get_column_letter(2)].width = 18 # Department
        ws.column_dimensions[get_column_letter(3)].width = 12 # Pay Period
        ws.column_dimensions[get_column_letter(4)].width = 28 # Reference ID
        ws.column_dimensions[get_column_letter(5)].width = 15 # Gross Salary
        ws.column_dimensions[get_column_letter(6)].width = 15 # Allowances
        ws.column_dimensions[get_column_letter(7)].width = 16 # Total Deductions
        ws.column_dimensions[get_column_letter(8)].width = 15 # Net Salary
        ws.column_dimensions[get_column_letter(9)].width = 10 # Status

        # --- Freeze Panes ---
        ws.freeze_panes = ws.cell(row=data_start_row, column=1) # Freeze header row

        # --- Save Workbook to Buffer ---
        logging.info("Saving Payroll Detail Report Workbook to buffer...")
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # --- Create Report Record ---
        report_name = f"Payroll_Detail_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all': report_name += f"_{department}"
        report_name += f"_{datetime.now().strftime('%H%M%S')}"
        file_name = f"{report_name}.xlsx"
        # Ensure Report model is imported: from .models import Report
        report = Report.objects.create(name=report_name, type='payroll', period_start=start_date, period_end=end_date, department=department if department != 'all' else None, status='generated')
        # Ensure ContentFile is imported: from django.core.files.base import ContentFile
        report.file.save(file_name, ContentFile(excel_data))
        logging.info(f"Payroll Detail report '{file_name}' saved successfully.")

        # --- Return HTTP Response ---
        # Ensure HttpResponse is imported: from django.http import HttpResponse
        response = HttpResponse(excel_data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
    except ImportError:
        logging.error("openpyxl library not found."); messages.error(request, "Excel generation failed: Required library 'openpyxl' not found."); return redirect('reports')
    except Exception as e:
        logging.error(f"Error generating Excel payroll detail report: {str(e)}", exc_info=True); messages.error(request, f'Error generating payroll report: {str(e)}'); return redirect('reports')

def generate_department_report(request, start_date, end_date, department=None):
    logging.info(f"Generating Excel department report for period {start_date} to {end_date}, department: {department}")
    try:
        # --- Date Validation --- 
        if isinstance(start_date, str):
            try: start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid start date format."); return redirect('reports')
        if isinstance(end_date, str):
            try: end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid end date format."); return redirect('reports')
        if not start_date or not end_date: messages.error(request, "Start/End date required."); return redirect('reports')
        if start_date > end_date: messages.error(request, "Start date cannot be after end date."); return redirect('reports')

        # --- Generate Excel Workbook --- 
        wb = Workbook()
        ws = wb.active
        ws.title = "Department Report"

        # --- Styles (Assuming availability or redefine) ---
        title_font = Font(bold=True, name='Calibri', size=14)
        period_font = Font(name='Calibri', size=11)
        dept_header_font = Font(bold=True, name='Calibri', size=13)
        table_header_font = Font(bold=True, name='Calibri', size=11)
        total_font = Font(bold=True, name='Calibri', size=10)
        summary_header_font = Font(bold=True, name='Calibri', size=12)
        currency_format = '"KSh"#,##0.00;[Red]"KSh"-#,##0.00'
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        right_alignment = Alignment(horizontal='right', vertical='center')
        left_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        header_fill = PatternFill(start_color='FFC0C0C0', end_color='FFC0C0C0', fill_type='solid') # Header grey
        dept_fill = PatternFill(start_color='FFE0E0E0', end_color='FFE0E0E0', fill_type='solid') # Lighter grey for dept header
        total_fill = PatternFill(start_color='FFF0F0F0', end_color='FFF0F0F0', fill_type='solid') # Even lighter for totals
        thin_border_side = Side(style='thin')
        thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

        # --- Write Main Title and Info --- 
        current_row = 1
        ws.cell(row=current_row, column=1, value="Detailed Department Report")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8) # Merge across expected max columns
        ws.cell(row=current_row, column=1).font = title_font; ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 1
        ws.cell(row=current_row, column=1, value=f"Period: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
        ws.cell(row=current_row, column=1).font = period_font; ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 2 # Spacer row

        # --- Grand Totals Initialization ---
        grand_total_employees = 0
        grand_total_gross = Decimal('0.00')
        grand_total_net = Decimal('0.00')
        grand_total_tax = Decimal('0.00')
        grand_total_deductions = Decimal('0.00')
        data_found = False # Flag to track if any department data is processed

        # --- Loop through Departments --- 
        departments_to_process = Employee.DEPARTMENT_CHOICES
        if department and department != 'all':
            # Filter to only the selected department
            departments_to_process = [(code, name) for code, name in Employee.DEPARTMENT_CHOICES if code == department]
        
        if not departments_to_process:
             messages.warning(request, "Selected department code is invalid."); return redirect('reports')
             
        dept_table_headers = ['Employee Name', 'Status', 'Basic Salary', 'Gross Pay', 'Deductions', 'Tax', 'Net Salary']

        for dept_code, dept_name in departments_to_process:
            employees_in_dept = Employee.objects.filter(department=dept_code).order_by('first_name', 'last_name')
            
            dept_total_gross = Decimal('0.00'); dept_total_net = Decimal('0.00')
            dept_total_tax = Decimal('0.00'); dept_total_deductions = Decimal('0.00')
            employee_payroll_data = [] # Store rows for this department
            dept_employee_count = 0
            
            for employee in employees_in_dept:
                payrolls = Payroll.objects.filter(
                    employee=employee,
                    pay_period__range=[start_date, end_date]
                )
                # Aggregate payrolls for this employee within the period
                emp_agg = payrolls.aggregate(
                    sum_gross=Sum('gross_salary'), sum_tax=Sum('tax_amount'),
                    sum_health=Sum('health_insurance'), sum_retire=Sum('retirement_amount'),
                    sum_other_ded=Sum('total_deductions'), sum_net=Sum('net_salary')
                )
                emp_gross = emp_agg['sum_gross'] or Decimal('0.00')
                
                if emp_gross > 0: # Only include employee if they had payroll in period
                    data_found = True
                    dept_employee_count += 1
                    emp_tax = emp_agg['sum_tax'] or Decimal('0.00')
                    emp_deductions = ((emp_agg['sum_health'] or Decimal('0.00')) + 
                                      (emp_agg['sum_retire'] or Decimal('0.00')) + 
                                      (emp_agg['sum_other_ded'] or Decimal('0.00')))
                    emp_net = emp_agg['sum_net'] or Decimal('0.00')
                    
                    employee_payroll_data.append([
                        f"{employee.first_name} {employee.last_name}",
                        employee.get_is_active_display(),
                        float(employee.salary), # Basic from Employee model
                        float(emp_gross),
                        float(emp_deductions),
                        float(emp_tax),
                        float(emp_net)
                    ])
                    dept_total_gross += emp_gross
                    dept_total_net += emp_net
                    dept_total_tax += emp_tax
                    dept_total_deductions += emp_deductions

            # If we have data for this department, write its section
            if employee_payroll_data:
                # --- Department Header ---
                ws.cell(row=current_row, column=1, value=f"Department: {dept_name}")
                ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(dept_table_headers))
                dept_header_cell = ws.cell(row=current_row, column=1)
                dept_header_cell.font = dept_header_font; dept_header_cell.fill = dept_fill; 
                dept_header_cell.alignment = left_alignment; dept_header_cell.border = thin_border
                # Apply border to merged cells
                for col_idx in range(2, len(dept_table_headers) + 1): ws.cell(row=current_row, column=col_idx).border = thin_border
                current_row += 1
                
                # --- Employee Table Header ---
                dept_table_header_row = current_row
                for col_idx, header_text in enumerate(dept_table_headers, 1):
                    cell = ws.cell(row=dept_table_header_row, column=col_idx, value=header_text)
                    cell.font = table_header_font; cell.fill = header_fill; cell.alignment = center_alignment; cell.border = thin_border
                current_row += 1
                
                # --- Employee Data Rows ---
                for emp_row in employee_payroll_data:
                    data_row_num = current_row
                    for col_idx, value in enumerate(emp_row, 1):
                        cell = ws.cell(row=data_row_num, column=col_idx, value=value)
                        cell.border = thin_border
                        if col_idx in [3, 4, 5, 6, 7]: cell.number_format = currency_format; cell.alignment = right_alignment
                        elif col_idx == 2: cell.alignment = center_alignment # Status
                        else: cell.alignment = left_alignment # Name
                    current_row += 1
                    
                # --- Department Total Row ---
                dept_total_row_data = [
                    f"Department Total ({dept_employee_count} employees)", "", "", 
                    float(dept_total_gross), float(dept_total_deductions), 
                    float(dept_total_tax), float(dept_total_net)
                ]
                dept_total_row_num = current_row
                for col_idx, value in enumerate(dept_total_row_data, 1):
                    cell = ws.cell(row=dept_total_row_num, column=col_idx, value=value)
                    cell.font = total_font; cell.fill = total_fill; cell.border = thin_border
                    if col_idx in [4, 5, 6, 7]: cell.number_format = currency_format; cell.alignment = right_alignment
                    elif col_idx == 1: cell.alignment = left_alignment
                    else: cell.alignment = center_alignment # Blank cells
                current_row += 2 # Spacer

                # Update Grand Totals
                grand_total_employees += dept_employee_count
                grand_total_gross += dept_total_gross
                grand_total_net += dept_total_net
                grand_total_tax += dept_total_tax
                grand_total_deductions += dept_total_deductions
        
        # --- Handle No Data Case --- 
        if not data_found:
            logging.warning("No relevant department/payroll data found for the selected criteria.")
            messages.warning(request, "No data found for the selected criteria to generate a department report.")
            return redirect('reports')
            
        # --- Write Overall Summary Table --- 
        # Only add if more than one department was potentially processed or if 'all' was selected
        if (department == 'all' or not department) and grand_total_employees > 0:
            summary_start_row = current_row
            ws.cell(row=summary_start_row, column=1, value="Overall Summary").font = summary_header_font
            current_row += 1
            summary_headers = ['Total Employees', 'Total Gross Pay', 'Total Deductions', 'Total Tax', 'Total Net Pay']
            summary_header_row = current_row
            ws.column_dimensions[get_column_letter(1)].width = 20 # Adjust widths for summary table
            ws.column_dimensions[get_column_letter(2)].width = 18
            ws.column_dimensions[get_column_letter(3)].width = 18
            ws.column_dimensions[get_column_letter(4)].width = 18
            ws.column_dimensions[get_column_letter(5)].width = 18
            
            for col_idx, header_text in enumerate(summary_headers, 1):
                 cell = ws.cell(row=summary_header_row, column=col_idx, value=header_text)
                 cell.font = table_header_font; cell.fill = header_fill; cell.border = thin_border
                 cell.alignment = center_alignment
            current_row += 1
            summary_data_row = [
                grand_total_employees, 
                float(grand_total_gross), 
                float(grand_total_deductions), 
                float(grand_total_tax), 
                float(grand_total_net)
            ]
            summary_data_num = current_row
            for col_idx, value in enumerate(summary_data_row, 1):
                 cell = ws.cell(row=summary_data_num, column=col_idx, value=value)
                 cell.border = thin_border
                 if col_idx > 1: cell.number_format = currency_format; cell.alignment = right_alignment
                 else: cell.alignment = center_alignment # Total Employees

        # --- Adjust Final Column Widths for Department Employee Tables --- 
        # Base widths on dept_table_headers
        ws.column_dimensions[get_column_letter(1)].width = 25 # Employee Name
        ws.column_dimensions[get_column_letter(2)].width = 12 # Status
        ws.column_dimensions[get_column_letter(3)].width = 15 # Basic Salary
        ws.column_dimensions[get_column_letter(4)].width = 15 # Gross Pay
        ws.column_dimensions[get_column_letter(5)].width = 15 # Deductions
        ws.column_dimensions[get_column_letter(6)].width = 15 # Tax
        ws.column_dimensions[get_column_letter(7)].width = 15 # Net Salary
        # Ensure Col A is wide enough if summary table was also added
        if (department == 'all' or not department) and grand_total_employees > 0:
             ws.column_dimensions[get_column_letter(1)].width = max(25, 20) # Max of Employee Name and Total Employees header

        # --- Freeze Panes (Optional - applied to overall title) ---
        # ws.freeze_panes = ws.cell(row=3, column=1) # Freeze below main title/period

        # --- Save Workbook to Buffer --- 
        logging.info("Saving Department Report Workbook to buffer...")
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # --- Create Report Record --- 
        report_name = f"Department_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all': report_name += f"_{department}"
        report_name += f"_{datetime.now().strftime('%H%M%S')}"
        file_name = f"{report_name}.xlsx"
        report = Report.objects.create(name=report_name, type='department', period_start=start_date, period_end=end_date, department=department if department != 'all' else None, status='generated')
        report.file.save(file_name, ContentFile(excel_data))
        logging.info(f"Department report '{file_name}' saved successfully.")

        # --- Return HTTP Response --- 
        response = HttpResponse(excel_data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
    except ImportError:
        logging.error("openpyxl library not found."); messages.error(request, "Excel generation failed: Required library 'openpyxl' not found."); return redirect('reports')
    except Exception as e:
        logging.error(f"Error generating Excel department report: {str(e)}", exc_info=True); messages.error(request, f'Error generating department report: {str(e)}'); return redirect('reports')

def generate_employee_report(request, start_date, end_date, department=None):
    logging.info(f"Generating Excel employee report for period {start_date} to {end_date}, department: {department}")
    try:
        # --- Date Validation --- 
        if isinstance(start_date, str):
            try: start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid start date format."); return redirect('reports')
        if isinstance(end_date, str):
            try: end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid end date format."); return redirect('reports')
        if not start_date or not end_date: messages.error(request, "Start/End date required."); return redirect('reports')
        if start_date > end_date: messages.error(request, "Start date cannot be after end date."); return redirect('reports')

        # --- Query Employee Data --- 
        employees = Employee.objects.all()
        if department and department != 'all':
            employees = employees.filter(department=department)
        logging.info(f"Found {employees.count()} employees potentially matching criteria.")
        
        # --- Generate Excel Workbook --- 
        wb = Workbook()
        ws = wb.active
        ws.title = "Employee Report"

        # --- Styles --- 
        # (Using styles defined earlier or redefine if needed - assuming they are available from generate_tax_report scope)
        # Let's redefine for clarity in this function
        title_font = Font(bold=True, name='Calibri', size=14)
        period_font = Font(name='Calibri', size=11)
        employee_header_font = Font(bold=True, name='Calibri', size=12)
        table_header_font = Font(bold=True, name='Calibri', size=11)
        total_font = Font(bold=True, name='Calibri', size=10)
        metric_header_font = Font(bold=True, name='Calibri', size=11)
        currency_format = '"KSh"#,##0.00;[Red]"KSh"-#,##0.00'
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        right_alignment = Alignment(horizontal='right', vertical='center')
        left_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        header_fill = PatternFill(start_color='FFC0C0C0', end_color='FFC0C0C0', fill_type='solid') # Header grey
        employee_fill = PatternFill(start_color='FFE0E0E0', end_color='FFE0E0E0', fill_type='solid') # Lighter grey for emp header
        total_fill = PatternFill(start_color='FFF0F0F0', end_color='FFF0F0F0', fill_type='solid') # Even lighter for totals
        thin_border_side = Side(style='thin')
        thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

        # --- Write Main Title and Info --- 
        current_row = 1
        ws.cell(row=current_row, column=1, value="Employee Performance Report")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
        ws.cell(row=current_row, column=1).font = title_font; ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 1
        ws.cell(row=current_row, column=1, value=f"Period: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
        ws.cell(row=current_row, column=1).font = period_font; ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 1
        if department and department != 'all':
             ws.cell(row=current_row, column=1, value=f"Department: {dict(Employee.DEPARTMENT_CHOICES).get(department, 'N/A')}")
             ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
             ws.cell(row=current_row, column=1).font = period_font; ws.cell(row=current_row, column=1).alignment = center_alignment
             current_row += 1
        current_row += 1 # Spacer row

        # --- Loop through Employees and Write Data --- 
        data_added_for_any_employee = False
        payroll_headers = ['Pay Period', 'Basic Salary', 'Allowances', 'Gross Pay', 'Total Deductions', 'Net Pay', 'Status']
        metric_headers = ['Metric', 'Value']
        
        sorted_employees = employees.order_by('first_name', 'last_name')

        for employee in sorted_employees:
            payrolls = Payroll.objects.filter(
                employee=employee, 
                pay_period__range=[start_date, end_date]
            ).order_by('pay_period')

            if not payrolls.exists():
                logging.debug(f"No payroll data for employee {employee.id} in period, skipping.")
                continue # Skip if no payroll data for this employee in the period
            
            data_added_for_any_employee = True # Mark that we found at least one employee with data

            # --- Employee Header Row ---
            ws.cell(row=current_row, column=1, value=f"Employee: {employee.first_name} {employee.last_name} (Dept: {employee.get_department_display()}, Status: {employee.get_is_active_display()})")
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(payroll_headers)) # Merge across table width
            emp_header_cell = ws.cell(row=current_row, column=1)
            emp_header_cell.font = employee_header_font
            emp_header_cell.fill = employee_fill
            emp_header_cell.alignment = left_alignment
            emp_header_cell.border = thin_border # Apply border to merged cell
            # Apply border to the individual cells covered by the merge for visual consistency
            for col_idx in range(2, len(payroll_headers) + 1):
                ws.cell(row=current_row, column=col_idx).border = thin_border
            current_row += 1

            # --- Payroll Table Header ---
            payroll_table_header_row = current_row
            for col_idx, header_text in enumerate(payroll_headers, 1):
                cell = ws.cell(row=payroll_table_header_row, column=col_idx, value=header_text)
                cell.font = table_header_font; cell.fill = header_fill; cell.alignment = center_alignment; cell.border = thin_border
            current_row += 1

            # --- Payroll Data Rows ---
            total_gross = Decimal('0.00'); total_net = Decimal('0.00')
            total_allowances = Decimal('0.00'); total_deductions_sum = Decimal('0.00')
            for payroll in payrolls:
                current_payroll_deductions = (payroll.tax_amount + payroll.health_insurance + payroll.retirement_amount + payroll.total_deductions)
                row_data = [
                    payroll.pay_period.strftime("%B %Y"),
                    float(employee.salary), # Base salary from Employee model
                    float(payroll.total_allowances),
                    float(payroll.gross_salary),
                    float(current_payroll_deductions),
                    float(payroll.net_salary),
                    payroll.get_payment_status_display()
                ]
                data_row_num = current_row
                for col_idx, value in enumerate(row_data, 1):
                    cell = ws.cell(row=data_row_num, column=col_idx, value=value)
                    cell.border = thin_border
                    if col_idx in [2, 3, 4, 5, 6]: cell.number_format = currency_format; cell.alignment = right_alignment
                    elif col_idx == 7: cell.alignment = center_alignment # Status
                    else: cell.alignment = left_alignment # Pay Period
                current_row += 1
                # Accumulate totals
                total_gross += payroll.gross_salary
                total_net += payroll.net_salary
                total_allowances += payroll.total_allowances
                total_deductions_sum += current_payroll_deductions

            # --- Payroll Summary Row for Employee ---
            summary_row_data = ['Total', '', float(total_allowances), float(total_gross), float(total_deductions_sum), float(total_net), '']
            summary_row_num = current_row
            for col_idx, value in enumerate(summary_row_data, 1):
                cell = ws.cell(row=summary_row_num, column=col_idx, value=value)
                cell.font = total_font; cell.fill = total_fill; cell.border = thin_border
                if col_idx in [3, 4, 5, 6]: cell.number_format = currency_format; cell.alignment = right_alignment
                elif col_idx == 1: cell.alignment = left_alignment
                else: cell.alignment = center_alignment # Blank cells
            current_row += 2 # Spacer row

            # --- Performance Metrics Table ---
            ws.cell(row=current_row, column=1, value="Performance Metrics (Period Total)").font = metric_header_font
            current_row += 1
            metric_header_row = current_row
            for col_idx, header_text in enumerate(metric_headers, 1):
                 cell = ws.cell(row=metric_header_row, column=col_idx, value=header_text)
                 cell.font = table_header_font; cell.fill = header_fill; cell.alignment = left_alignment; cell.border = thin_border
            current_row += 1
            avg_gross = total_gross / max(len(payrolls), 1)
            avg_net = total_net / max(len(payrolls), 1)
            metrics_data = [
                ['Average Monthly Gross (Calculated)', float(avg_gross)],
                ['Average Monthly Net (Calculated)', float(avg_net)],
                ['Total Allowances', float(total_allowances)],
                ['Total Deductions', float(total_deductions_sum)]
            ]
            for row_vals in metrics_data:
                metric_row_num = current_row
                for col_idx, value in enumerate(row_vals, 1):
                    cell = ws.cell(row=metric_row_num, column=col_idx, value=value)
                    cell.border = thin_border
                    if col_idx == 1: cell.alignment = left_alignment
                    elif col_idx == 2: cell.number_format = currency_format; cell.alignment = right_alignment
                current_row += 1
            current_row += 2 # Spacer before next employee

        # --- Handle No Data Case --- 
        if not data_added_for_any_employee:
            logging.warning("No employee payroll data found for the selected criteria.")
            # Add a message to the Excel sheet itself
            ws.cell(row=current_row, column=1, value="No employee payroll data found for the selected criteria.").font = Font(bold=True, color="FF0000")
            # Still save the workbook with the message
        
        # --- Adjust Column Widths --- 
        # Adjust based on payroll_headers length and potential metrics table width
        ws.column_dimensions[get_column_letter(1)].width = 25 # Pay Period / Metric Name
        ws.column_dimensions[get_column_letter(2)].width = 18 # Basic Salary / Metric Value
        ws.column_dimensions[get_column_letter(3)].width = 15 # Allowances
        ws.column_dimensions[get_column_letter(4)].width = 15 # Gross Pay
        ws.column_dimensions[get_column_letter(5)].width = 18 # Total Deductions
        ws.column_dimensions[get_column_letter(6)].width = 15 # Net Pay
        ws.column_dimensions[get_column_letter(7)].width = 10 # Status
        
        # Freeze Panes (Optional - might be less useful if headers repeat per employee)
        # ws.freeze_panes = ws.cell(row=payroll_table_header_row + 1, column=1) 

        # --- Save Workbook to Buffer --- 
        logging.info("Saving Employee Report Workbook to buffer...")
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # --- Create Report Record --- 
        report_name = f"Employee_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all': report_name += f"_{department}"
        report_name += f"_{datetime.now().strftime('%H%M%S')}"
        file_name = f"{report_name}.xlsx"
        report = Report.objects.create(name=report_name, type='employee', period_start=start_date, period_end=end_date, department=department if department != 'all' else None, status='generated')
        report.file.save(file_name, ContentFile(excel_data))
        logging.info(f"Employee report '{file_name}' saved successfully.")

        # --- Return HTTP Response --- 
        response = HttpResponse(excel_data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
    except ImportError:
        logging.error("openpyxl library not found."); messages.error(request, "Excel generation failed: Required library 'openpyxl' not found."); return redirect('reports')
    except Exception as e:
        logging.error(f"Error generating Excel employee report: {str(e)}", exc_info=True); messages.error(request, f'Error generating employee report: {str(e)}'); return redirect('reports')

def generate_tax_report(request, start_date, end_date, department=None):
    logging.info(f"Generating Excel tax report for period {start_date} to {end_date}, department: {department}")
    try:
        # --- Date Validation --- 
        if isinstance(start_date, str):
            try: start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid start date format."); return redirect('reports')
        if isinstance(end_date, str):
            try: end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError: messages.error(request, "Invalid end date format."); return redirect('reports')
        if not start_date or not end_date: messages.error(request, "Start/End date required."); return redirect('reports')
        if start_date > end_date: messages.error(request, "Start date cannot be after end date."); return redirect('reports')

        # --- Query and Process Data --- 
        payroll_query = Payroll.objects.filter(
            pay_period__range=[start_date, end_date]
        ).select_related('employee')
        if department and department != 'all':
            payroll_query = payroll_query.filter(employee__department=department)
        logging.info(f"Found {payroll_query.count()} payroll records matching criteria.")
        if not payroll_query.exists():
            messages.warning(request, "No payroll data found for selected criteria."); return redirect('reports')

        totals = payroll_query.aggregate(
            total_gross=Sum('gross_salary'), total_tax=Sum('tax_amount'),
            total_health=Sum('health_insurance'), total_retirement=Sum('retirement_amount'),
            total_other_deductions=Sum('total_deductions'), total_net=Sum('net_salary')
        )
        total_gross = totals['total_gross'] or Decimal('0.00')
        total_tax = totals['total_tax'] or Decimal('0.00')
        total_other_deductions_combined = ((totals['total_health'] or Decimal('0.00')) + 
                                       (totals['total_retirement'] or Decimal('0.00')) + 
                                       (totals['total_other_deductions'] or Decimal('0.00')))
        total_net = totals['total_net'] or Decimal('0.00')
        if total_gross <= 0:
             messages.warning(request, "No relevant payroll data with positive gross salary found."); return redirect('reports')

        # --- Generate Excel Workbook --- 
        wb = Workbook()
        ws = wb.active
        ws.title = "Tax Report"

        # --- Styles --- 
        header_font = Font(bold=True, name='Calibri', size=12)
        title_font = Font(bold=True, name='Calibri', size=14)
        total_font = Font(bold=True, name='Calibri', size=11)
        currency_format = '"KSh"#,##0.00;[Red]"KSh"-#,##0.00'
        percent_format = '0.0%'
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        right_alignment = Alignment(horizontal='right', vertical='center')
        left_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        header_fill = PatternFill(start_color='FFC0C0C0', end_color='FFC0C0C0', fill_type='solid') # Light grey
        total_fill = PatternFill(start_color='FFE0E0E0', end_color='FFE0E0E0', fill_type='solid') # Lighter grey
        thin_border_side = Side(style='thin')
        thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

        # --- Write Headers and Info (Using explicit rows) ---
        current_row = 1
        ws.cell(row=current_row, column=1, value="Tax Deduction Report")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7) # Merge across 7 columns
        ws.cell(row=current_row, column=1).font = title_font
        ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 1

        ws.cell(row=current_row, column=1, value=f"Period: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
        ws.cell(row=current_row, column=1).alignment = center_alignment
        current_row += 1

        if department and department != 'all':
             ws.cell(row=current_row, column=1, value=f"Department: {dict(Employee.DEPARTMENT_CHOICES).get(department, 'N/A')}")
             ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
             ws.cell(row=current_row, column=1).alignment = center_alignment
             current_row += 1
        current_row += 1 # Add a blank row before the table header
        main_table_header_row = current_row

        # --- Write Main Table Header (Using explicit row) ---
        headers = ['Employee Name', 'Department', 'Gross Income', 'Tax Rate', 'Tax Amount', 'Other Deductions', 'Net Income']
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=main_table_header_row, column=col_idx, value=header_text)
            cell.font = header_font; cell.fill = header_fill; cell.alignment = center_alignment; cell.border = thin_border
        current_row += 1

        # --- Write Employee Data --- 
        employee_ids_in_period = payroll_query.values_list('employee_id', flat=True).distinct()
        employees_in_report = Employee.objects.filter(id__in=employee_ids_in_period).order_by('first_name', 'last_name')
        for employee in employees_in_report:
            employee_payrolls = payroll_query.filter(employee=employee)
            emp_totals = employee_payrolls.aggregate(
                emp_gross=Sum('gross_salary'), emp_tax=Sum('tax_amount'), emp_health=Sum('health_insurance'), 
                emp_retirement=Sum('retirement_amount'), emp_other_ded=Sum('total_deductions'), emp_net=Sum('net_salary'))
            emp_gross = emp_totals['emp_gross'] or Decimal('0.00')
            emp_tax = emp_totals['emp_tax'] or Decimal('0.00')
            emp_other_deductions = ((emp_totals['emp_health'] or Decimal('0.00')) + (emp_totals['emp_retirement'] or Decimal('0.00')) + (emp_totals['emp_other_ded'] or Decimal('0.00')))
            emp_net = emp_totals['emp_net'] or Decimal('0.00')
            
            tax_rates_in_period = employee_payrolls.values_list('tax_rate', flat=True).distinct()
            tax_rate_display = f"{tax_rates_in_period[0]:.1f}%" if len(tax_rates_in_period) == 1 else ("Varies" if len(tax_rates_in_period) > 1 else "N/A")
            if emp_gross > 0:
                row_data = [
                    f"{employee.first_name} {employee.last_name}", 
                    employee.get_department_display(), 
                    float(emp_gross), 
                    tax_rate_display, 
                    float(emp_tax), 
                    float(emp_other_deductions),
                    float(emp_net)
                ]
                # Append using specific row
                for col_idx, value in enumerate(row_data, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=value)
                    cell.border = thin_border
                    if col_idx in [3, 5, 6, 7]: cell.number_format = currency_format; cell.alignment = right_alignment
                    elif col_idx == 4: cell.alignment = center_alignment
                    else: cell.alignment = left_alignment # Name, Department
                current_row += 1
        main_table_end_row = current_row -1

        # --- Write Total Row --- 
        total_row_data = ['Total', '', float(total_gross), '', float(total_tax), float(total_other_deductions_combined), float(total_net)]
        ws.append(total_row_data)
        for col_idx, value in enumerate(total_row_data, 1):
            cell = ws.cell(row=current_row, column=col_idx, value=value)
            cell.border = thin_border
            cell.font = total_font
            cell.fill = total_fill
            if col_idx in [3, 5, 6, 7]: cell.number_format = currency_format; cell.alignment = right_alignment
            elif col_idx == 1: cell.alignment = left_alignment
            else: cell.alignment = center_alignment # Blank cells
        current_row += 2 # Add a blank row spacer

        # --- Write Tax Summary Table --- 
        summary_start_row = current_row
        ws.cell(row=summary_start_row, column=1, value="Overall Tax Summary").font = header_font
        current_row += 1
        summary_headers = ['Description', 'Amount', 'Percentage of Gross']
        ws.append(summary_headers)
        summary_header_row = current_row
        for col_idx, header_text in enumerate(summary_headers, 1):
             cell = ws.cell(row=summary_header_row, column=col_idx, value=header_text)
             cell.font = header_font; cell.fill = header_fill; cell.alignment = center_alignment if col_idx > 1 else left_alignment; cell.border = thin_border
             cell.alignment = center_alignment if col_idx > 1 else left_alignment
        current_row += 1
        summary_data = [
            ['Total Gross Income', float(total_gross), 1.0],
            ['Total Tax Deducted', float(total_tax), float(total_tax/total_gross if total_gross else 0)],
            ['Other Deductions (Health, Retirement, etc.)', float(total_other_deductions_combined), float(total_other_deductions_combined/total_gross if total_gross else 0)],
            ['Total Net Income', float(total_net), float(total_net/total_gross if total_gross else 0)]]
        for row_vals in summary_data:
            data_row_num = current_row
            for col_idx, value in enumerate(row_vals, 1):
                cell = ws.cell(row=data_row_num, column=col_idx, value=value)
                cell.border = thin_border
                if col_idx == 1: cell.alignment = left_alignment
                elif col_idx == 2: cell.number_format = currency_format; cell.alignment = right_alignment
                elif col_idx == 3: cell.number_format = percent_format; cell.alignment = right_alignment
            current_row += 1

        # --- Adjust Column Widths (Apply at the end) --- 
        # Columns A-G used by main table, A-C by summary
        ws.column_dimensions[get_column_letter(1)].width = 40 # Col A: Employee Name / Summary Desc (Max needed)
        ws.column_dimensions[get_column_letter(2)].width = 18 # Amount
        ws.column_dimensions[get_column_letter(3)].width = 18 # Percentage
        ws.column_dimensions[get_column_letter(4)].width = 10 # Tax Rate
        ws.column_dimensions[get_column_letter(5)].width = 15 # Tax Amount
        ws.column_dimensions[get_column_letter(6)].width = 18 # Other Deductions
        ws.column_dimensions[get_column_letter(7)].width = 15 # Net Income
        
        # Freeze Panes (Optional - might be less useful if headers repeat per employee)
        # ws.freeze_panes = ws.cell(row=payroll_table_header_row + 1, column=1) 

        # --- Save Workbook to Buffer --- 
        logging.info("Saving Tax Report Workbook to buffer...")
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # --- Create Report Record --- 
        report_name = f"Tax_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all': report_name += f"_{department}"
        report_name += f"_{datetime.now().strftime('%H%M%S')}"
        file_name = f"{report_name}.xlsx"
        report = Report.objects.create(name=report_name, type='tax', period_start=start_date, period_end=end_date, department=department if department != 'all' else None, status='generated')
        report.file.save(file_name, ContentFile(excel_data))
        logging.info(f"Tax report '{file_name}' saved successfully.")

        # --- Return HTTP Response --- 
        response = HttpResponse(excel_data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
    except ImportError:
        logging.error("openpyxl library not found."); messages.error(request, "Excel generation failed: Required library 'openpyxl' not found."); return redirect('reports')
    except Exception as e:
        logging.error(f"Error generating Excel tax report: {str(e)}", exc_info=True); messages.error(request, f'Error generating tax report: {str(e)}'); return redirect('reports')

@require_POST
@csrf_protect
def delete_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    try:
        report_name = report.name
        if report.file:
            report.file.delete(save=False)
        report.delete()
        messages.success(request, f'Report "{report_name}" deleted successfully.')
        logging.info(f"Deleted report {report_id} - '{report_name}'.")
    except Exception as e:
        logging.error(f"Error deleting report {report_id} - '{report.name}': {str(e)}", exc_info=True)
        messages.error(request, f'Error deleting report: {str(e)}')
    return redirect('reports')

def download_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if not report.file:
        raise Http404("Report file not found.")
    try:
        file_name = report.file.name
        logging.info(f"Attempting to serve report: {file_name}")
        if file_name.lower().endswith('.xlsx'):
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif file_name.lower().endswith('.pdf'):
            content_type = 'application/pdf' # Keep for old reports
        else:
            content_type = 'application/octet-stream' # Fallback
            logging.warning(f"Unknown file type for report {report_id}, using generic content type.")
        response = HttpResponse(report.file.read(), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        logging.info(f"Serving download for report {report_id} ('{report.name}') as {content_type}.")
        return response
    except Exception as e:
        logging.error(f"Error serving report {report_id} ('{report.name}'): {str(e)}", exc_info=True)
        messages.error(request, "Error accessing report file.")
        return redirect('reports')