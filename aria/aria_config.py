"""ARIA Config — Loads and validates aria/config.yaml"""

import os
import logging
import yaml
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config(path: str = None) -> Dict[str, Any]:
    global _config
    if _config is not None and path is None:
        return _config
    config_path = path or _CONFIG_PATH
    if not os.path.exists(config_path):
        logger.warning(f"ARIA config not found at {config_path}, using defaults")
        _config = _default_config()
        return _config
    try:
        with open(config_path, "r") as f:
            _config = yaml.safe_load(f) or {}
        logger.info(f"ARIA config loaded from {config_path}")
    except Exception as e:
        logger.error(f"Failed to load ARIA config: {e}")
        _config = _default_config()
    return _config


def reload_config() -> Dict[str, Any]:
    global _config
    _config = None
    return load_config()


def get_config() -> Dict[str, Any]:
    if _config is None:
        return load_config()
    return _config


def _default_config() -> Dict[str, Any]:
    return {
        "routing": {
            "enabled": True,
            "default_model": "qwen3:8b",
            "models": {
                "general": "qwen3:8b",
                "coding": "qwen2.5-coder:7b",
                "security": "qwen3:8b",
                "lightweight": "nemotron-3-nano:4b",
            },
            "coding_keywords": ["code", "python", "debug", "function", "error", "bug"],
            "security_keywords": ["security", "vulnerability", "exploit", "firewall"],
        },
        "guardrails": {
            "enabled": True,
            "input": {"blocked_patterns": [], "max_message_length": 0},
            "output": {"blocked_patterns": []},
            "require_confirmation": ["rm -rf", "DROP TABLE", "DROP DATABASE"],
            "audit": {
                "enabled": True,
                "log_file": "data/aria_audit.log",
                "log_inputs": True,
                "log_outputs": True,
                "log_model_used": True,
                "log_route_decision": True,
            },
        },
        "prompts": {"directory": "aria/prompts", "default": "general"},
        "obsidian": {"enabled": False},
    }
