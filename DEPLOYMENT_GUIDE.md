# AWS Deployment Guide for DialEasy (Django + PostgreSQL RDS)

This guide provides step-by-step instructions to deploy the DialEasy backend on an AWS Ubuntu EC2 instance using RDS for the PostgreSQL database.

## 1. Setup AWS RDS (PostgreSQL)
1. Log in to **AWS Console** > **RDS** > **Create database**.
2. **Choose a database creation method**: Standard Create.
3. **Engine options**: PostgreSQL.
4. **Templates**: Free Tier (Crucial for avoiding charges).
5. **Settings**:
   - DB instance identifier: `dialeasy-db`
   - Master username: `dialeasy_admin`
   - Master password: `your_secure_password`
6. **Instance configuration**: `db.t3.micro` (Free Tier).
7. **Connectivity**:
   - Public access: **No** (Better security).
   - VPC security group: Create new (e.g., `rds-sg`).
8. **Create Database**. 

**Note**: After creation, go to the RDS Security Group and allow **Inbound Rule** for port `5432` from your EC2 instance's Private IP or Security Group.

---

## 2. Prepare EC2 Instance (Ubuntu)
SSH into your Ubuntu instance:
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### Install Dependencies:
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx git libpq-dev postgresql-client -y
```

---

## 3. Clone and Setup Project
```bash
git clone https://github.com/Shiwa45/DialEasy.git
cd DialEasy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn  # Production server
```

---

## 4. Environment Configuration
Create a `.env` file in the project root:
```bash
nano .env
```
Add the following details (replacing with your RDS endpoint):
```env
DEBUG=False
SECRET_KEY=your_secret_key
DATABASE_URL=postgres://dialeasy_admin:your_secure_password@your-rds-endpoint:5432/postgres
ALLOWED_HOSTS=your-ec2-ip,your-domain.com
```

---

## 5. Database Schema (Multi-Tenancy)
DialEasy uses a multi-tenant architecture. Standard migrations won't work. You must run these commands:

### Step A: Run Schema Migrations
This creates the tables for both the public schema and all tenant schemas.
```bash
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant
```

### Step B: Create Public Tenant (Crucial)
This sets up the "public" schema which manages all other tenants. Replace `your-domain.com` with your EC2 IP or domain.
```bash
python manage.py create_public_tenant --domain=your-domain.com
```

### Step C: Create Admin User
```bash
python manage.py createsuperuser
```

### Step D: Collect Static Files
```bash
python manage.py collectstatic --noinput
```

---

## 6. Gunicorn Setup (Systemd)
**IMPORTANT**: Do NOT place the `.sock` file in `/home/ubuntu/`. Nginx will get a "Permission Denied" error because it cannot access the ubuntu user's home folder. Use `/run/gunicorn.sock`.

Create a gunicorn service file:
```bash
sudo nano /etc/systemd/system/gunicorn.service
```
Paste this configuration:
```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/DialEasy
# The socket must be in a location accessible by www-data
ExecStart=/home/ubuntu/DialEasy/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          telecrm_project.wsgi:application

[Install]
WantedBy=multi-user.target
```
Start and enable gunicorn:
```bash
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

---

## 7. Nginx Configuration (Fixing Permission Denied)
Ensure Nginx is looking at the correct socket in `/run/`.

```bash
sudo nano /etc/nginx/sites-available/dialeasy
```
Paste this configuration:
```nginx
server {
    listen 80;
    server_name your-ec2-ip;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /home/ubuntu/DialEasy/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/DialEasy/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

### Final Permission Fix
Ensure the Nginx user (`www-data`) has execute permissions on the project path:
```bash
sudo chmod o+x /home/ubuntu
sudo chmod o+x /home/ubuntu/DialEasy
```

Enable the config and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/dialeasy /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

---

## 8. AWS Security Group Update
In the **EC2 Security Group**, ensure you have an Inbound Rule for **HTTP (Port 80)** from `0.0.0.0/0`.

Your project is now live at `http://your-ec2-ip/`!
