# PayPulse Payroll System

A comprehensive payroll management system built with Django.

## Deployment to Render (Free Tier)

### Prerequisites

1. Create a Render account at [render.com](https://render.com)
2. Have your database URL ready (PostgreSQL recommended)

### Deployment Steps

1. Log in to your Render account
2. Click "New" and select "Web Service"
3. Connect your GitHub repository or upload your code directly
4. Configure the following settings:

   - **Name**: paypulse (or your preferred name)
   - **Environment**: Python
   - **Region**: Choose the closest to your users
   - **Branch**: main (or your default branch)
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn pappulse.wsgi:application`
   - **Plan**: Free

5. Add the following environment variables:

   - `SECRET_KEY`: Your Django secret key
   - `DEBUG`: "False"
   - `DATABASE_URL`: Your PostgreSQL database URL
   - `ALLOWED_HOSTS`: ".onrender.com" (or your custom domain)

6. Click "Create Web Service"

### Local Development

1. Create a `.environment` file in the project root with the following variables:

```
SECRET_KEY=your_secret_key
DEBUG=True
DATABASE_URL=your_database_url
```

2. Install dependencies:

```
pip install -r requirements.txt
```

3. Run migrations:

```
python manage.py migrate
```

4. Start the development server:

```
python manage.py runserver
```

## Features

- Employee management
- Payroll processing
- PDF generation
- Excel reports
- Dashboard with analytics
