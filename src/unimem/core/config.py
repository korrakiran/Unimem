"""Configuration system for Unimem v2.0.0."""

import json
from pathlib import Path
from pydantic import BaseModel, Field
from unimem.utils.paths import get_config_path

class Config(BaseModel):
    """Configuration settings for Unimem stored in ~/.unimem/config.json."""
    auto_summary: bool = Field(default=True, description="Automatically run summary on project enter.")
    auto_sync: bool = Field(default=True, description="Automatically sync state on events.")
    shell_hooks: bool = Field(default=True, description="Whether shell hooks are enabled.")
    verbose_logs: bool = Field(default=False, description="Enable verbose logs.")
    ai_rule_sync: bool = Field(default=True, description="Automatically sync AI rules (.cursorrules, etc.) into projects.")

def load_config() -> Config:
    """Load config from ~/.unimem/config.json or return defaults and create the file."""
    config_path = get_config_path()
    if not config_path.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return Config(**data)
    except Exception:
        # Fallback to defaults if corrupted
        return Config()

def save_config(config: Config) -> None:
    """Save config to ~/.unimem/config.json."""
    config_path = get_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    except Exception:
        pass
