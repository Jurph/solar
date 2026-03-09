#!/bin/bash

# NOTE: This script intentionally overlaps with launch-django.bat.
# The duplication is deliberate because POSIX shell and Windows batch
# have different process, activation, and startup semantics.
# Keep behavior aligned across both files, but do not try to force
# them into a single cross-platform script.

# Resolve project root and venv Python path once, up front.
# Using an explicit path (rather than relying on activation) avoids
# environment-ordering bugs when multiple Python versions are present.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"

launch_server() {
    echo "Starting Django development environment..."

    # Check if virtual environment exists, create if it doesn't
    if [ ! -d "$SCRIPT_DIR/venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "$SCRIPT_DIR/venv"
        echo "Virtual environment created."
    fi

    # Verify the venv Python exists and print its version
    if [ ! -x "$VENV_PYTHON" ]; then
        echo "ERROR: venv not found at $VENV_PYTHON"
        echo "Run: python3 -m venv venv  (using Python 3.10+)"
        exit 1
    fi
    echo "Using $("$VENV_PYTHON" --version) from venv"

    echo "Checking PyTorch CUDA availability..."
    "$VENV_PYTHON" - <<'EOF'
try:
    import torch
    print(f"torch version: {torch.__version__}")
    print(f"cuda available: {torch.cuda.is_available()}")
    print(f"cuda device count: {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"device 0: {torch.cuda.get_device_name(0)}")
    else:
        print("no cuda devices detected")
except ImportError:
    print("torch not installed (skipping CUDA check)")
EOF

    # Install Django if not already installed
    if ! "$VENV_PYTHON" -c "import django" 2>/dev/null; then
        echo "Installing Django..."
        "$VENV_PYTHON" -m pip install django
    fi

    # Set PYTHONPATH to include the project root
    export PYTHONPATH="$SCRIPT_DIR"

    echo "Attempting to start ollama server..."
    (ollama serve &)
    sleep 2
    if ! pgrep -f "ollama serve" > /dev/null; then
        echo "ollama didn't start - LLM features may not work properly"
    else
        echo "Ollama server is running."
    fi

    # Run migrations
    echo "Running database migrations..."
    "$VENV_PYTHON" "$SCRIPT_DIR/mysite/manage.py" makemigrations universe
    "$VENV_PYTHON" "$SCRIPT_DIR/mysite/manage.py" migrate

    # Check if superuser exists, prompt to create if it doesn't
    echo "Checking for superuser..."
    if ! "$VENV_PYTHON" "$SCRIPT_DIR/mysite/manage.py" check_superuser 2>/dev/null; then
        echo "No superuser found. Creating superuser..."
        "$VENV_PYTHON" "$SCRIPT_DIR/mysite/manage.py" createsuperuser
    fi

    # Start development server
    echo "Starting development server..."
    echo "Admin interface will be available at: http://127.0.0.1:8000/admin/"
    echo "Universe view will be available at: http://127.0.0.1:8000/universe/"
    echo
    echo "Press Ctrl+C to stop the server"
    echo "After stopping, press 'R' to migrate and restart, or any other key to exit"
    "$VENV_PYTHON" "$SCRIPT_DIR/mysite/manage.py" runserver
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
