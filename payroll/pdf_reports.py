from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from datetime import datetime
from .models import Payroll, Employee

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

@login_required
def generate_payroll_pdf_report(request, start_date, end_date, department=None):
    # Convert string dates to datetime objects
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Query payroll records
    payrolls = Payroll.objects.filter(
        pay_period__range=[start_date, end_date]
    ).select_related('employee')

    if department and department != 'all':
        payrolls = payrolls.filter(employee__department=department)

    if not payrolls.exists():
        messages.warning(request, "No payroll records found for the selected criteria.")
        return redirect('reports')

    # Prepare context for PDF
    context = {
        'payrolls': payrolls,
        'start_date': start_date,
        'end_date': end_date,
        'department': dict(Employee.DEPARTMENT_CHOICES).get(department) if department != 'all' else 'All Departments',
        'generated_date': datetime.now()
    }
    
    # Generate PDF
    pdf = render_to_pdf('payroll/pdf_templates/payroll_report.html', context)
    if pdf:
        filename = f"Payroll_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all':
            filename += f"_{department}"
        filename += ".pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error Rendering PDF", status=400)

@login_required
def generate_department_pdf_report(request, start_date, end_date, department=None):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    departments = {}
    department_list = [department] if department and department != 'all' else [d[0] for d in Employee.DEPARTMENT_CHOICES]
    
    for dept in department_list:
        employees = Employee.objects.filter(department=dept)
        if employees.exists():
            dept_payrolls = Payroll.objects.filter(
                employee__in=employees,
                pay_period__range=[start_date, end_date]
            ).select_related('employee')
            
            if dept_payrolls.exists():
                departments[dict(Employee.DEPARTMENT_CHOICES)[dept]] = {
                    'payrolls': dept_payrolls,
                    'total_gross': sum(p.gross_salary for p in dept_payrolls),
                    'total_net': sum(p.net_salary for p in dept_payrolls),
                    'employee_count': employees.count()
                }

    if not departments:
        messages.warning(request, "No department data found for the selected criteria.")
        return redirect('reports')

    context = {
        'departments': departments,
        'start_date': start_date,
        'end_date': end_date,
        'generated_date': datetime.now()
    }
    
    pdf = render_to_pdf('payroll/pdf_templates/department_report.html', context)
    if pdf:
        filename = f"Department_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all':
            filename += f"_{department}"
        filename += ".pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error Rendering PDF", status=400)

@login_required
def generate_employee_pdf_report(request, start_date, end_date, department=None):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    employees = Employee.objects.all()
    if department and department != 'all':
        employees = employees.filter(department=department)
    
    employee_data = []
    for employee in employees:
        payrolls = Payroll.objects.filter(
            employee=employee,
            pay_period__range=[start_date, end_date]
        )
        if payrolls.exists():
            total_gross = sum(p.gross_salary for p in payrolls)
            total_net = sum(p.net_salary for p in payrolls)
            employee_data.append({
                'employee': employee,
                'payrolls': payrolls,
                'total_gross': total_gross,
                'total_net': total_net,
                'avg_gross': total_gross / payrolls.count(),
                'avg_net': total_net / payrolls.count()
            })

    if not employee_data:
        messages.warning(request, "No employee data found for the selected criteria.")
        return redirect('reports')

    context = {
        'employee_data': employee_data,
        'start_date': start_date,
        'end_date': end_date,
        'department': dict(Employee.DEPARTMENT_CHOICES).get(department) if department != 'all' else 'All Departments',
        'generated_date': datetime.now()
    }
    
    pdf = render_to_pdf('payroll/pdf_templates/employee_report.html', context)
    if pdf:
        filename = f"Employee_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all':
            filename += f"_{department}"
        filename += ".pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error Rendering PDF", status=400)

@login_required
def generate_tax_pdf_report(request, start_date, end_date, department=None):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    payrolls = Payroll.objects.filter(
        pay_period__range=[start_date, end_date]
    ).select_related('employee')

    if department and department != 'all':
        payrolls = payrolls.filter(employee__department=department)

    if not payrolls.exists():
        messages.warning(request, "No tax data found for the selected criteria.")
        return redirect('reports')

    # Calculate totals
    total_gross = sum(p.gross_salary for p in payrolls)
    total_tax = sum(p.tax_amount for p in payrolls)
    total_net = sum(p.net_salary for p in payrolls)

    employee_tax_data = {}
    for payroll in payrolls:
        emp_id = payroll.employee.id
        if emp_id not in employee_tax_data:
            employee_tax_data[emp_id] = {
                'employee': payroll.employee,
                'gross': 0,
                'tax': 0,
                'net': 0,
                'tax_rate': payroll.tax_rate
            }
        employee_tax_data[emp_id]['gross'] += payroll.gross_salary
        employee_tax_data[emp_id]['tax'] += payroll.tax_amount
        employee_tax_data[emp_id]['net'] += payroll.net_salary

    context = {
        'employee_tax_data': employee_tax_data.values(),
        'total_gross': total_gross,
        'total_tax': total_tax,
        'total_net': total_net,
        'start_date': start_date,
        'end_date': end_date,
        'department': dict(Employee.DEPARTMENT_CHOICES).get(department) if department != 'all' else 'All Departments',
        'generated_date': datetime.now()
    }
    
    pdf = render_to_pdf('payroll/pdf_templates/tax_report.html', context)
    if pdf:
        filename = f"Tax_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        if department and department != 'all':
            filename += f"_{department}"
        filename += ".pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error Rendering PDF", status=400)
