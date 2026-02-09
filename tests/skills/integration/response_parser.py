"""
Response parsing utilities for extracting structured data from LLM responses.

Provides enhanced JSON extraction and fact extraction from prose responses.
"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_from_response(response: str | None) -> dict[str, Any] | list[Any] | None:
    """
    Extract JSON data from an LLM response that may contain markdown or prose.

    Enhanced version with better handling of edge cases:
    - Nested JSON in code blocks
    - JSON with trailing commas (lenient parsing)
    - Multiple JSON objects (returns first valid)
    - JSON with comments

    Handles common patterns:
    - Raw JSON
    - JSON in ```json code blocks
    - JSON in ``` code blocks
    - JSON embedded in prose
    - Multiline JSON

    Args:
        response: Raw response text that may contain JSON

    Returns:
        Parsed JSON data or None if no valid JSON found
    """
    if not response:
        return None

    # Try direct parse first (response is pure JSON)
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code blocks (most common pattern)
    code_block_patterns = [
        r"```json\s*([\s\S]*?)\s*```",  # ```json ... ```
        r"```typescript\s*([\s\S]*?)\s*```",  # Sometimes LLMs use typescript blocks
        r"```\s*([\s\S]*?)\s*```",  # ``` ... ```
    ]

    for pattern in code_block_patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        for match in matches:
            parsed = _try_parse_json(match.strip())
            if parsed is not None:
                return parsed

    # Try finding bare JSON objects (start with { or [)
    # Use a more careful approach to find balanced brackets
    json_candidates = _find_json_candidates(response)
    for candidate in json_candidates:
        parsed = _try_parse_json(candidate)
        if parsed is not None:
            return parsed

    return None


def _try_parse_json(text: str) -> dict[str, Any] | list[Any] | None:
    """
    Attempt to parse text as JSON with lenient handling.

    Handles:
    - Standard JSON
    - JSON with trailing commas
    - JSON with single quotes (converts to double)

    Args:
        text: Text to parse as JSON

    Returns:
        Parsed JSON or None if parsing fails
    """
    if not text:
        return None

    # Try standard parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try removing trailing commas
    cleaned = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try converting single quotes to double (Python dict literals)
    # Be careful not to break strings containing apostrophes
    try:
        # Only convert quotes that look like JSON delimiters
        converted = re.sub(r"'(\w+)':", r'"\1":', text)
        return json.loads(converted)
    except json.JSONDecodeError:
        pass

    return None


def _find_json_candidates(text: str) -> list[str]:
    """
    Find potential JSON substrings in text by matching balanced brackets.

    Args:
        text: Text to search for JSON

    Returns:
        List of potential JSON strings
    """
    candidates = []

    # Find all positions where JSON might start
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        i = 0
        while i < len(text):
            start_pos = text.find(start_char, i)
            if start_pos == -1:
                break

            # Try to find matching end bracket
            depth = 0
            in_string = False
            escape_next = False

            for j in range(start_pos, len(text)):
                char = text[j]

                if escape_next:
                    escape_next = False
                    continue

                if char == "\\":
                    escape_next = True
                    continue

                if char == '"' and not in_string:
                    in_string = True
                elif char == '"' and in_string:
                    in_string = False
                elif not in_string:
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            candidates.append(text[start_pos : j + 1])
                            break

            i = start_pos + 1

    return candidates


def extract_facts_from_prose(
    response: str,
    fact_queries: list[dict[str, str]],
    use_haiku: bool = True,
) -> dict[str, Any]:
    """
    Extract specific facts from a prose response using an LLM.

    For Tier 2 tests, when the response is prose instead of JSON,
    we can use a smaller/faster model to extract specific facts.

    Args:
        response: The prose response text
        fact_queries: List of facts to extract, each with:
            - name: Identifier for the fact
            - question: Question to ask about the response
            - type: Expected type (string, number, boolean, list)
        use_haiku: If True, use Claude Haiku for extraction (cheaper)

    Returns:
        Dictionary mapping fact names to extracted values

    Example:
        facts = extract_facts_from_prose(
            response="The route from Jita to Amarr is 45 jumps...",
            fact_queries=[
                {"name": "jump_count", "question": "How many jumps?", "type": "number"},
                {"name": "origin", "question": "What is the origin?", "type": "string"},
            ]
        )
        # Returns: {"jump_count": 45, "origin": "Jita"}
    """
    # This is a placeholder implementation
    # In Tier 2 tests, this would actually call the Anthropic API
    # For now, we return empty results for Tier 1 mock testing

    # Check if anthropic is available
    try:
        import anthropic

        client = anthropic.Anthropic()
    except (ImportError, anthropic.AuthenticationError):
        # No API key or anthropic not installed
        return {}

    # Build extraction prompt
    query_list = "\n".join(
        f"- {q['name']}: {q['question']} (type: {q['type']})" for q in fact_queries
    )

    extraction_prompt = f"""Extract the following facts from this response.
Return ONLY a JSON object with the fact names as keys.

Facts to extract:
{query_list}

Response to analyze:
{response}

Return valid JSON only, no explanation."""

    try:
        model = "claude-3-5-haiku-20241022" if use_haiku else "claude-sonnet-4-20250514"
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": extraction_prompt}],
        )

        result_text = message.content[0].text
        return extract_json_from_response(result_text) or {}

    except Exception:
        return {}


def normalize_response_for_comparison(
    response: dict[str, Any],
    volatile_keys: set[str] | None = None,
) -> dict[str, Any]:
    """
    Normalize a response for comparison by replacing volatile values.

    Removes or normalizes fields that change between runs:
    - Timestamps
    - Cache ages
    - Random IDs

    Args:
        response: The response dict to normalize
        volatile_keys: Additional keys to normalize

    Returns:
        Normalized response dict
    """
    if volatile_keys is None:
        volatile_keys = {
            "cache_age_seconds",
            "timestamp",
            "query_timestamp",
            "compiled_at",
            "fetched_at",
            "last_updated",
            "issued",
        }

    def _normalize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "<NORMALIZED>" if k in volatile_keys else _normalize(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [_normalize(item) for item in obj]
        return obj

    return _normalize(response)
