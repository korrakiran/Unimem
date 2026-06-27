# Unimem v2 — Universal Cognitive Memory Layer for AI Coding Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)](https://github.com/korrakiran/Unimem/releases)

**Unimem** is a persistent background cognitive layer designed for AI coding agents (such as Claude Code, Cursor, Gemini CLI, Aider, Windsurf, Cline, and GitHub Copilot). It continuously maintains project memory in the background so that any incoming AI agent can instantly resume work. 

With Unimem, you switch tools mid-project without having to re-explain the architecture, conventions, constraints, or completed features.

---

## The Vision: Zero Daily Commands

Unimem works automatically in the background:
1. **Entering a Repo**: Simply `cd` into your project directory. The shell hook detects the repo, loads the state, and auto-spawns the background watcher daemon.
2. **Coding**: As you work or as AI agents generate code, the filesystem watcher records changes and uses **debounced compilation** (every 3 seconds) to batch-compile log events silently into a consolidated state, avoiding expensive filesystem writes.
3. **Switching Tools**: When you open another agent (e.g. Cursor, Aider, Cline), the agent reads the dynamic rules files or `.unimem/memory.md` and instantly understands the exact context.
4. **Handoff**: Type `unimem continue` to obtain a perfectly compiled prompt template to get any fresh agent up-to-speed immediately.

---

## Key Features

* **Universal Tool Handoff**: Enables seamless context transitions between Claude Code, Cursor, Aider, Windsurf, Cline, and others.
* **Semantic Cognitive Memory**: Tracks crucial project metadata beyond code modifications:
  * **Decisions**: Key design choices (e.g., choice of databases).
  * **Constraints**: Coding rules and testing boundaries.
  * **Preferences**: Custom tech stacks and styles.
  * **Mistakes**: Logged anti-patterns and middleware warnings.
* **Persistent Background Watcher**: Auto-monitors file creations, modifications, deletions, and git status.
* **Debounced Event Compilation**: Collects file events and batches writes every 3 seconds to optimize performance.
* **Idempotent Shell Hooks**: Installs hooks in `.zshrc`, `.bashrc`, and `.config/fish/config.fish` with background execution settings to keep shell interaction quiet.
* **Crash Recovery & Snapshots**: Handles interrupts, orphaned sessions, and saves states automatically on daemon SIGTERM/SIGINT shutdown.
* **100% Local-First**: No network dependencies, no cloud databases, and no external API queries. Your code stays private.

---

## Architecture

```
unimem/
├── bin/            # Executable runner scripts
├── src/            # Modular python package
│   ├── core/       # Daemon runtime, watchers, rules engine, git collectors
│   ├── hooks/      # Silent profile hooks (zsh, bash, fish)
│   ├── memory/     # Database manager, schemas, migrations, snapshots
│   ├── cli/        # Typer entry point and subcommands
│   └── utils/      # System paths, timestamps, logger
├── Formula/        # Audited Homebrew formula
├── README.md       # Documentation
└── pyproject.toml  # Package configuration
```

### Centralized Storage
Project memory databases are saved globally under:
`~/.unimem/projects/<project-id>/`

This directory stores:
* `state.json`: The structured project state schema (including cognitive memory list fields).
* `memory.md`: The human/AI-readable compiled project status.
* `snapshots/`: Historic backups of states.
* `daemon.pid` & `daemon.log`: Lifecycle logs for the background watcher.

A local `.unimem` directory is created as a symlink pointing to the global directory, giving workspace AI agents direct, transparent access.

---

## Installation

Install Unimem using Homebrew with the following shorthand commands:

```bash
# 1. Tap the repository:
brew tap korrakiran/unimem

# 2. Install the package:
brew install korrakiran/unimem/unimem

# 3. Inject the silent shell hooks:
unimem shell install

# 4. Activate in current terminal:
source ~/.zshrc
```

---

## CLI Control Reference

While Unimem runs automatically in the background, you can control it via the CLI:

* **`unimem init`**: Manually initialize Unimem in the current directory and start the background daemon.
* **`unimem status`**: Display project objectives, task progress, git changes, and background daemon status.
* **`unimem continue`**: Output the cognitive handoff prompt for copy-pasting to a fresh AI agent session.
* **`unimem shell [install | uninstall]`**: Install or remove shell hooks.
* **`unimem daemon [run | stop]`**: Manually start or stop the background watcher daemon.
* **`unimem doctor`**: Run system diagnostics (verifies configuration health, dependencies, and shell hooks).
* **`unimem version`**: Print current version (2.0.0).

---

## Cognitive Memory Fields

Unimem state stores cognitive data under clear headings. Add these directly into `.unimem/memory.md` under:
* `## Constraints` (e.g. `Never modify auth pipeline without tests.`)
* `## Mistakes / Anti-Patterns` (e.g. `Previous refactor broke middleware.`)
* `## Coding Preferences` (e.g. `Prefer FastAPI over Flask.`)

On synchronization, Unimem parses and reconciles these items back into `state.json` automatically.
