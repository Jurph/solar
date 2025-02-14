@echo off
:start
echo Starting Django development environment...

REM Check if virtual environment exists, create if it doesn't
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Install Django if not already installed
python -c "import django" 2>NUL
if errorlevel 1 (
    echo Installing Django...
    pip install django
)

REM Set the Python path to include the project root
set PYTHONPATH=%CD%

REM Navigate to project directory
cd mysite

REM Run migrations
echo Running database migrations...
python manage.py makemigrations universe
python manage.py migrate

REM Check if superuser exists, prompt to create if it doesn't
python -c "from django.contrib.auth.models import User; exit(0 if User.objects.filter(is_superuser=True).exists() else 1)"
if errorlevel 1 (
    echo No superuser found. Creating superuser...
    python manage.py createsuperuser
)

REM Start development server with restart option
echo Starting development server...
echo Admin interface will be available at: http://127.0.0.1:8000/admin/
echo Universe view will be available at: http://127.0.0.1:8000/universe/
echo.
echo Press Ctrl+C to stop the server
echo After stopping, press 'R' to migrate and restart, or any other key to exit
python manage.py runserver

REM Check for restart
choice /c RC /n /m "Press R to migrate and restart, or C to close"
if errorlevel 2 goto end
if errorlevel 1 goto start

:end
echo Closing server...