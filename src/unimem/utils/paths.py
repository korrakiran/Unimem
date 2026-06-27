"""Path utilities for locating project root and global/project-specific memory directories."""

import hashlib
import os
from pathlib import Path
from typing import Optional

def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Find the project root by looking for .git, package.json, pyproject.toml, Cargo.toml, or go.mod.
    
    Traverses parent directories from start_path (defaults to current working directory).
    If none is found, returns the starting path.
    """
    if start_path is None:
        # Avoid using cwd if it does not exist or we don't have access
        try:
            start_path = Path.cwd()
        except Exception:
            start_path = Path.home()
        
    start_path = start_path.resolve()
    current = start_path
    
    while True:
        if (current / ".git").exists() or \
           (current / "package.json").exists() or \
           (current / "pyproject.toml").exists() or \
           (current / "Cargo.toml").exists() or \
           (current / "go.mod").exists():
            return current
        
        # Stop at root
        if current.parent == current:
            break
        current = current.parent
        
    return start_path

def get_global_unimem_dir() -> Path:
    """Get the path to the global ~/.unimem directory."""
    return Path.home() / ".unimem"

def get_projects_dir() -> Path:
    """Get the path to ~/.unimem/projects directory."""
    return get_global_unimem_dir() / "projects"

def get_config_path() -> Path:
    """Get the path to ~/.unimem/config.json."""
    return get_global_unimem_dir() / "config.json"

def get_project_id(project_root: Path) -> str:
    """Generate a unique and stable identifier for a project based on its path."""
    path_str = str(project_root.resolve())
    h = hashlib.sha256(path_str.encode("utf-8")).hexdigest()[:8]
    # Strip non-alphanumeric chars for a safe folder name
    safe_name = "".join(c for c in project_root.name if c.isalnum() or c in ("-", "_"))
    if not safe_name:
        safe_name = "project"
    return f"{safe_name}-{h}"

def get_project_mem_dir(project_root: Path) -> Path:
    """Get the path to the global project memory directory: ~/.unimem/projects/<project-id>/"""
    return get_projects_dir() / get_project_id(project_root)

def get_events_dir(project_root: Path) -> Path:
    """Get the path to ~/.unimem/projects/<project-id>/events"""
    return get_project_mem_dir(project_root) / "events"

def get_sessions_dir(project_root: Path) -> Path:
    """Get the path to ~/.unimem/projects/<project-id>/sessions"""
    return get_project_mem_dir(project_root) / "sessions"

def get_snapshots_dir(project_root: Path) -> Path:
    """Get the path to ~/.unimem/projects/<project-id>/snapshots"""
    return get_project_mem_dir(project_root) / "snapshots"

def get_decisions_dir(project_root: Path) -> Path:
    """Get the path to ~/.unimem/projects/<project-id>/decisions"""
    return get_project_mem_dir(project_root) / "decisions"

def get_state_file(project_root: Path) -> Path:
    """Get the path to ~/.unimem/projects/<project-id>/state.json"""
    return get_project_mem_dir(project_root) / "state.json"

def get_memory_md(project_root: Path) -> Path:
    """Get the path to ~/.unimem/projects/<project-id>/memory.md"""
    return get_project_mem_dir(project_root) / "memory.md"
