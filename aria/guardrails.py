"""ARIA Guardrails — Input/output filtering, command confirmation, and audit logging."""

import os
import re
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from aria.aria_config import get_config

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    allowed: bool
    reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    needs_confirmation: List[str] = field(default_factory=list)


def check_input(message: str, user: str = None) -> GuardrailResult:
    config = get_config()
    guardrails = config.get("guardrails", {})
    if not guardrails.get("enabled", True):
        return GuardrailResult(allowed=True)
    input_rules = guardrails.get("input", {})
    max_length = input_rules.get("max_message_length", 0)
    if max_length > 0 and len(message) > max_length:
        return GuardrailResult(allowed=False, reason=f"Message exceeds maximum length ({len(message)} > {max_length} chars)")
    blocked_patterns = input_rules.get("blocked_patterns", [])
    for pattern in blocked_patterns:
        try:
            if re.search(pattern, message, re.IGNORECASE):
                _audit_log("INPUT_BLOCKED", user=user, message=message[:200], reason=f"Matched blocked pattern: {pattern}")
                return GuardrailResult(allowed=False, reason="Message matched a blocked pattern")
        except re.error as e:
            logger.warning(f"Invalid guardrail regex pattern: {e}")
    return GuardrailResult(allowed=True)


def check_output(response: str, user: str = None) -> GuardrailResult:
    config = get_config()
    guardrails = config.get("guardrails", {})
    if not guardrails.get("enabled", True):
        return GuardrailResult(allowed=True)
    output_rules = guardrails.get("output", {})
    warnings = []
    needs_confirmation = []
    blocked_patterns = output_rules.get("blocked_patterns", [])
    for pattern in blocked_patterns:
        try:
            if re.search(pattern, response, re.IGNORECASE):
                _audit_log("OUTPUT_BLOCKED", user=user, response=response[:200], reason=f"Matched blocked pattern: {pattern}")
                return GuardrailResult(allowed=False, reason="Response matched a blocked pattern")
        except re.error as e:
            logger.warning(f"Invalid guardrail regex pattern: {e}")
    confirm_patterns = guardrails.get("require_confirmation", [])
    for cmd in confirm_patterns:
        if cmd.lower() in response.lower():
            needs_confirmation.append(cmd)
    if needs_confirmation:
        warnings.append(f"Response contains potentially dangerous commands: {', '.join(needs_confirmation)}. Review carefully before executing.")
        _audit_log("DANGEROUS_COMMANDS", user=user, commands=needs_confirmation, response=response[:500])
    return GuardrailResult(allowed=True, warnings=warnings, needs_confirmation=needs_confirmation)


def audit_interaction(user=None, message=None, response=None, model=None, domain=None, route_reason=None, session_id=None):
    config = get_config()
    audit_config = config.get("guardrails", {}).get("audit", {})
    if not audit_config.get("enabled", True):
        return
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "session_id": session_id, "user": user or "unknown"}
    if audit_config.get("log_inputs", True) and message:
        entry["input"] = message[:500]
    if audit_config.get("log_outputs", True) and response:
        entry["output"] = response[:500]
    if audit_config.get("log_model_used", True) and model:
        entry["model"] = model
    if audit_config.get("log_route_decision", True):
        if domain:
            entry["domain"] = domain
        if route_reason:
            entry["route_reason"] = route_reason
    _write_audit_entry(entry)


def _audit_log(event_type: str, **kwargs):
    config = get_config()
    audit_config = config.get("guardrails", {}).get("audit", {})
    if not audit_config.get("enabled", True):
        return
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event_type}
    entry.update({k: v for k, v in kwargs.items() if v is not None})
    _write_audit_entry(entry)


def _write_audit_entry(entry: dict):
    config = get_config()
    log_file = config.get("guardrails", {}).get("audit", {}).get("log_file", "data/aria_audit.log")
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def get_audit_log(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    config = get_config()
    log_file = config.get("guardrails", {}).get("audit", {}).get("log_file", "data/aria_audit.log")
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        entries = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(entries) >= limit + offset:
                break
        return entries[offset:offset + limit]
    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")
        return []
