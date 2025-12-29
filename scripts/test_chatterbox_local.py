"""
Test-drive Chatterbox-Turbo locally using the downloaded weights.

Usage:
    SET DJANGO_SETTINGS_MODULE=mysite.settings
    SET CHATTERBOX_LOCAL_PATH=C:\\Users\\Jurph\\Documents\\Python Scripts\\solar\\models\\chatterbox-turbo
    python scripts/test_chatterbox_local.py
    
    Or explicitly use venv Python:
    .\venv\Scripts\python.exe scripts\test_chatterbox_local.py
"""

from pathlib import Path
import sys
import os

# Ensure we're using the venv Python
_venv_python = Path(__file__).parent.parent / "venv" / "Scripts" / "python.exe"
if _venv_python.exists() and sys.executable != str(_venv_python) and not os.environ.get("_VENV_RERUN"):
    print(f"Warning: Not using venv Python. Expected: {_venv_python}")
    print(f"Current: {sys.executable}")
    print("Re-running with venv Python...")
    import subprocess
    os.environ["_VENV_RERUN"] = "1"
    sys.exit(subprocess.call([str(_venv_python), __file__] + sys.argv[1:]))

# Setup Django BEFORE importing any Django-dependent code
current_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(current_path))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

import django
django.setup()

# Now we can import Django-dependent code
from mysite.universe.services.tts_service import get_tts_service


def main() -> int:
    # Load canonical audio sentences
    canonical_file = Path(__file__).parent.parent / "docs" / "Canonical Audio Sentences.txt"
    with open(canonical_file, 'r', encoding='utf-8') as f:
        sentences = [line.strip() for line in f if line.strip()]
    
    print(f"Loaded {len(sentences)} canonical sentences")
    
    voices = [
        "pilot-M-001",
        "pilot-M-002",
        "pilot-F-001",
        "controller-M-001",
    ]

    service = get_tts_service()
    print(f"TTS Service device: {service.device}")
    import torch
    print(f"CUDA available: {torch.cuda.is_available()}")
    outdir = Path("audio/voices/generated")
    outdir.mkdir(parents=True, exist_ok=True)

    # Combine all sentences into a single text with pauses
    combined_text = " ".join(sentences)
    print(f"Combined text: {combined_text[:100]}...")
    
    any_failed = False
    for v in voices:
        try:
            wav_bytes = service.generate(text=combined_text, voice_id=v)
            out_path = outdir / f"{v}_canonical_all.wav"
            out_path.write_bytes(wav_bytes)
            print(f"Generated {out_path} ({len(wav_bytes)} bytes)")
        except Exception as e:
            any_failed = True
            print(f"Failed for {v}: {e}")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())

