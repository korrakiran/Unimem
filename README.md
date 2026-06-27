# Unimem

### The Universal Project Memory Layer for AI Coding Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform Support](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](#-installation)
[![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)](https://github.com/korrakiran/Unimem/releases)

---

## Why Unimem?

AI coding agents are powerful, but they are bounded by context limits and session boundaries:
* **Context Loss**: Every time you start a new chat, run a new agent command, or switch tools, the agent forgets previous progress.
* **Redundant Onboarding**: You waste time re-explaining the architecture, code conventions, ongoing tasks, and recent decisions.
* **Tool Fragmentation**: Switching between Claude Code, Aider, Gemini CLI, or Cursor means manually copying summaries and instruction files back and forth.

**Unimem solves this by acting as a persistent, background memory layer for your workspace.** It maintains a centralized, structured database of project objectives, tech stack settings, completed tasks, and architectural decisions, automatically injecting this context into all compliant AI coding tools.

---

## Key Features

* **Persistent Project Memory**: Centralized project state keeps track of goals, pending tasks, tech stack details, and custom coding preferences across tool restarts.
* **Auto Project Detection**: Identifies git roots, `package.json`, `pyproject.toml`, `Cargo.toml`, or `go.mod` files to automatically map project memory.
* **Seamless Shell Integration**: Background shell hooks silently update project context whenever you change directories, avoiding manual command runs.
* **Bi-directional Sync (`memory.md` ⟷ `state.json`)**: Auto-generates a clean, human/AI-readable `memory.md` markdown file. Any direct updates written to it by AI agents are parsed and reconciled back into structured state JSON.
* **AI Rule Auto-Injections**: Dynamically generates and updates configuration rules for multiple tools (e.g. `.cursorrules`, `.clauderules`, `.clinerules`, `.aiderules`, and `.aider.instructions.md`).
* **Tool Configuration Merging**: Merges system-wide rules templates in your home folder with workspace-specific configurations, ensuring instructions never duplicate.
* **Automatic Snapshots & Crash Recovery**: Captures backups of the project state and maintains tracking sessions. Close-out triggers ensure logs are saved even if an agent process terminates unexpectedly.
* **Git-Aware Context updates**: Inspects git branch history, latest commits, staged modifications, and untracked files to compile event trails.
* **100% Local and Private**: Runs entirely on your machine. No cloud storage, no external LLM API calls, and no data leaves your local system.

### Supported Tools
* **Cursor** (`.cursorrules`)
* **Claude Code** (`.clauderules`)
* **Gemini CLI** (`.geminirules`)
* **Aider** (`.aiderules`, `.aider.instructions.md`)
* **Cline** (`.clinerules`)
* **Windsurf** (`.windsurfrules`)
* **Continue** (`.continuerules`)
* **Supermaven** (`.supermavenrules`)
* **Codeium** (`.codeiumrules`)
* **Tabnine** (`.tabninerules`)

---

## Architecture

Unimem separates execution concerns into clean, modular layers:

```
                  ┌───────────────────────────────────┐
                  │             CLI Layer             │
                  │   (init, summary, status, task)   │
                  └─────────────────┬─────────────────┘
                                    │
                  ┌─────────────────▼─────────────────┐
                  │            Core Engine            │
                  │ (Git/File collection, Adapters)   │
                  └─────────────────┬─────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
┌────────▼────────┐        ┌────────▼────────┐        ┌────────▼────────┐
│   Hooks Layer   │        │  Rules Engine   │        │  Memory Layer   │
│ (Shell hooks:   │        │ (Merges home &  │        │ (Global storage │
│  zsh/bash/fish) │        │  project rules) │        │  & symlinking)  │
└─────────────────┘        └─────────────────┘        └─────────────────┘
```

### Storage Registry
Unimem keeps your workspace roots clean by storing all database files in your home directory:
`~/.unimem/projects/<project-id>/`

Inside this folder, Unimem maintains:
* `state.json`: The raw, structured project roadmap, tech stack, and file operations registry.
* `memory.md`: The markdown representation of the project brain that AI tools consume.
* `events/`: Historical stream of log updates.
* `sessions/`: Log files detailing tool interaction durations.
* `snapshots/`: Versioned state snapshots for historical rollbacks.
* `decisions/`: Architecture design decision logs.

A lightweight, local symlink `.unimem` is placed in the project root pointing to the global directory, giving workspace AI tools transparent access.

---

## Installation

### Via Homebrew (Recommended)
Because Homebrew shorthand taps assume a separate `homebrew-unimem` repository, and Unimem uses a single-repo structure, you must explicitly supply the URL to the main repository:

```bash
# 1. Tap the primary repository directly:
brew tap korrakiran/unimem https://github.com/korrakiran/Unimem.git

# 2. Install the package:
brew install unimem

# 3. Inject silent shell hooks:
unimem shell install

# 4. Activate the changes in your current terminal:
source ~/.zshrc
```

### Via pipx
```bash
pipx install unimem
unimem shell install
source ~/.zshrc
```

---

## Command Reference

### `unimem init`
Sets up project memory database inside the current directory.
```bash
unimem init --name "My project" --desc "A web application"
```

### `unimem status`
Prints a formatted summary detailing the project goal, tasks progress, git state, and recent activity.
```bash
unimem status
```

### `unimem summary`
Processes latest files log entries to update the central state database and outputs a concise markdown project brief for AI agents.
```bash
unimem summary
```

### `unimem task done`
Marks the current task as completed and promotes the next task in the queue.
```bash
unimem task done --next "integrate auth modules"
```

### `unimem shell [install | uninstall]`
Manages shell hooks setup in configuration profile scripts.
```bash
unimem shell install
```

### `unimem doctor`
Runs environment diagnostics verifying path structures, configuration schemas, dependencies, and shell hook bindings.
```bash
unimem doctor
```

### `unimem version`
Prints the active version string.
```bash
unimem version
```

---

## Configuration

Customize Unimem behavior globally using `~/.unimem/config.json`:

```json
{
  "auto_summary": true,
  "auto_sync": true,
  "shell_hooks": true,
  "verbose_logs": false,
  "ai_rule_sync": true
}
```

---

## Security & Privacy
* **No Telemetry**: Unimem is local-first. It does not collect analytics or report crash telemetry.
* **No LLM Queries**: Summaries and mappings are generated using local heuristics and git/file diff parsers. No codebase content is ever sent to third-party APIs.
* **Centralized Storage**: Keeps configuration data out of Git history by resolving files to `~/.unimem` rather than raw repository tracking.
