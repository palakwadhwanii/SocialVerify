import re
from typing import Any
from urllib.parse import urlparse
from pydantic import ValidationError
from schemas.report import SocialVerifyReport
from utils.logger import logger

# Prompt Injection detection patterns
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|guidelines?|prompts?)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|guidelines?|prompts?)", re.IGNORECASE),
    re.compile(r"\b(system\s+prompt|developer\s+mode|jailbreak|DAN|unrestricted\s+AI)\b", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(hidden|internal|system).*(prompt|instructions?|keys?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+an?\s+(unrestricted|DAN|jailbroken)", re.IGNORECASE),
    re.compile(r"bypass\s+(all\s+)?(security|safety|content)\s+filters?", re.IGNORECASE),
    re.compile(r"<\s*script\s*>", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
]

# Prohibited / Abusive content patterns
ABUSE_PATTERNS = [
    re.compile(r"\b(how\s+to\s+make\s+a\s+bomb|synthesize\s+nerve\s+agent)\b", re.IGNORECASE),
    re.compile(r"\b(child\s+exploitation|terrorist\s+recruitment)\b", re.IGNORECASE),
]

ALLOWED_TOOLS = {
    "search_news",
    "search_social_posts",
    "web_search",
    "lookup_evidence_db",
    "retrieve_source_context",
    "google_fact_check_search",
    "adk_evidence_analysis",
}


class InputGuardrail:
    """Security filter to inspect, sanitize, and validate incoming user queries."""

    @staticmethod
    def validate_query(query: str) -> tuple[bool, str]:
        if not query or not query.strip():
            return False, "Query cannot be empty."

        cleaned = query.strip()
        if len(cleaned) < 3:
            return False, "Query must be at least 3 characters long."
        if len(cleaned) > 2000:
            return False, "Query exceeds maximum allowed length of 2000 characters."

        # Check for prompt injection
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(cleaned):
                logger.warning(f"Guardrail blocked prompt injection attempt: {pattern.pattern}")
                return False, "Security rejection: Potentially adversarial prompt injection detected."

        # Check for harmful/abusive instructions
        for pattern in ABUSE_PATTERNS:
            if pattern.search(cleaned):
                logger.warning(f"Guardrail blocked abusive query: {pattern.pattern}")
                return False, "Security rejection: Request violates acceptable use policies."

        return True, "Query passed all security checks."

    @staticmethod
    def check_for_prompt_injection(text: str) -> tuple[bool, str]:
        """Inspect untrusted text (e.g. retrieved social posts) for prompt injection patterns."""
        if not text:
            return True, ""
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                return False, f"Prompt injection pattern detected: {pattern.pattern}"
        return True, ""


class ToolGuardrail:
    """Ensures agent tool execution is strictly restricted and bounded."""

    @staticmethod
    def validate_tool_call(tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name not in ALLOWED_TOOLS:
            logger.error(f"Unauthorized tool execution attempt: {tool_name}")
            return False, f"Tool '{tool_name}' is not in the allowed tool registry."

        # Bounded limits check
        if "page_size" in arguments:
            if not (1 <= int(arguments["page_size"]) <= 20):
                return False, "page_size must be between 1 and 20."
        if "limit" in arguments:
            if not (1 <= int(arguments["limit"]) <= 25):
                return False, "limit must be between 1 and 25."

        return True, "Tool call validated."


class OutputGuardrail:
    """Validates structured model outputs, URLs, and citation integrity."""

    @staticmethod
    def validate_report(report_data: dict[str, Any], retrieved_urls: set[str]) -> tuple[bool, SocialVerifyReport | None, list[str]]:
        errors: list[str] = []

        try:
            report = SocialVerifyReport.model_validate(report_data)
        except ValidationError as e:
            errors.append(f"Pydantic schema validation error: {e}")
            return False, None, errors

        # Citation membership verification: Ensure all cited URLs match retrieved evidence
        for idx, claim in enumerate(report.claim_assessments):
            for cite in claim.supporting_evidence:
                if (cite.startswith("http://") or cite.startswith("https://")) and cite not in retrieved_urls:
                    errors.append(f"Claim {idx} cites unretrieved URL: {cite}")
            for cite in claim.counter_evidence:
                if (cite.startswith("http://") or cite.startswith("https://")) and cite not in retrieved_urls:
                    errors.append(f"Claim {idx} counter-cites unretrieved URL: {cite}")

        for source in report.evidence_sources:
            url_str = str(source.url)
            parsed = urlparse(url_str)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"Invalid evidence URL: {url_str}")

        if errors:
            logger.warning(f"Output guardrail detected validation warnings: {errors}")

        # The report is valid if it adheres to the Pydantic model
        return True, report, errors
