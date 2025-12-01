# Solar
A procedural space system builder 

## Vision
Create a realistic-feeling space traffic control simulation with procedurally generated ships, procedural dialogue, and emergent events. Generate staticky radio voices and comms beeps that evoke the Apollo mission tapes for ambient background fun. 

See /docs/TODO.md for full project vision and roadmap.

## Installing Prerequisites 

### Python Environment Setup - First Time Only 

Note: The launch scripts (`launch-django.bat` for Windows or `launch-django.sh` for Linux/MacOS) will automatically set up a virtual environment for you if one doesn't exist, but you may prefer to set up your environment manually for more control. See **Quick Start** below. 

#### Option 1: Using venv (Recommended)

1. Create a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   
   # Linux/MacOS
   python3 -m venv venv
   ```

2. Activate the virtual environment:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/MacOS
   source venv/bin/activate
   ```

3. Install required packages:
   ```bash
   pip install django
   pip install -r requirements.txt  # If a requirements.txt file exists
   ```

#### Option 2: Using Conda

1. Create a conda environment:
   ```bash
   conda create -n solar python=3.10
   ```

2. Activate the conda environment:
   ```bash
   conda activate solar
   ```

3. Install required packages:
   ```bash
   conda install django
   pip install -r requirements.txt  # For any packages not available in conda
   ```

### Installing Ollama for local LLM support 

**You don't need to run Ollama!** This is compatible with any OpenAI-compatible endpoint. I find Ollama is an easy way to run lightweight LLMs locally (i.e. without paying per-token!), and so I include it here. You can edit `/services/llm_service.py` to configure the URL and API key for any LLM you like. If you are going to configure your own LLM service you're on you're own; but here are the instructions if you want to run Ollama locally: 

1. Install Ollama from [ollama.com](https://ollama.com/)
2. Pull your favorite Qwen2.5 or Llama3 model:

```bash
ollama pull qwen2.5:0.5b

```
or 

```bash 
ollama pull llama3
```

If you don't mind the extra resource usage, `qwen2.5:1.5b` and `llama3` are substantially better for marginally more disk space (about 1GB total) and RAM/VRAM usage. 

3. Run Ollama with the model of your choice loaded: 

```bash
ollama serve
```

This will start an OpenAI service on `localhost:11434` that responds to the game's internal requests for LLM support. 

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

- Universe view: http://127.0.0.1:8000/universe/ - the interface you use to view the layout of Solar's universe 
- Event scroller: http://127.0.0.1:8000/events/ - the dialogue scroller that shows communications going on throughout the solar system 
- Admin interface: http://127.0.0.1:8000/admin/ - the (dreaded) Django admin interface - best not to mess with this!
- Ollama endpoint: https:/127.0.0.1:11434/ - the ollama endpoint simply says 'ollama is running' 

### Development Workflow
The launch scripts include a restart feature for rapid development:

1. Press `Ctrl+C` to stop the server
2. Press `R` to:
   - Run any new database migrations
   - Restart the server automatically
3. Press any other key to exit completely

This is particularly useful when making model changes or other updates that require database migrations.

## Installing Dependencies

### Using pip
```bash
pip install -r requirements.txt
```

### Using conda
```bash
conda env create -f environment.yml
conda activate solar
```

## Manual Setup (if launch scripts don't work)

### Prerequisites
- Python 3.10+
- pip (Python package installer)
- Ollama (https://ollama.com/) for LLM-enhanced dialogue (optional)

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
pip install -r requirements.txt
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
- `universe/models/` - Data models for celestial bodies, navigation, etc.
- `universe/services/` - Service classes including LLM integration
- `universe/views.py` - View logic for displaying the universe
- `tests/` - Test modules including LLM functionality tests
- `xml/` - XML files for universe definition

## Running the unit tests 

Once the server is launched and running, from the `solar/` directory you can run:

```bash
python manage.py test 
```

For more control over test execution:

```bash 
# Run all tests
pytest

# Skip slow tests (like LLM tests)
pytest -m "not slow"

# Only run LLM tests
pytest -m "slow"
```

