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
from decimal import Decimal
from django.utils import timezone
from datetime import datetime
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.urls import reverse
import tempfile

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
    
    context = {
        'total_employees': total_employees,
        'active_employees': active_employees,
        'on_leave_employees': on_leave_employees,
        'probation_employees': probation_employees,
    }
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
    active_employees = Employee.objects.filter(is_active='active').order_by('first_name', 'last_name')
    
    # Calculate summary statistics with comma formatting
    total_payroll = Payroll.objects.aggregate(total=models.Sum('gross_salary'))['total'] or 0
    total_employees = Employee.objects.filter(is_active='active').count()
    paid_count = Payroll.objects.filter(payment_status='paid').count()
    pending_count = Payroll.objects.filter(payment_status='pending').count()
    
    if show_all:
        payroll_history = Payroll.objects.select_related('employee').order_by('-pay_period', 'employee__first_name')
    else:
        payroll_history = Payroll.objects.select_related('employee').order_by('-pay_period', 'employee__first_name')[:10]
    
    context = {
        'active_employees': active_employees,
        'payroll_history': payroll_history,
        'show_all': show_all,
        'total_payrolls': Payroll.objects.count(),
        'total_payroll': "{:,.2f}".format(total_payroll),  # Format with commas
        'total_employees': total_employees,
        'paid_count': paid_count,
        'pending_count': pending_count,
    }
    return render(request, 'payroll/payroll.html', context)

def generate_payroll(request):
    if request.method == 'POST':
        try:
            employee_id = request.POST.get('employee')
            pay_date = request.POST.get('pay_date')
            allowances = Decimal(request.POST.get('total_allowances', '0'))
            deductions = Decimal(request.POST.get('total_deductions', '0'))
            
            if not employee_id or not pay_date:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Employee and pay date are required'
                }, status=400)

            employee = get_object_or_404(Employee, id=employee_id)
            
            # Create payroll record
            payroll = Payroll.objects.create(
                employee=employee,
                pay_period=pay_date,
                gross_salary=employee.salary,
                total_allowances=allowances,
                total_deductions=deductions,
                net_salary=employee.salary + allowances - deductions,
                payment_status='pending'
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payroll created successfully',
                'data': {
                    'detail_url': reverse('payroll_detail', args=[payroll.id])
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    # GET request
    context = {
        'active_employees': Employee.objects.filter(is_active='active').order_by('first_name', 'last_name'),
    }
    return render(request, 'payroll/payroll.html', context)

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
        
        # Create response object with PDF mime type
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
        elements.append(Paragraph(f"Period: {payroll.pay_period.strftime('%B %Y')}", normal_style))
        elements.append(Spacer(1, 20))
        
        # Employee information
        employee_data = [
            ['Name:', f"{payroll.employee.first_name} {payroll.employee.last_name}", 'Department:', 
             dict(Employee.DEPARTMENT_CHOICES).get(payroll.employee.department, '')],
            ['Employee ID:', str(payroll.employee.id), 'Pay Period:', 
             payroll.pay_period.strftime("%B %d, %Y")]
        ]
        
        employee_table = Table(employee_data, colWidths=[100, 150, 100, 150])
        employee_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(employee_table)
        elements.append(Spacer(1, 20))
        
        # Salary details
        salary_data = [
            ['Description', 'Amount'],
            ['Gross Salary', f"KSh {payroll.gross_salary:,.2f}"],
            ['Allowances', f"KSh {payroll.total_allowances:,.2f}"],
            ['Deductions', f"KSh {payroll.total_deductions:,.2f}"],
            ['Net Salary', f"KSh {payroll.net_salary:,.2f}"]
        ]
        
        salary_table = Table(salary_data, colWidths=[300, 200])
        salary_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
        ]))
        elements.append(salary_table)
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%B %d, %Y')}", normal_style))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF from buffer
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