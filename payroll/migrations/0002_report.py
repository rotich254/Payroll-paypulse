# Generated by Django 5.2 on 2025-04-20 07:18

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('type', models.CharField(choices=[('payroll', 'Payroll Summary'), ('department', 'Department Summary'), ('employee', 'Employee Summary'), ('tax', 'Tax Summary')], max_length=20)),
                ('generated_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('period', models.CharField(max_length=50)),
                ('file', models.FileField(blank=True, null=True, upload_to='reports/')),
            ],
        ),
    ]
