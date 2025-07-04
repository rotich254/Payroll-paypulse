# Generated by Django 5.2 on 2025-04-20 07:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0003_delete_report'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('type', models.CharField(choices=[('payroll', 'Payroll Summary'), ('department', 'Department Summary'), ('employee', 'Employee Summary'), ('tax', 'Tax Summary')], max_length=20)),
                ('generated_date', models.DateTimeField(auto_now_add=True)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('department', models.CharField(blank=True, choices=[('engineering', 'Engineering'), ('marketing', 'Marketing'), ('sales', 'Sales'), ('human_resource', 'Human Resource'), ('finance', 'Finance'), ('design', 'Design')], max_length=20, null=True)),
                ('file', models.FileField(upload_to='reports/')),
                ('status', models.CharField(choices=[('generated', 'Generated'), ('failed', 'Failed'), ('processing', 'Processing')], default='processing', max_length=20)),
            ],
        ),
    ]
