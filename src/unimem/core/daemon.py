"""Background daemon process management for Unimem v2.0.0."""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from unimem.utils.paths import get_project_mem_dir
from unimem.utils.logger import logger
from unimem.core.watcher import FilesystemWatcher

def get_pid_file(project_root: Path) -> Path:
    """Return path to daemon.pid file."""
    return get_project_mem_dir(project_root) / "daemon.pid"

def get_log_file(project_root: Path) -> Path:
    """Return path to daemon.log file."""
    return get_project_mem_dir(project_root) / "daemon.log"

def is_daemon_running(project_root: Path) -> bool:
    """Verify if the daemon is currently running using the PID file."""
    pid_file = get_pid_file(project_root)
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False

def start_daemon(project_root: Path) -> None:
    """Spawn the daemon process in the background, fully detached."""
    if is_daemon_running(project_root):
        logger.debug("Daemon is already running.")
        return

    log_file_path = get_log_file(project_root)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Run: python3 -m unimem.cli.app daemon run --root <project_root>
    cmd = [
        sys.executable,
        "-m", "unimem.cli.app",
        "daemon", "run",
        "--root", str(project_root)
    ]
    
    with open(log_file_path, "a", encoding="utf-8") as f:
        subprocess.Popen(
            cmd,
            stdout=f,
            stderr=f,
            start_new_session=True,
            env=os.environ.copy()
        )
    logger.debug(f"Daemon process spawned in the background. Log: {log_file_path}")

def stop_daemon(project_root: Path) -> None:
    """Terminate the running background daemon process."""
    pid_file = get_pid_file(project_root)
    if not pid_file.exists():
        logger.debug("No daemon PID file found.")
        return
        
    try:
        pid = int(pid_file.read_text().strip())
        logger.info(f"Stopping daemon process with PID {pid}...")
        os.kill(pid, signal.SIGTERM)
        # Wait up to 5 seconds for it to exit
        for _ in range(50):
            if not is_daemon_running(project_root):
                break
            time.sleep(0.1)
    except Exception as e:
        logger.debug(f"Failed to kill daemon process: {e}")
    finally:
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass

def run_daemon(project_root: Path) -> None:
    """Main blocking run loop for the daemon process."""
    pid_file = get_pid_file(project_root)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    
    logger.info(f"Unimem background daemon started with PID {os.getpid()} on {project_root}")
    
    watcher = FilesystemWatcher(project_root)
    
    def cleanup(signum, frame):
        logger.info(f"Received signal {signum}. Shutting down daemon...")
        watcher.stop()
        # Save final project state before exiting
        try:
            from unimem.memory.manager import MemoryManager
            manager = MemoryManager(project_root)
            if manager.is_initialized():
                state = manager.load_state(reconcile_memory=True)
                manager.save_state(state, update_memory=True)
                logger.info("Saved final state on daemon shutdown.")
        except Exception as e:
            logger.debug(f"Error saving state on daemon shutdown: {e}")
            
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        watcher.run_forever()
    except Exception as e:
        logger.error(f"Daemon watcher encountered exception: {e}")
    finally:
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass
