"""ARIA Router — Classifies queries and selects the optimal model + system prompt."""

import os
import re
import logging
from dataclasses import dataclass
from typing import Optional

from aria.aria_config import get_config

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    domain: str
    model: str
    system_prompt: str
    confidence: float
    reason: str


_prompt_cache: dict = {}


def _load_prompt(domain: str) -> str:
    if domain in _prompt_cache:
        return _prompt_cache[domain]
    config = get_config()
    prompts_dir = config.get("prompts", {}).get("directory", "aria/prompts")
    for ext in (".md", ".txt"):
        path = os.path.join(prompts_dir, f"{domain}{ext}")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    prompt = f.read().strip()
                _prompt_cache[domain] = prompt
                logger.debug(f"Loaded ARIA prompt: {domain} ({len(prompt)} chars)")
                return prompt
            except Exception as e:
                logger.error(f"Failed to load prompt {path}: {e}")
    fallback = f"You are ARIA, a helpful AI assistant specialized in {domain}."
    _prompt_cache[domain] = fallback
    return fallback


def clear_prompt_cache():
    _prompt_cache.clear()
    logger.info("ARIA prompt cache cleared")


def _score_domain(message: str, keywords: list) -> float:
    if not keywords or not message:
        return 0.0
    message_lower = message.lower()
    total_score = 0.0
    max_possible = 0.0
    for keyword in keywords:
        kw_lower = keyword.lower()
        weight = 1.0 + (0.5 * kw_lower.count(" "))
        max_possible += weight
        if " " in kw_lower:
            if kw_lower in message_lower:
                total_score += weight
        else:
            pattern = r"\b" + re.escape(kw_lower) + r"\b"
            if re.search(pattern, message_lower):
                total_score += weight
    if max_possible == 0:
        return 0.0
    raw = total_score / min(max_possible, 5.0)
    return min(raw, 1.0)


def _has_code_patterns(message: str) -> bool:
    code_indicators = [
        r"```",
        r"def\s+\w+\s*\(",
        r"class\s+\w+[:\(]",
        r"import\s+\w+",
        r"from\s+\w+\s+import",
        r"function\s+\w+\s*\(",
        r"const\s+\w+\s*=",
        r"pip install",
        r"npm install",
        r"SELECT\s+.*\s+FROM",
        r"docker\s+(run|build|compose)",
        r"git\s+(commit|push|pull|merge|clone|checkout)",
    ]
    for pattern in code_indicators:
        if re.search(pattern, message, re.IGNORECASE):
            return True
    return False


def route_query(message: str, current_model: str = None) -> RouteDecision:
    config = get_config()
    routing_config = config.get("routing", {})
    if not routing_config.get("enabled", True):
        return RouteDecision(
            domain="general",
            model=current_model or routing_config.get("default_model", "qwen3:8b"),
            system_prompt=_load_prompt("general"),
            confidence=1.0,
            reason="Routing disabled",
        )
    models = routing_config.get("models", {})
    coding_keywords = routing_config.get("coding_keywords", [])
    security_keywords = routing_config.get("security_keywords", [])
    coding_score = _score_domain(message, coding_keywords)
    security_score = _score_domain(message, security_keywords)
    if _has_code_patterns(message):
        coding_score = min(coding_score + 0.3, 1.0)
    threshold = 0.15
    if security_score > coding_score and security_score >= threshold:
        domain = "security"
        model = models.get("security", routing_config.get("default_model"))
        confidence = security_score
        reason = f"Security keywords detected (score: {security_score:.2f})"
    elif coding_score >= threshold:
        domain = "coding"
        model = models.get("coding", routing_config.get("default_model"))
        confidence = coding_score
        reason = f"Coding keywords/patterns detected (score: {coding_score:.2f})"
    else:
        domain = "general"
        model = models.get("general", routing_config.get("default_model"))
        confidence = 1.0 - max(coding_score, security_score)
        reason = "General query"
    system_prompt = _load_prompt(domain)
    decision = RouteDecision(domain=domain, model=model, system_prompt=system_prompt, confidence=confidence, reason=reason)
    logger.info(f"ARIA Router: domain={domain}, model={model}, confidence={confidence:.2f}, reason={reason}")
    return decision


def get_available_domains() -> list:
    config = get_config()
    prompts_dir = config.get("prompts", {}).get("directory", "aria/prompts")
    domains = []
    if os.path.isdir(prompts_dir):
        for f in os.listdir(prompts_dir):
            if f.endswith((".md", ".txt")) and not f.startswith("_"):
                domains.append(f.rsplit(".", 1)[0])
    return sorted(set(domains))
