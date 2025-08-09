from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sum_field(queryset, field_name):
    """
    Template filter to sum a specific field across a queryset
    Example: {{ payrolls|sum_field:'gross_salary' }}
    """
    try:
        return sum(getattr(obj, field_name) or Decimal('0.00') for obj in queryset)
    except (AttributeError, TypeError):
        return Decimal('0.00')

@register.filter
def div(value, arg):
    """
    Divides the value by the argument
    Example: {{ total_tax|div:total_gross }}
    """
    try:
        return Decimal(str(value)) / Decimal(str(arg))
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0.00')

@register.filter
def multiply(value, arg):
    """
    Multiplies the value by the argument
    Example: {{ ratio|multiply:100 }}
    """
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError):
        return Decimal('0.00')
