# PostgreSQL Database Setup and Production Deployment Guide

This guide will help you migrate from SQLite to PostgreSQL database and set up the application for production use.

## Prerequisites

1. **PostgreSQL**: Install PostgreSQL locally for development
   ```bash
   # Windows (using Chocolatey)
   choco install postgresql
   
   # macOS (using Homebrew)
   brew install postgresql
   
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   ```

2. **Database Service**: Choose a cloud PostgreSQL provider for production:
   - **Render.com** (recommended for simple deployments)
   - **Railway** (developer-friendly)
   - **Supabase** (PostgreSQL with additional features)
   - **AWS RDS**, **Google Cloud SQL**, **Azure Database**

## Step 1: Set Up PostgreSQL Database

### 1.1 Local Development Setup
```bash
# Start PostgreSQL service
# Windows
net start postgresql-x64-14

# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql
```

### 1.2 Create Local Database
```bash
# Connect to PostgreSQL as superuser
psql -U postgres

# Create database and user
CREATE DATABASE ems_db;
CREATE USER ems_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ems_db TO ems_user;
\q
```

### 1.3 Production Database Options

#### Option A: Render.com PostgreSQL
1. Go to [render.com](https://render.com)
2. Create a new PostgreSQL database
3. Copy the connection string

#### Option B: Railway PostgreSQL
1. Go to [railway.app](https://railway.app)
2. Create a new project
3. Add PostgreSQL service
4. Copy the connection string

#### Option C: Supabase
1. Go to [supabase.com](https://supabase.com)
2. Create a new project
3. Go to Settings > Database
4. Copy the connection string

## Step 2: Configure Environment Variables

### 2.1 Update .env File
Update your `.env` file with the PostgreSQL database credentials:

```env
# Django Settings
SECRET_KEY=your-super-secret-key-here-change-this
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,localhost,127.0.0.1

# PostgreSQL Database Configuration
# For local development:
# DATABASE_URL=postgresql://ems_user:your_password@localhost:5432/ems_db
# For production (replace with your actual database URL):
DATABASE_URL=postgresql://username:password@hostname:5432/database_name

# Superuser Configuration
DJANGO_SUPERUSER_EMAIL_1=admin@yourdomain.com
DJANGO_SUPERUSER_PASSWORD_1=your-secure-admin-password
DJANGO_SUPERUSER_FIRSTNAME_1=Admin
DJANGO_SUPERUSER_LASTNAME_1=User

# Security Settings (for production)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Email Configuration (optional)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### 2.2 Environment-Specific Configuration

For different environments, create separate `.env` files:

- `.env.production` - Production settings
- `.env.staging` - Staging settings  
- `.env.development` - Development settings

## Step 3: Install Dependencies

```bash
# Install the updated requirements
pip install -r requirements.txt
```

## Step 4: Database Migration

### 4.1 Export Data from SQLite (if you have existing data)
```bash
# Export existing data
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission > data_backup.json
```

### 4.2 Run Migrations on PostgreSQL
```bash
# Create and apply migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser(s)
python manage.py create_superuser
```

### 4.3 Import Data (if you have existing data)
```bash
# Load the backed up data
python manage.py loaddata data_backup.json
```

## Step 5: Production Deployment Options

### Option 1: Deploy to Render.com

1. **Create render.yaml** (if not exists):
```yaml
services:
  - type: web
    name: ems-ibr
    env: python
    buildCommand: "./build.sh"
    startCommand: "gunicorn core.wsgi:application"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DATABASE_URL
        fromDatabase:
          name: ems-production
          property: connectionString
```

2. **Connect your repository** to Render and deploy

### Option 2: Deploy to Railway

1. **Connect your repository** to Railway
2. **Set environment variables** in Railway dashboard
3. **Deploy** using the existing build.sh script

### Option 3: Deploy to Vercel

1. **Create vercel.json**:
```json
{
  "builds": [
    {
      "src": "core/wsgi.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "core/wsgi.py"
    }
  ]
}
```

2. **Deploy** using Vercel CLI or GitHub integration

### Option 4: Deploy to DigitalOcean App Platform

1. **Create .do/app.yaml**:
```yaml
name: ems-ibr
services:
- name: web
  source_dir: /
  github:
    repo: your-username/ems-ibr
    branch: main
  run_command: gunicorn --worker-tmp-dir /dev/shm core.wsgi:application
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: DATABASE_URL
    value: your-turso-database-url
  - key: DATABASE_AUTH_TOKEN
    value: your-turso-auth-token
    type: SECRET
```

## Step 6: Production Checklist

### Security
- [ ] Set `DEBUG=False`
- [ ] Use a strong, unique `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Enable SSL/HTTPS
- [ ] Set secure cookie flags
- [ ] Configure CORS if needed

### Database
- [ ] Turso database created and configured
- [ ] Database migrations applied
- [ ] Superuser accounts created
- [ ] Data backed up (if migrating)

### Static Files
- [ ] `STATIC_ROOT` configured
- [ ] Static files collected
- [ ] WhiteNoise configured for static file serving

### Monitoring
- [ ] Logging configured
- [ ] Error tracking set up (Sentry recommended)
- [ ] Performance monitoring

### Email
- [ ] Email backend configured
- [ ] SMTP settings tested
- [ ] Email templates reviewed

## Step 7: Testing the Setup

### 7.1 Local Testing with PostgreSQL
```bash
# Set environment variables for testing
export DATABASE_URL="postgresql://ems_user:your_password@localhost:5432/ems_db"
export DEBUG="True"

# Run the application
python manage.py runserver
```

### 7.2 Production Testing
```bash
# Test with production settings
export DEBUG="False"
python manage.py check --deploy

# Test static files
python manage.py collectstatic --noinput

# Test database connection
python manage.py dbshell
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify DATABASE_URL format: `postgresql://username:password@hostname:5432/database_name`
   - Check network connectivity
   - Ensure PostgreSQL service is running
   - Verify database credentials and permissions

2. **Migration Issues**
   - Run `python manage.py showmigrations` to check status
   - Use `python manage.py migrate --fake-initial` if needed

3. **Static Files Not Loading**
   - Verify `STATIC_ROOT` and `STATIC_URL` settings
   - Run `python manage.py collectstatic`
   - Check WhiteNoise configuration

4. **SSL/HTTPS Issues**
   - Verify SSL certificate installation
   - Check `SECURE_SSL_REDIRECT` setting
   - Ensure proxy headers are configured

### Useful Commands

```bash
# Connect to PostgreSQL database
psql $DATABASE_URL

# Check database connection from Django
python manage.py dbshell

# View database tables
psql $DATABASE_URL -c "\dt"

# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size(current_database()));"

# Monitor active connections
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"
```

## Backup and Recovery

### Regular Backups
```bash
# Export data regularly using Django
python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json

# Or use PostgreSQL's pg_dump
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
pg_dump $DATABASE_URL | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Recovery
```bash
# Restore from Django backup
python manage.py loaddata backup_file.json

# Restore from PostgreSQL dump
psql $DATABASE_URL < backup_file.sql

# Restore from compressed backup
gunzip -c backup_file.sql.gz | psql $DATABASE_URL
```

## Performance Optimization

1. **Database Optimization**
   - Use database indexes appropriately
   - Optimize queries with `select_related()` and `prefetch_related()`
   - Consider database replicas for read scaling

2. **Caching**
   - Implement Redis caching for frequently accessed data
   - Use Django's cache framework

3. **Static Files**
   - Use CDN for static file delivery
   - Enable compression with WhiteNoise

## Support

For issues related to:
- **PostgreSQL Database**: [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- **Django with PostgreSQL**: [Django PostgreSQL Notes](https://docs.djangoproject.com/en/5.0/ref/databases/#postgresql-notes)
- **Django Deployment**: [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- **Application Issues**: Check the application logs and Django documentation