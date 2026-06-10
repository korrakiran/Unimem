"""State builder orchestration to compile and update state.json using event streams."""

from pathlib import Path
from typing import List
from unimem.memory.manager import MemoryManager
from unimem.memory.schemas import ProjectState, Event
from unimem.storage.json_store import JsonStore
from unimem.summarizer.local import LocalSummarizer
from unimem.utils.paths import get_events_dir
from unimem.utils.logger import logger

def rebuild_state(project_root: Path, summarizer_type: str = "local") -> ProjectState:
    """Read all event files chronologically, apply the summarizer, and save the updated state."""
    manager = MemoryManager(project_root)
    if not manager.is_initialized():
        raise FileNotFoundError(f"Unimem is not initialized at {project_root}")
        
    return manager.rebuild_state_from_events(summarizer_type)
