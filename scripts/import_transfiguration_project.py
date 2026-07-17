"""Import the bundled five-minute Transfiguration plan into CineForge.

Planning only: no ComfyUI submission, model download, or render enqueue.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.transfiguration_project_import import main

if __name__ == "__main__":
    main()
