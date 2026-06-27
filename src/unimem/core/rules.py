"""Rule Injection and Syncing Engine for Unimem v2.0.0."""

from pathlib import Path
from unimem.utils.logger import logger

SUPPORTED_RULE_FILES = [
    "AGENTS.md",
    ".cursorrules",
    ".clauderules",
    ".windsurfrules",
    ".clinerules",
    ".antigravityrules",
    ".geminirules",
    ".aiderrules",
    "CLAUDE.md",
    ".aiderules",
    ".aider.instructions.md",
    ".supermavenrules",
    ".codeiumrules",
    ".continuerules",
    ".doublerules",
    ".tabninerules",
    ".phindrules"
]

UNIMEM_RULES = """# Unimem Agent Instructions
# These are MANDATORY instructions. You MUST follow all rules below exactly without exception.

Unimem is active in this project. You are resuming work from a previous session.

CRITICAL STARTUP RULE:
Do NOT scan, list, or search the entire project repository or folder tree on startup. This wastes token context and is inefficient. Instead, follow these steps immediately:

1. Read the structured project state at `.unimem/state.json` first to get the exact roadmap, goals, tasks, and file listings.
2. Read the human-readable project memory at `.unimem/memory.md` next to get the narrative context, recent decisions, and details.
3. Trust `.unimem/state.json` and `.unimem/memory.md` as the absolute sources of truth for the project state. Do NOT attempt to reconstruct them or scan the repository first.

CRITICAL WORKFLOW RULES:

- You MUST update `.unimem/state.json` with your file changes. To optimize token consumption, batch state syncs: group 3-5 file operations in memory/history before performing a single `.unimem/state.json` write instead of a read→edit→sync cycle for every individual file operation.

- Lazy-load `.unimem/memory.md`: Only read or parse `.unimem/memory.md` when the task type requires it (e.g. handoffs, summaries, or complex task planning), rather than injecting or loading it on every simple file operation.

- When you finish or pause work, always update `.unimem/state.json` first to document completed features, goals, or tasks, then run `unimem summary` to synchronize changes into `memory.md` and keep the supporting `.unimem/` logs aligned.

- When you complete the current task, run: unimem task done --next "describe the next task"

- If you are interrupted or about to stop, always run: unimem task done --next "describe next task" before exiting so context is preserved for the next agent.

UNIMEM UPDATE GUIDELINES:
Run `unimem summary` at checkpoint moments to prevent mid-process context loss:

ALWAYS run `unimem summary` at:
- Major milestones (feature/module completion, architectural decisions)
- Every 45 minutes of continuous work (safety checkpoint)
- Before stopping or pausing work
- At the end of the work session
- After completing a significant refactor or bug fix

DO NOT run `unimem summary` for:
- CSS or styling tweaks (unless part of a major UI overhaul)
- Code formatting or comments
- Typo fixes
- Simple variable renames
- Dependency version bumps
- Whitespace changes

For minor changes: Make the change, build/test, update state.json, but skip `unimem summary` unless approaching a checkpoint time or milestone.

CRASH RECOVERY:
If an agent crashes mid-work:
1. The next agent reads `.unimem/state.json` and its `file_history` to see exactly what was created/modified
2. The next agent reads `.unimem/memory.md` for the last completed milestone
3. The next agent reconstructs only the in-progress work since the last checkpoint, not the entire project

CRITICAL GIT RULE:
- Do NOT stage, commit, or push the `.unimem` directory or any files inside it (such as `.unimem/state.json` or `.unimem/memory.md`). They are local-only project memory.
- Do NOT stage, commit, or push any temporary files, logs, or screenshots (especially those in `/var/folders/`, `/tmp/`, or similar temp folders).
- Do NOT stage, commit, or push any of the auto-generated agent rules or instruction files (such as `AGENTS.md`, `.cursorrules`, `.aiderules`, `.aider.instructions.md`, etc.). These are local configurations and must remain untracked.
"""

def merge_rules(content1: str, content2: str) -> str:
    """Merge two rule contents line-by-line while avoiding duplicates and preserving formatting."""
    lines1 = content1.strip().split("\n")
    lines2 = content2.strip().split("\n")
    
    seen = set()
    merged_lines = []
    
    for line in lines1 + lines2:
        if not line.strip():
            if merged_lines and merged_lines[-1] != "":
                merged_lines.append("")
            continue
        if line not in seen:
            seen.add(line)
            merged_lines.append(line)
            
    return "\n".join(merged_lines).strip()

def sync_project_rules(project_root: Path) -> None:
    """Sync AI rule files by merging home directory templates, project files, and Unimem defaults."""
    home_dir = Path.home()
    
    for rule_file in SUPPORTED_RULE_FILES:
        home_path = home_dir / rule_file
        project_path = project_root / rule_file
        
        home_content = ""
        project_content = ""
        
        if home_path.exists():
            try:
                home_content = home_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.debug(f"Failed to read home rule file {rule_file}: {e}")
                
        if project_path.exists():
            try:
                project_content = project_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.debug(f"Failed to read project rule file {rule_file}: {e}")
                
        # Merge home and project contents
        merged = merge_rules(home_content, project_content)
        
        # Ensure Unimem default instructions are prepended if not already present
        if "Unimem Agent Instructions" not in merged:
            merged = f"{UNIMEM_RULES}\n\n{merged}".strip()
            
        try:
            # Write back to project
            project_path.parent.mkdir(parents=True, exist_ok=True)
            project_path.write_text(merged, encoding="utf-8")
        except Exception as e:
            logger.debug(f"Failed to write rule file {rule_file} to project: {e}")
            
    # Also write to .github/copilot-instructions.md for GitHub Copilot
    copilot_dir = project_root / ".github"
    copilot_file = copilot_dir / "copilot-instructions.md"
    try:
        copilot_dir.mkdir(parents=True, exist_ok=True)
        # Check if already has it
        copilot_content = ""
        if copilot_file.exists():
            copilot_content = copilot_file.read_text(encoding="utf-8")
        if "Unimem Agent Instructions" not in copilot_content:
            copilot_file.write_text(f"{UNIMEM_RULES}\n\n{copilot_content}".strip(), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Failed to write copilot instructions: {e}")
