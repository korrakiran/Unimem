"""Tests for Unimem v2.0.0 features: init, summary, shell hooks, rule sync, and memory persistence."""

import os
import shutil
from pathlib import Path
import pytest
from unimem.memory.manager import MemoryManager
from unimem.memory.schemas import ProjectState, Event
from unimem.core.config import load_config, save_config, Config
from unimem.core.rules import sync_project_rules, SUPPORTED_RULE_FILES
from unimem.hooks.installer import install_hooks, uninstall_hooks, check_hooks
from unimem.utils.paths import get_project_mem_dir, get_state_file, get_memory_md
import unimem.utils.paths

@pytest.fixture(autouse=True)
def mock_home_unimem(tmp_path, monkeypatch):
    """Mock Path.home() and get_global_unimem_dir to point to a temporary test directory."""
    test_home = tmp_path / "fake_home"
    test_home.mkdir()
    
    # Mock Path.home
    monkeypatch.setattr(Path, "home", lambda: test_home)
    
    # Mock paths.get_global_unimem_dir
    monkeypatch.setattr(unimem.utils.paths, "get_global_unimem_dir", lambda: test_home / ".unimem")
    
    yield test_home

def test_init_and_memory_persistence(temp_dir):
    """Test initializing a project and verifying memory files are persisted globally with local symlink."""
    manager = MemoryManager(temp_dir)
    assert not manager.is_initialized()
    
    # Initialize
    manager.initialize("TestProject", "A test description.")
    assert manager.is_initialized()
    
    # Check that global directory was created
    global_dir = get_project_mem_dir(temp_dir)
    assert global_dir.exists()
    assert (global_dir / "state.json").exists()
    assert (global_dir / "memory.md").exists()
    
    # Check that state fields are populated correctly
    state = manager.load_state()
    assert state.project_name == "TestProject"
    assert state.description == "A test description."
    assert "Initialize the repository and basic components" in state.current_goal
    
    # Modify state and save
    state.current_goal = "New Goal"
    state.tech_stack = ["Python", "Typer"]
    manager.save_state(state)
    
    # Verify loaded state matches
    loaded = manager.load_state()
    assert loaded.current_goal == "New Goal"
    assert loaded.tech_stack == ["Python", "Typer"]

def test_summary_engine(temp_dir):
    """Test summary compilation from events."""
    manager = MemoryManager(temp_dir)
    manager.initialize("TestProject")
    
    # Record some mock events
    event1 = Event(
        tool="test-agent",
        event_type="file_created",
        prompt="Create README",
        response_summary="Created README.md with instructions.",
        files_changed=["README.md"]
    )
    manager.record_event(event1)
    
    event2 = Event(
        tool="test-agent",
        event_type="agent_run",
        prompt="Implement feature",
        response_summary="Implemented feature auth in auth.py.",
        files_changed=["auth.py"]
    )
    manager.record_event(event2)
    
    # Rebuild state
    state = manager.rebuild_state_from_events()
    
    # Heuristics should pick up 'auth' or 'feature' and files
    assert len(state.file_history) > 0
    assert "README.md" in state.important_files or "auth.py" in state.important_files

def test_rule_sync(temp_dir, mock_home_unimem):
    """Test AI rule sync, merging home templates and project files with Unimem defaults."""
    # Write a template in fake home directory
    home_cursorrules = mock_home_unimem / ".cursorrules"
    home_cursorrules.write_text("Home rule settings", encoding="utf-8")
    
    # Write a project file
    project_cursorrules = temp_dir / ".cursorrules"
    project_cursorrules.write_text("Project rule settings", encoding="utf-8")
    
    # Run sync
    sync_project_rules(temp_dir)
    
    # Verify both got merged and Unimem defaults are added
    assert project_cursorrules.exists()
    content = project_cursorrules.read_text(encoding="utf-8")
    assert "Unimem Agent Instructions" in content
    assert "Home rule settings" in content
    assert "Project rule settings" in content

def test_shell_hooks(mock_home_unimem):
    """Test shell hooks installer installs and uninstalls cleanly."""
    # Create fake shell config files
    zshrc = mock_home_unimem / ".zshrc"
    zshrc.write_text("# Old settings", encoding="utf-8")
    
    # Install hooks
    installed = install_hooks()
    assert len(installed) > 0
    assert str(zshrc) in installed
    
    # Check hook status
    status = check_hooks()
    zsh_status = next(s for s in status if s[0] == "zsh")
    assert zsh_status[2] is True # Installed
    
    # Verify file content
    content = zshrc.read_text(encoding="utf-8")
    assert "unimem_hook" in content
    
    # Uninstall hooks
    uninstalled = uninstall_hooks()
    assert len(uninstalled) > 0
    assert str(zshrc) in uninstalled
    
    # Verify file content is clean
    content_clean = zshrc.read_text(encoding="utf-8")
    assert "unimem_hook" not in content_clean
    assert "# Old settings" in content_clean
