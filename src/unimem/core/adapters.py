"""Adapters for wrapping AI agent sessions and injecting project context into their environments for Unimem v2.0.0."""

import os
import signal
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Type, Optional

from unimem.memory.manager import MemoryManager
from unimem.memory.schemas import Event, Session
from unimem.core.git import GitCollector
from unimem.core.file_collector import FileCollector
from unimem.utils.logger import logger

class BaseAdapter(ABC):
    """Abstract base class that connects specific AI agent environments with Unimem."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    @abstractmethod
    def load_context(self) -> Dict[str, Any]:
        """Extract and format the project intelligence data for the target agent."""
        pass

    @abstractmethod
    def save_session(self, session_id: str, summary: str, files_changed: List[str]) -> None:
        """Record and end the current session."""
        pass

    @abstractmethod
    def launch(self, command: List[str]) -> Any:
        """Launch the AI agent process, wrapping its execution in a Unimem session."""
        pass


class AdapterRegistry:
    """Registry to map adapter names to their implementing classes."""
    _registry: Dict[str, Type[BaseAdapter]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register an adapter class."""
        def decorator(subclass: Type[BaseAdapter]):
            cls._registry[name.lower()] = subclass
            return subclass
        return decorator

    @classmethod
    def get_adapter(cls, name: str, project_root: Path) -> BaseAdapter:
        """Resolve and instantiate an adapter by name. Falls back to 'generic'."""
        adapter_name = name.lower()
        if adapter_name not in cls._registry:
            logger.warning(f"Adapter '{name}' not found. Falling back to 'generic'.")
            adapter_name = "generic"
            
        adapter_cls = cls._registry[adapter_name]
        return adapter_cls(project_root)

    @classmethod
    def list_adapters(cls) -> List[str]:
        """List all registered adapters."""
        return list(cls._registry.keys())


@AdapterRegistry.register("generic")
class GenericAdapter(BaseAdapter):
    """Generic adapter for running arbitrary tool commands inside Unimem context environment."""

    def load_context(self) -> Dict[str, Any]:
        """Load project state and return environment configurations."""
        manager = MemoryManager(self.project_root)
        if not manager.is_initialized():
            return {}
            
        try:
            state = manager.load_state(reconcile_memory=True)
            
            task_str = state.current_task.lower()
            goal_str = state.current_goal.lower()
            narrative_keywords = ["handoff", "summary", "plan", "design", "architecture", "review", "refactor", "initialize"]
            requires_memory = not state.current_task or any(k in task_str or k in goal_str for k in narrative_keywords)
            
            from unimem.utils.paths import get_memory_md
            memory_md_path = get_memory_md(self.project_root)
            context_md = ""
            if memory_md_path.exists():
                if requires_memory:
                    context_md = memory_md_path.read_text(encoding="utf-8")
                else:
                    context_md = "Unimem active. Read .unimem/memory.md for full project memory."
                    
            return {
                "project_name": state.project_name,
                "current_goal": state.current_goal,
                "current_task": state.current_task,
                "context_md": context_md,
                "state_json": state.model_dump_json()
            }
        except Exception as e:
            logger.error(f"Failed to load generic context: {e}")
            return {}

    def save_session(self, session_id: str, summary: str, files_changed: List[str]) -> None:
        """Saves session info by delegating to MemoryManager."""
        manager = MemoryManager(self.project_root)
        if not manager.is_initialized():
            return
            
        event = Event(
            tool="generic",
            event_type="agent_run",
            prompt=f"Session execution summary for session {session_id}",
            response_summary=summary,
            files_changed=files_changed
        )
        manager.record_event(event)

    def launch(self, command: List[str]) -> subprocess.CompletedProcess:
        """Launch a tool subprocess with Unimem variables injected into env."""
        if not command:
            raise ValueError("No command provided to launch.")
            
        manager = MemoryManager(self.project_root)
        session_id = None
        
        if manager.is_initialized():
            session = manager.start_session("generic")
            session_id = session.session_id
            
        context = self.load_context()
        env = os.environ.copy()
        if context:
            env["UNIMEM_ACTIVE"] = "true"
            env["UNIMEM_PROJECT"] = context.get("project_name", "")
            env["UNIMEM_CONTEXT_MD"] = context.get("context_md", "")
            env["UNIMEM_STATE_JSON"] = context.get("state_json", "")
            env["UNIMEM_SESSION_ID"] = session_id or ""
            
        initial_changed = []
        if GitCollector.is_git_repo(self.project_root):
            git_stats = GitCollector.get_changed_files(self.project_root)
            initial_changed = git_stats["unstaged"] + git_stats["staged"] + git_stats["untracked"]
            
        logger.info(f"Launching subprocess: {' '.join(command)}")

        def _handle_signal(signum, frame):
            if session_id and manager.is_initialized():
                manager.end_session(session_id)
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        try:
            result = subprocess.run(command, env=env, shell=False)
            
            final_changed = []
            if GitCollector.is_git_repo(self.project_root):
                git_stats = GitCollector.get_changed_files(self.project_root)
                all_changed = git_stats["unstaged"] + git_stats["staged"] + git_stats["untracked"]
                final_changed = sorted(list(set(all_changed) - set(initial_changed)))
            else:
                final_changed = FileCollector.get_recently_modified_files(self.project_root, limit=5)
                
            if session_id and manager.is_initialized():
                summary = f"Subprocess command finished with exit code {result.returncode}."
                self.save_session(session_id, summary, final_changed)
                manager.end_session(session_id)
                
            return result
        except Exception as e:
            logger.error(f"Error launching subprocess: {e}")
            if session_id and manager.is_initialized():
                manager.end_session(session_id)
            raise


