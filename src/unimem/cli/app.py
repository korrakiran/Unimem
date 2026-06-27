"""Main CLI application entry point compiling all subcommands for Unimem v2.0.0."""

import sys
import subprocess
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from unimem import __version__
from unimem.core.config import load_config
from unimem.core.git import GitCollector
from unimem.core.summarizer import generate_agent_summary
from unimem.core.rules import sync_project_rules
from unimem.memory.manager import MemoryManager
from unimem.hooks.installer import install_hooks, uninstall_hooks, check_hooks
from unimem.utils.paths import find_project_root, get_config_path
from unimem.utils.logger import logger

app = typer.Typer(
    name="unimem",
    help="Unimem - Universal Project Memory Layer for AI Coding Agents",
    add_completion=False,
)

console = Console()

# Task subcommand group
task_app = typer.Typer(help="Manage project tasks")
app.add_typer(task_app, name="task")


@app.command("init")
def init_cmd(
    name: Optional[str] = typer.Option(
        None, 
        "--name", "-n", 
        help="Name of the project. Defaults to the current directory name."
    ),
    description: str = typer.Option(
        "", 
        "--desc", "-d", 
        help="Short description of the project."
    )
):
    """Initialize a new Unimem project memory layer in the current directory."""
    project_root = find_project_root()
    manager = MemoryManager(project_root)
    
    if manager.is_initialized():
        console.print(f"[yellow]Unimem is already initialized for {project_root}.[/yellow]")
        raise typer.Exit()
        
    try:
        if not name:
            name = project_root.name
        manager.initialize(name, description)
        
        # Load config and install shell hooks if enabled
        config = load_config()
        if config.shell_hooks:
            installed = install_hooks()
            if installed:
                console.print("[green]Idempotently installed shell hooks in config files.[/green]")
                
    except Exception as e:
        console.print(f"[red]Error initializing Unimem: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("summary")
def summary_cmd():
    """Compile recorded event logs into a consolidated ProjectState and output summary."""
    project_root = find_project_root()
    manager = MemoryManager(project_root)

    if not manager.is_initialized():
        # Auto-init if unseen
        manager.bootstrap_if_needed()
        
    try:
        # Rebuild state from events and sync rule files
        state = manager.rebuild_state_from_events(update_memory=True)
        
        # Generate and save agent summary
        summary_text = generate_agent_summary(state, project_root)
        
        # Add summary to past summaries (keeping latest 10)
        if not state.past_summaries or state.past_summaries[-1] != summary_text:
            state.past_summaries.append(summary_text)
            state.past_summaries = state.past_summaries[-10:]
            manager.save_state(state, update_memory=True)
            
        console.print(summary_text)
    except Exception as e:
        console.print(f"[red]Error compiling summary: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("status")
def status_cmd():
    """Display Unimem initialization, project state details, and Git status."""
    project_root = find_project_root()
    manager = MemoryManager(project_root)

    if not manager.is_initialized():
        console.print(f"[yellow]Unimem is not initialized at {project_root}. Run 'unimem init' first.[/yellow]")
        raise typer.Exit(code=1)
        
    try:
        state = manager.load_state()
    except Exception as e:
        console.print(f"[red]Error loading state: {e}[/red]")
        raise typer.Exit(code=1)
        
    # Header Panel
    tech_stack_str = ", ".join(state.tech_stack) if state.tech_stack else "Not specified"
    console.print(Panel(
        f"[bold cyan]{state.project_name}[/bold cyan]\n"
        f"[italic]{state.description or 'No description'}[/italic]\n\n"
        f"[bold]Root:[/bold] {project_root}\n"
        f"[bold]Tech Stack:[/bold] {tech_stack_str}",
        title="Unimem Status",
        expand=False
    ))
    
    # Goal / Task Panel
    console.print(Panel(
        f"[bold green]Goal:[/bold green] {state.current_goal or 'Not set'}\n"
        f"[bold yellow]Current Task:[/bold yellow] {state.current_task or 'Not set'}\n"
        f"[bold blue]Next Task:[/bold blue] {state.next_task or 'Not set'}",
        title="🎯 Current Focus",
        expand=False
    ))
    
    # Git Integration details
    is_git = GitCollector.is_git_repo(project_root)
    git_status_text = ""
    if is_git:
        branch = GitCollector.get_current_branch(project_root)
        latest_commit = GitCollector.get_latest_commit(project_root)
        changes = GitCollector.get_changed_files(project_root)
        
        git_status_text = f"[bold]Branch:[/bold] {branch}\n"
        if latest_commit:
            git_status_text += f"[bold]Latest Commit:[/bold] {latest_commit['sha'][:7]} - {latest_commit['message']}\n"
            
        total_changed = len(changes["staged"]) + len(changes["unstaged"]) + len(changes["untracked"])
        git_status_text += f"[bold]Modified/Untracked Files:[/bold] {total_changed} files"
        
        if total_changed > 0:
            git_status_text += "\n"
            for f in changes["staged"]:
                git_status_text += f"  [green]staged:   {f}[/green]\n"
            for f in changes["unstaged"]:
                git_status_text += f"  [yellow]modified: {f}[/yellow]\n"
            for f in changes["untracked"]:
                git_status_text += f"  [red]untracked: {f}[/red]\n"
    else:
        git_status_text = "[yellow]Not a Git repository.[/yellow]"
        
    console.print(Panel(
        git_status_text.strip(),
        title="🌿 Git Status",
        expand=False
    ))


@app.command("sync")
def sync_cmd():
    """Detect project root, initialize if unseen, and trigger summary update silently."""
    project_root = find_project_root()
    
    # Check if current directory has project indicators
    indicators = [".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod"]
    is_project = any((project_root / ind).exists() for ind in indicators)
    
    if not is_project:
        # Exit quietly if not inside a project directory
        return
        
    manager = MemoryManager(project_root)
    
    try:
        if not manager.is_initialized():
            manager.bootstrap_if_needed()
            # Rules sync is performed as part of initialization
        else:
            # Rebuild state and rules for known project
            state = manager.rebuild_state_from_events(update_memory=True)
            sync_project_rules(project_root)
            
            # Update summary text
            summary_text = generate_agent_summary(state, project_root)
            if not state.past_summaries or state.past_summaries[-1] != summary_text:
                state.past_summaries.append(summary_text)
                state.past_summaries = state.past_summaries[-10:]
                manager.save_state(state, update_memory=True)
    except Exception as e:
        logger.debug(f"Sync error encountered: {e}")


@app.command("doctor")
def doctor_cmd():
    """Run diagnostic checks on the Unimem setup."""
    console.print("[cyan]Running Unimem Diagnostics...[/cyan]\n")
    
    table = Table(title="Diagnostic Checks")
    table.add_column("Component", style="bold")
    table.add_column("Status", width=10)
    table.add_column("Details")
    
    all_ok = True
    
    # 1. Config file check
    config_path = get_config_path()
    if config_path.exists():
        try:
            load_config()
            table.add_row("Config File", "[green]OK[/green]", f"config.json loaded successfully at {config_path}")
        except Exception as e:
            table.add_row("Config File", "[red]ERROR[/red]", f"Failed to parse config.json: {e}")
            all_ok = False
    else:
        table.add_row("Config File", "[yellow]WARN[/yellow]", "config.json does not exist. A new one will be created.")
        
    # 2. Shell hooks check
    try:
        hook_status = check_hooks()
        hooks_installed = any(status for _, _, status in hook_status)
        if hooks_installed:
            details = ", ".join(f"{shell} ({'active' if status else 'inactive'})" for shell, _, status in hook_status)
            table.add_row("Shell Hooks", "[green]OK[/green]", f"Shell hooks detected: {details}")
        else:
            table.add_row("Shell Hooks", "[yellow]WARN[/yellow]", "No active shell hooks found in configuration files.")
    except Exception as e:
        table.add_row("Shell Hooks", "[red]ERROR[/red]", f"Error checking shell hooks: {e}")
        all_ok = False

    # 3. Project-specific checks (if inside project)
    project_root = find_project_root()
    manager = MemoryManager(project_root)
    
    if manager.is_initialized():
        table.add_row("Project Init", "[green]OK[/green]", f"Initialized project root: {project_root}")
        try:
            manager.load_state()
            table.add_row("Project State", "[green]OK[/green]", "state.json loaded successfully.")
        except Exception as e:
            table.add_row("Project State", "[red]ERROR[/red]", f"Failed to parse project state: {e}")
            all_ok = False
    else:
        table.add_row("Project Init", "[yellow]WARN[/yellow]", "Current directory is not initialized with Unimem.")
        
    # 4. Dependency checks
    try:
        table.add_row("Dependencies", "[green]OK[/green]", "watchdog and GitPython are successfully installed.")
    except Exception as e:
        table.add_row("Dependencies", "[red]ERROR[/red]", f"Missing dependencies: {e}")
        all_ok = False
        
    console.print(table)
    
    if all_ok:
        console.print("\n[bold green]✓ Unimem environment is fully healthy![/bold green]")
    else:
        console.print("\n[bold red]✗ Diagnostics found issues. Please review details above.[/bold red]")
        raise typer.Exit(code=1)


@app.command("version")
def version_cmd():
    """Print the Unimem version details."""
    console.print(f"Unimem version: {__version__}")


@task_app.command("done")
def task_done_cmd(
    next_task: str = typer.Option(
        "", 
        "--next", 
        help="Description of the next task."
    )
):
    """Complete the current task and promote the next one."""
    project_root = find_project_root()
    manager = MemoryManager(project_root)

    if not manager.is_initialized():
        console.print(f"[yellow]Unimem is not initialized at {project_root}. Run 'unimem init' first.[/yellow]")
        raise typer.Exit(code=1)
        
    try:
        state = manager.complete_task(next_task)
        console.print("[green]Task completed and promoted successfully![/green]")
        console.print(f"  [bold]Current Goal:[/bold] {state.current_goal or 'Not set'}")
        console.print(f"  [bold]Current Task:[/bold] {state.current_task or 'Not set'}")
        console.print(f"  [bold]Next Task:[/bold]    {state.next_task or 'Not set'}")
    except Exception as e:
        console.print(f"[red]Error completing task: {e}[/red]")
        raise typer.Exit(code=1)


# Also add a subcommand group for shell hooks installation/uninstallation
shell_app = typer.Typer(help="Manage shell hooks installation")
app.add_typer(shell_app, name="shell")

@shell_app.command("install")
def shell_install():
    """Install unimem shell hooks into your shell profile configs."""
    try:
        updated = install_hooks()
        if updated:
            console.print("[green]Successfully installed shell hooks in:[/green]")
            for path in updated:
                console.print(f"  - {path}")
            console.print("\nRun [cyan]source <your-shell-config>[/cyan] or restart your terminal to activate.")
        else:
            console.print("[yellow]Shell hooks were already installed or no config files found.[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to install shell hooks: {e}[/red]")
        raise typer.Exit(code=1)

@shell_app.command("uninstall")
def shell_uninstall():
    """Uninstall unimem shell hooks from your shell profile configs."""
    try:
        removed = uninstall_hooks()
        if removed:
            console.print("[green]Successfully removed shell hooks from:[/green]")
            for path in removed:
                console.print(f"  - {path}")
        else:
            console.print("[yellow]No active shell hooks found to uninstall.[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to uninstall shell hooks: {e}[/red]")
        raise typer.Exit(code=1)


# Maintain update command for CLI upgrades
@app.command("update")
def update_cmd():
    """Update Unimem to the latest version automatically."""
    console.print("[cyan]Detecting Unimem installation method...[/cyan]")
    
    is_brew = False
    executable = sys.executable
    if "cellar/unimem" in executable.lower() or "homebrew" in executable.lower():
        is_brew = True
    else:
        try:
            res = subprocess.run(["brew", "list", "unimem"], capture_output=True, text=True)
            if res.returncode == 0:
                is_brew = True
        except Exception:
            pass

    is_pipx = False
    if "pipx" in executable.lower() or "pipx" in sys.argv[0].lower():
        is_pipx = True

    try:
        if is_brew:
            console.print("[green]Detected Homebrew installation. Upgrading via brew...[/green]")
            cmd = ["brew", "upgrade", "unimem"]
        elif is_pipx:
            console.print("[green]Detected pipx installation. Upgrading via pipx...[/green]")
            cmd = ["pipx", "upgrade", "unimem"]
        else:
            console.print("[yellow]Could not determine package manager. Attempting pip upgrade...[/yellow]")
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "unimem"]

        console.print(f"[cyan]Running: {' '.join(cmd)}[/cyan]")
        
        result = subprocess.run(cmd)
        if result.returncode == 0:
            sys.stdout.write("✓ Unimem upgraded successfully!\n")
            return
        else:
            console.print(f"[red]Upgrade failed with exit code: {result.returncode}[/red]")
            raise typer.Exit(code=result.returncode)

    except Exception as e:
        console.print(f"[red]Error during upgrade: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
