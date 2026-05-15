@echo off

REM Go to your Django project folder
cd /d "C:\Users\Easyian\OneDrive\Desktop\easyian-crm"

REM Activate virtual environment
call venv\Scripts\activate

REM Run Django server
python manage.py runserver 0.0.0.0:8000

pause