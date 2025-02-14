#!/bin/bash

launch_server() {
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