# Unimem v2 — Universal Project Memory Layer for AI Coding Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform Support](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](#-installation-guide)
[![Homebrew Formula](https://img.shields.io/badge/Homebrew-Formula-orange.svg)](https://github.com/korrakiran/unimem/blob/main/Formula/unimem.rb)
[![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)](https://github.com/korrakiran/unimem/releases)

**Unimem** is a universal, persistent project memory and handoff layer designed for AI coding agents (such as Claude Code, Gemini CLI, Cursor, Aider, Windsurf, Cline, and GitHub Copilot). It maintains project memory and auto-injects context into supported AI tools so you can switch tools mid-project without losing momentum.

Version 2.0.0 is a complete rewrite featuring a clean, modular architecture, global configuration, and centralized per-project memory persistence.

---

## Why Unimem?

When developing with AI agents:
* **Token limits / context exhaustion** force you to restart sessions, losing context.
* **Tool switching** (e.g. from Claude Code to Aider) requires writing long prompts explaining what was done.
* **No persistent memory** means fresh agents lack awareness of project goals, tech stack, or coding preferences.

**Unimem** solves this by maintaining a persistent project brain. Incoming agents read `memory.md` to instantly learn the project state, and outgoing agents write their progress automatically.

---

## v2.0.0 Architecture & Features

```
unimem/
├── bin/            # Executable helper scripts
├── src/            # Modular python package
│   ├── core/       # Configuration, git/file collection, adapters, summarizer
│   ├── hooks/      # Idempotent shell hooks (zsh, bash, fish)
│   ├── memory/     # Managers, schemas, migrations, snapshots
│   ├── cli/        # Typer entry point and subcommands
│   └── utils/      # Path resolution, timestamps, logging
├── Formula/        # Homebrew formula
├── README.md       # Documentation
└── pyproject.toml  # Package configuration
```

### Key Improvements in v2.0.0:
* **Global Memory Hub**: Memory is centralized under `~/.unimem/projects/<project-id>/` to keep project roots clean, using lightweight local `.unimem` pointer symlinks for agent visibility.
* **Global Configuration**: Customize behavior in `~/.unimem/config.json`.
* **Idempotent Shell Hooks**: Inbuilt command (`unimem shell install`) safely adds hooks to `.zshrc`, `.bashrc`, and `.config/fish/config.fish` with automatic background silent mode (`nomonitor`) preventing annoying shell output.
* **Clean Project Detection**: Automatically detects projects using git roots, `package.json`, `pyproject.toml`, `Cargo.toml`, or `go.mod` on directory entrance.
* **Rule Merging Engine**: Detects rule templates in your home directory, merges them with project-specific rules, and injects Unimem defaults.

---

## Installation Guide

### macOS / Linux

#### Option 1: Via Homebrew (Recommended)
```bash
brew tap korrakiran/unimem
brew install unimem
unimem shell install
source ~/.zshrc
```

#### Option 2: Via pipx
```bash
pipx install unimem
unimem shell install
```

### Windows (pipx)
```bash
pip install --user pipx
pipx install unimem
```

---

## Commands Reference

### `unimem init`
Initialize Unimem memory tracking in the current directory.
```bash
unimem init --name "My Project" --desc "An awesome app"
```

### `unimem summary`
Rebuild the project state from event logs and print a concise, agent-formatted summary of what changed, important files, architecture, risks, and recommendations.
```bash
unimem summary
```

### `unimem status`
Show the project name, tech stack, current goal, current task, git status, and recent events.
```bash
unimem status
```

### `unimem sync`
Run auto-detection and trigger memory synchronization (used automatically by background shell hooks).
```bash
unimem sync
```

### `unimem task done`
Complete the current task and promote the next planned task to current.
```bash
unimem task done --next "implement new feature"
```

### `unimem doctor`
Run diagnostic health checks on your configuration, database files, and shell hooks.
```bash
unimem doctor
```

### `unimem version`
Print current version.
```bash
unimem version
```

---

## Global Configuration (`~/.unimem/config.json`)

Configure options globally:
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

## Troubleshooting

### Background job outputs when executing `cd`
If your terminal prints job numbers (e.g. `[1] 12345` or `done unimem summary`) when changing directories, make sure you run `unimem shell install` to install the updated v2 shell hooks, which use `setopt localoptions nomonitor` to run silent background tasks.
