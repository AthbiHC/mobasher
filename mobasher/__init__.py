"""
Mobasher - Real-Time Live TV Analysis System

A comprehensive system for capturing, processing, and analyzing live television broadcasts
with advanced AI capabilities including Arabic speech recognition, computer vision,
and semantic analysis.
"""

# Load .env from the repo root so all submodules pick up environment variables
try:
    from pathlib import Path
    from dotenv import load_dotenv
    _repo_root = Path(__file__).resolve().parents[2]
    _env_path = _repo_root / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=str(_env_path), override=False)
except Exception:
    # Do not crash if dotenv is unavailable; DBSettings will still handle its own env_file
    pass

__version__ = "0.1.0"
__author__ = "Mobasher Team"
__description__ = "Real-Time Live TV Analysis System"
