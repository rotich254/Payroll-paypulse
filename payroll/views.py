from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Employee
from .forms import EmployeeForm
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


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