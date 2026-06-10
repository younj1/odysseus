"""ARIA Integration Hook — Bridges ARIA into the Odysseus chat pipeline."""

import logging
from typing import Optional, Tuple, Dict, Any

from aria.aria_config import get_config, load_config
from aria.router import route_query, RouteDecision
from aria.guardrails import check_input, check_output, audit_interaction

logger = logging.getLogger(__name__)

load_config()


def pre_chat(message: str, user: str = None, session_id: str = None, current_model: str = None) -> Tuple[bool, Optional[str], RouteDecision]:
    input_result = check_input(message, user=user)
    if not input_result.allowed:
        logger.warning(f"ARIA: Input blocked for user={user}: {input_result.reason}")
        return False, input_result.reason, RouteDecision(domain="blocked", model=current_model or "", system_prompt="", confidence=1.0, reason=input_result.reason or "Blocked by guardrail")
    route = route_query(message, current_model=current_model)
    logger.info(f"ARIA pre_chat: user={user}, domain={route.domain}, model={route.model}, confidence={route.confidence:.2f}")
    return True, None, route


def post_chat(message=None, response=None, user=None, session_id=None, route=None) -> Dict[str, Any]:
    output_result = check_output(response or "", user=user)
    audit_interaction(user=user, message=message, response=response, model=route.model if route else None, domain=route.domain if route else None, route_reason=route.reason if route else None, session_id=session_id)
    return {"allowed": output_result.allowed, "warnings": output_result.warnings, "needs_confirmation": output_result.needs_confirmation}


def get_aria_system_prompt(message: str, current_model: str = None) -> Optional[str]:
    config = get_config()
    if not config.get("routing", {}).get("enabled", True):
        return None
    route = route_query(message, current_model=current_model)
    return route.system_prompt


def is_aria_enabled() -> bool:
    try:
        config = get_config()
        return config.get("routing", {}).get("enabled", True)
    except Exception:
        return False