@AdapterRegistry.register("claude")
class ClaudeAdapter(GenericAdapter):
    """Adapter for wrapping Claude Code sessions."""

    def launch(self, command: Optional[List[str]] = None) -> None:
        """Launch Claude Code, defaulting to standard CLI execution."""
        if not command:
            command = ["claude"]
            
        logger.info("[cyan]Initializing Claude Code Unimem Adapter...[/cyan]")
        
        manager = MemoryManager(self.project_root)
        session_id = None
        if manager.is_initialized():
            session = manager.start_session("claude")
            session_id = session.session_id
            
        try:
            context = self.load_context()
            env = os.environ.copy()
            if context:
                env["UNIMEM_ACTIVE"] = "true"
                env["UNIMEM_PROJECT"] = context.get("project_name", "")
                env["UNIMEM_CONTEXT_MD"] = context.get("context_md", "")
                env["UNIMEM_STATE_JSON"] = context.get("state_json", "")
                env["UNIMEM_SESSION_ID"] = session_id or ""
                
            initial_changed = []
            if GitCollector.is_git_repo(self.project_root):
                git_stats = GitCollector.get_changed_files(self.project_root)
                initial_changed = git_stats["unstaged"] + git_stats["staged"] + git_stats["untracked"]
                
            logger.info(f"Running Claude Code: {' '.join(command)}")

            def _handle_signal(signum, frame):
                if session_id and manager.is_initialized():
                    manager.end_session(session_id)
                signal.signal(signum, signal.SIG_DFL)
                os.kill(os.getpid(), signum)

            signal.signal(signal.SIGTERM, _handle_signal)
            signal.signal(signal.SIGINT, _handle_signal)

            result = subprocess.run(command, env=env, shell=False)
            
            final_changed = []
            if GitCollector.is_git_repo(self.project_root):
                git_stats = GitCollector.get_changed_files(self.project_root)
                all_changed = git_stats["unstaged"] + git_stats["staged"] + git_stats["untracked"]
                final_changed = sorted(list(set(all_changed) - set(initial_changed)))
                
            if session_id and manager.is_initialized():
                event = Event(
                    tool="claude",
                    event_type="agent_run",
                    prompt=f"Claude session finished with exit code {result.returncode}",
                    response_summary=f"Claude completed task with exit code {result.returncode}.",
                    files_changed=final_changed
                )
                manager.record_event(event)
                manager.end_session(session_id)
        except FileNotFoundError:
            logger.error("[red]Claude command not found. Please ensure 'claude' CLI is installed.[/red]")
            if session_id and manager.is_initialized():
                manager.end_session(session_id)
        except Exception as e:
            logger.error(f"Error executing Claude: {e}")
            if session_id and manager.is_initialized():
                manager.end_session(session_id)


@AdapterRegistry.register("gemini")
class GeminiAdapter(GenericAdapter):
    """Adapter for wrapping Gemini Code sessions."""

    def launch(self, command: Optional[List[str]] = None) -> None:
        if not command:
            command = ["gemini"]
        logger.info("[cyan]Initializing Gemini Unimem Adapter...[/cyan]")
        # Standard launch wraps gemini command identical to claude
        # (We skip duplicate details for brevity but register the adapter name)
        super().launch(command)


@AdapterRegistry.register("codex")
class CodexAdapter(GenericAdapter):
    """Adapter for wrapping Codex/Copilot sessions."""

    def launch(self, command: Optional[List[str]] = None) -> None:
        if not command:
            command = ["copilot"]
        logger.info("[cyan]Initializing Copilot Unimem Adapter...[/cyan]")
        super().launch(command)


def load_builtin_adapters() -> None:
    """Trigger registration of built-in adapters."""
    pass
