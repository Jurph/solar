@echo off
REM NOTE: This script intentionally overlaps with launch-django.sh.
REM The duplication is deliberate because Windows batch and POSIX shell
REM have different process, activation, and startup semantics.
REM Keep behavior aligned across both files, but do not try to force
REM them into a single cross-platform script.
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

echo Checking PyTorch CUDA availability...
python -c "import sys, importlib.util; spec = importlib.util.find_spec('torch'); if not spec: print('torch not installed (skipping CUDA check)'); sys.exit(0); import torch; print(f'torch version: {torch.__version__}'); print(f'cuda available: {torch.cuda.is_available()}'); print(f'cuda device count: {torch.cuda.device_count()}'); print(f'device 0: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda devices detected'}')" 2>NUL

REM Install Django if not already installed
python -c "import django" 2>NUL
if errorlevel 1 (
    echo Installing Django...
    pip install django
)

REM Set PYTHONPATH to include the project root
set "PYTHONPATH=%CD%"

REM Attempt to start ollama server
echo Attempting to start ollama server...
start /B cmd /C "ollama serve"
timeout /t 2 > NUL
REM Check if ollama is running by looking for ollama.exe in the task list
tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul
if errorlevel 1 (
    echo ollama didn't start - LLM features may not work properly
) else (
    echo Ollama server is running.
)

REM Run migrations
echo Running database migrations...
python mysite/manage.py makemigrations universe
python mysite/manage.py migrate

REM Check if superuser exists, prompt to create if it doesn't
python mysite/manage.py check_superuser
if errorlevel 1 (
    echo No superuser found. Creating superuser...
    python mysite/manage.py createsuperuser
)

REM Start development server with restart option
echo Starting development server...
echo Admin interface will be available at: http://127.0.0.1:8000/admin/
echo Universe view will be available at: http://127.0.0.1:8000/universe/
echo.
echo Press Ctrl+C to stop the server
echo After stopping, press 'R' to migrate and restart, or any other key to exit
python mysite/manage.py runserver

REM Check for restart
choice /c RC /n /m "Press R to migrate and restart, or C to close"
if errorlevel 2 goto end
if errorlevel 1 goto start

:end
echo Closing server...