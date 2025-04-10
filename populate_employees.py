# This script is designed to be run from the command line. You can use the following commands:
# python populate_employees.py --count 100  # To create 100 employees
# python populate_employees.py --clear --count 100  # To clear existing employees and create 100 new ones

import os
import sys
import django
import random
from datetime import date, timedelta
from faker import Faker
from decimal import Decimal

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pappulse.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error setting up Django environment: {str(e)}")
    sys.exit(1)

from payroll.models import Employee

def generate_salary_by_department(department):
    """Generate appropriate salary range based on department"""
    salary_ranges = {
        'engineering': (60000, 150000),
        'marketing': (45000, 120000),
        'sales': (40000, 100000),
        'human_resource': (45000, 110000),
        'finance': (50000, 130000),
        'design': (45000, 115000)
    }
    min_salary, max_salary = salary_ranges.get(department, (30000, 100000))
    return Decimal(random.uniform(min_salary, max_salary)).quantize(Decimal('0.01'))

def populate_employees(num_employees=50):
    fake = Faker()
    
    # Get choices from Employee model
    departments = [dept[0] for dept in Employee.DEPARTMENT_CHOICES]
    statuses = [status[0] for status in Employee.ACTIVE_STATUS]
    
    employees = []
    
    for _ in range(num_employees):
        try:
            # Generate fake data
            first_name = fake.first_name()
            last_name = fake.last_name()
            email = f"{first_name.lower()}.{last_name.lower()}@{fake.domain_name()}"
            phone_number = fake.numerify(text="###-###-####")
            
            # Generate hire date (within last 7 years)
            max_date = date.today()
            min_date = max_date - timedelta(days=7*365)
            hire_date = fake.date_between(start_date=min_date, end_date=max_date)
            
            # Select department and generate appropriate salary
            department = random.choice(departments)
            salary = generate_salary_by_department(department)
            
            # Weighted choice for status (more likely to be active)
            is_active = random.choices(
                statuses,
                weights=[0.7, 0.2, 0.1],  # 70% active, 20% on leave, 10% probation
                k=1
            )[0]
            
            # Create employee object
            employee = Employee(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                hire_date=hire_date,
                department=department,
                salary=salary,
                is_active=is_active
            )
            employees.append(employee)
            
        except Exception as e:
            print(f"Error generating employee data: {str(e)}")
            continue
    
    # Bulk create employees
    if employees:
        try:
            Employee.objects.bulk_create(employees)
            print(f"Successfully added {len(employees)} employees!")
        except Exception as e:
            print(f"Error creating employees: {str(e)}")
    else:
        print("No employees were generated!")

def clear_employees():
    """Clear all employees from the database"""
    try:
        count = Employee.objects.all().count()
        Employee.objects.all().delete()
        print(f"Cleared {count} employees from the database.")
    except Exception as e:
        print(f"Error clearing employees: {str(e)}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate the database with fake employee data.')
    parser.add_argument('--count', type=int, default=50, help='Number of employees to create')
    parser.add_argument('--clear', action='store_true', help='Clear existing employees before adding new ones')
    
    args = parser.parse_args()
    
    if args.clear:
        clear_employees()
    
    print(f"Starting to populate database with {args.count} employees...")
    populate_employees(args.count)
    print("Population complete!")

