"""Filesystem watcher using Watchdog observers for Unimem v2.0.0."""

import time
import threading
from pathlib import Path
from typing import Optional

from unimem.memory.manager import MemoryManager
from unimem.memory.schemas import Event
from unimem.core.file_collector import FileCollector
from unimem.utils.logger import logger

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    FileSystemEventHandler = object
    HAS_WATCHDOG = False

class DebouncedCompiler:
    """Thread-safe debouncer to batch and compile filesystem events."""

    def __init__(self, handler, delay: float = 3.0):
        self.handler = handler
        self.delay = delay
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()

    def touch(self) -> None:
        """Reset the compilation timer."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.delay, self.compile)
            self.timer.start()

    def compile(self) -> None:
        """Trigger compilation execution."""
        try:
            self.handler.batch_operations()
        except Exception as e:
            logger.debug(f"Debounced compilation exception: {e}")


class UnimemFileSystemEventHandler(FileSystemEventHandler if HAS_WATCHDOG else object):
    """Listens to filesystem events and writes event summaries to Unimem."""

    def __init__(self, project_root: Path):
        if HAS_WATCHDOG:
            super().__init__()
        self.project_root = project_root
        self.manager = MemoryManager(project_root)
        self._pending_events = []
        self.compiler = DebouncedCompiler(self, delay=3.0)

    def _should_process(self, path_str: str) -> bool:
        """Filter out files that should be ignored."""
        path = Path(path_str)
        if path.is_dir():
            return False
        return not FileCollector.should_ignore(path, self.project_root)

    def _record_file_event(self, event_type: str, path: str, dest_path: str = "") -> None:
        """Create and write a filesystem event to Unimem."""
        try:
            rel_path = str(Path(path).relative_to(self.project_root))
            files = [rel_path]
            
            if event_type == "moved" and dest_path:
                rel_dest = str(Path(dest_path).relative_to(self.project_root))
                files.append(rel_dest)
                summary = f"Moved file from '{rel_path}' to '{rel_dest}'"
            elif event_type == "created":
                summary = f"Created file '{rel_path}'"
            elif event_type == "deleted":
                summary = f"Deleted file '{rel_path}'"
            else:
                summary = f"Modified file '{rel_path}'"

            if not self.manager.is_initialized():
                return

            event = Event(
                tool="watcher",
                event_type=f"file_{event_type}",
                prompt="",
                response_summary=summary,
                files_changed=files
            )
            self._pending_events.append(event)
            logger.info(f"[watcher] Queued {event_type} event for {rel_path}")
            
            # Touch debouncer to trigger compiler batching
            self.compiler.touch()
        except Exception as e:
            logger.debug(f"Error handling watcher event: {e}")

    def batch_operations(self) -> None:
        """Process buffered events and perform a single write."""
        if not self._pending_events:
            return
            
        events_to_process = list(self._pending_events)
        self._pending_events.clear()
        
        logger.info(f"[watcher] Batch compiling {len(events_to_process)} file events...")
        self.manager.record_events_batch(events_to_process, auto_snapshot=True)

    def on_created(self, event) -> None:
        if self._should_process(event.src_path):
            self._record_file_event("created", event.src_path)

    def on_modified(self, event) -> None:
        if self._should_process(event.src_path):
            self._record_file_event("modified", event.src_path)

    def on_deleted(self, event) -> None:
        if self._should_process(event.src_path):
            self._record_file_event("deleted", event.src_path)

    def on_moved(self, event) -> None:
        if self._should_process(event.src_path) or (hasattr(event, 'dest_path') and self._should_process(event.dest_path)):
            dest = getattr(event, 'dest_path', "")
            self._record_file_event("moved", event.src_path, dest)


class FilesystemWatcher:
    """Manages the startup and shutdown of the filesystem watch service."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.handler = UnimemFileSystemEventHandler(project_root)
        self.observer: Optional[Observer] = None

    def start(self) -> None:
        """Start monitoring the project directory for file events."""
        if not HAS_WATCHDOG:
            logger.warning("[yellow]Watchdog is not installed. File watching is disabled.[/yellow]")
            return
            
        logger.info(f"[cyan]Starting Unimem filesystem watcher on {self.project_root}...[/cyan]")
        self.observer = Observer()
        self.observer.schedule(self.handler, path=str(self.project_root), recursive=True)
        self.observer.start()
        logger.info("[green]Watcher service is running. Press Ctrl+C to exit.[/green]")

    def stop(self) -> None:
        """Stop the filesystem monitor."""
        if self.observer:
            logger.info("Stopping filesystem watcher...")
            if hasattr(self.handler, 'batch_operations'):
                self.handler.batch_operations()
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Watcher service stopped.")

    def run_forever(self) -> None:
        """Keep the watcher running until interrupted (blocking)."""
        self.start()
        if not HAS_WATCHDOG:
            return
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Watcher interrupted by user.")
        finally:
            self.stop()
