# Solar
A procedural space system builder

## Vision
Create a realistic-feeling space traffic control simulation with procedurally generated ships, dialogue, and events. See /docs/TODO.md for full project vision and roadmap.

## Quick Start

### Windows
Double-click `launch-django.bat` in the project root directory.

### Linux/MacOS
From the project root directory:

```bash
chmod +x launch-django.sh  # Make the script executable (first time only)
./launch-django.sh
```

The server will start automatically and open these URLs:
- Admin interface: http://127.0.0.1:8000/admin/
- Universe view: http://127.0.0.1:8000/universe/

### Development Workflow
The launch scripts include a restart feature for rapid development:

1. Press `Ctrl+C` to stop the server
2. Press `R` to:
   - Run any new database migrations
   - Restart the server automatically
3. Press any other key to exit completely

This is particularly useful when making model changes or other updates that require database migrations.

## Manual Setup (if launch scripts don't work)

### Prerequisites
- Python 3.x
- pip (Python package installer)

### First-Time Setup
1. Create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

2. Install required packages:

```bash
pip install django
```

3. Navigate to the mysite directory and run migrations:

```bash
cd mysite
python manage.py makemigrations universe
python manage.py migrate
```

4. Create an admin superuser:

```bash
python manage.py createsuperuser
```

### Running the Development Server
1. Ensure your virtual environment is activated
2. Navigate to the mysite directory
3. Run the development server:

```bash
python manage.py runserver
```

### Project Structure
- `universe/` - Main Django app containing the space simulation
- `universe/models.py` - Data models for celestial bodies
- `universe/views.py` - View logic for displaying the universe
- `wordlists/` - Text files for procedural name generation
- `milkyway.xml` - Sample solar system data

## Development Notes
- The project uses Django's built-in SQLite database
- Models follow a hierarchical structure: Galaxy -> StarSystem -> Star -> Planet -> Moon
- Space stations can orbit any celestial body