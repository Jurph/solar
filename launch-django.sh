#!/bin/bash

launch_server() {
    echo "Attempting to start ollama server..."
    (ollama serve &) 
    sleep 2
    if ! pgrep -f "ollama serve" > /dev/null; then
        echo "ollama didn't start - LLM features may not work properly"
    else
        echo "Ollama server is running."
    fi

    echo "Starting Django development environment..."

    # Check if virtual environment exists, create if it doesn't
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        echo "Virtual environment created."
    fi

    # Activate virtual environment
    echo "Activating virtual environment..."
    source venv/bin/activate

    echo "Checking PyTorch CUDA availability..."
    python - <<'EOF'
import torch
has_torch = True
try:
    import torch  # noqa: F401
except Exception:
    has_torch = False

if not has_torch:
    print("torch not installed (skipping CUDA check)")
else:
    print(f"torch version: {torch.__version__}")
    print(f"cuda available: {torch.cuda.is_available()}")
    print(f"cuda device count: {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"device 0: {torch.cuda.get_device_name(0)}")
    else:
        print("no cuda devices detected")
EOF

    # Install Django if not already installed
    python -c "import django" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Installing Django..."
        pip install django
    fi

    # Navigate to project directory
    cd mysite

    # Run migrations
    echo "Running database migrations..."
    python manage.py makemigrations universe
    python manage.py migrate

    # Check if superuser exists, prompt to create if it doesn't
    echo "Checking for superuser..."
    python - <<EOF
from django.contrib.auth.models import User
exit(0 if User.objects.filter(is_superuser=True).exists() else 1)
EOF

    if [ $? -ne 0 ]; then
        echo "No superuser found. Creating superuser..."
        python manage.py createsuperuser
    fi

    # Start development server
    echo "Starting development server..."
    echo "Admin interface will be available at: http://127.0.0.1:8000/admin/"
    echo "Universe view will be available at: http://127.0.0.1:8000/universe/"
    echo
    echo "Press Ctrl+C to stop the server"
    echo "After stopping, press 'R' to migrate and restart, or any other key to exit"
    python manage.py runserver
}

while true; do
    launch_server
    read -n 1 -p "Press R to migrate and restart, or any other key to exit: " input
    echo
    if [[ ! $input =~ ^[Rr]$ ]]; then
        echo "Closing server..."
        break
    fi
done