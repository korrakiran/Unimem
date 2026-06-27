"""Shell hook installer and manager for Unimem v2.0.0."""

import os
from pathlib import Path
from typing import List, Tuple
from unimem.utils.logger import logger

HOOK_START_MARKER = "# >>> unimem shell hook >>>"
HOOK_END_MARKER = "# <<< unimem shell hook <<<"

ZSH_HOOK_CODE = f"""
{HOOK_START_MARKER}
# Unimem Shell Hook for zsh
unimem_hook() {{
  setopt localoptions nomonitor 2>/dev/null
  if [[ "$PWD" != "$_UNIMEM_LAST_PWD" ]]; then
    export _UNIMEM_LAST_PWD="$PWD"
    unimem sync >/dev/null 2>&1 &
  fi
}}
autoload -U add-zsh-hook 2>/dev/null
add-zsh-hook chpwd unimem_hook 2>/dev/null
add-zsh-hook precmd unimem_hook 2>/dev/null
{HOOK_END_MARKER}
"""

BASH_HOOK_CODE = f"""
{HOOK_START_MARKER}
# Unimem Shell Hook for bash
unimem_hook() {{
  if [[ "$PWD" != "$_UNIMEM_LAST_PWD" ]]; then
    export _UNIMEM_LAST_PWD="$PWD"
    unimem sync >/dev/null 2>&1 &
  fi
}}
if [[ ! "$PROMPT_COMMAND" =~ "unimem_hook" ]]; then
  PROMPT_COMMAND="unimem_hook;$PROMPT_COMMAND"
fi
{HOOK_END_MARKER}
"""

FISH_HOOK_CODE = f"""
{HOOK_START_MARKER}
# Unimem Shell Hook for fish
function __unimem_hook --on-variable PWD
    unimem sync >/dev/null 2>&1 &
end
{HOOK_END_MARKER}
"""

def get_shell_config_paths() -> List[Tuple[str, Path, str]]:
    """Return list of (shell_name, config_file_path, hook_code) tuples."""
    home = Path.home()
    return [
        ("zsh", home / ".zshrc", ZSH_HOOK_CODE),
        ("bash", home / ".bashrc", BASH_HOOK_CODE),
        ("bash", home / ".bash_profile", BASH_HOOK_CODE),
        ("fish", home / ".config" / "fish" / "config.fish", FISH_HOOK_CODE)
    ]

def remove_hook_content(content: str) -> str:
    """Remove unimem hook block from the file content."""
    pattern = re.compile(
        rf"{re.escape(HOOK_START_MARKER)}.*?{re.escape(HOOK_END_MARKER)}",
        re.DOTALL
    )
    return pattern.sub("", content).strip()

import re

def install_hooks() -> List[str]:
    """Install unimem shell hooks into config files in an idempotent manner.
    
    Returns a list of successfully updated config paths.
    """
    updated_files = []
    configs = get_shell_config_paths()
    
    for shell, path, hook in configs:
        # Create directory if it's fish and doesn't exist
        if shell == "fish":
            path.parent.mkdir(parents=True, exist_ok=True)
            
        if not path.exists():
            # For zshrc or bashrc, create it if they are the default shells
            # For others, only write if already present or we want to be safe
            if shell in ["zsh", "bash"]:
                try:
                    path.touch()
                except Exception:
                    continue
            else:
                continue
                
        try:
            content = path.read_text(encoding="utf-8")
            if HOOK_START_MARKER in content:
                # Clean old hooks first to avoid duplicates
                content = remove_hook_content(content)
                
            new_content = f"{content}\n\n{hook}".strip() + "\n"
            path.write_text(new_content, encoding="utf-8")
            updated_files.append(str(path))
        except Exception as e:
            logger.debug(f"Failed to install hook to {path}: {e}")
            
    return updated_files

def uninstall_hooks() -> List[str]:
    """Uninstall unimem shell hooks from config files."""
    removed_files = []
    configs = get_shell_config_paths()
    
    for _, path, _ in configs:
        if not path.exists():
            continue
            
        try:
            content = path.read_text(encoding="utf-8")
            if HOOK_START_MARKER in content:
                new_content = remove_hook_content(content) + "\n"
                path.write_text(new_content, encoding="utf-8")
                removed_files.append(str(path))
        except Exception as e:
            logger.debug(f"Failed to remove hook from {path}: {e}")
            
    return removed_files

def check_hooks() -> List[Tuple[str, Path, bool]]:
    """Check status of shell hooks.
    
    Returns list of (shell_name, path, is_installed) tuples.
    """
    status = []
    configs = get_shell_config_paths()
    
    for shell, path, _ in configs:
        if not path.exists():
            status.append((shell, path, False))
            continue
            
        try:
            content = path.read_text(encoding="utf-8")
            is_installed = HOOK_START_MARKER in content
            status.append((shell, path, is_installed))
        except Exception:
            status.append((shell, path, False))
            
    return status
