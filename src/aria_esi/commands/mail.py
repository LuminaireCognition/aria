"""
ARIA ESI Mail Commands

Read EVE mail headers and bodies.
All commands require authentication.
"""

import argparse
import re
from datetime import datetime, timezone

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
    parse_datetime,
)


def _strip_html(text: str) -> str:
    """Strip HTML tags from text."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    clean = clean.replace("&nbsp;", " ")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    return clean.strip()


# Recipient type display mapping
RECIPIENT_TYPES = {
    "character": "Character",
    "corporation": "Corporation",
    "alliance": "Alliance",
    "mailing_list": "Mailing List",
}


# =============================================================================
# Mail List Command
# =============================================================================


def cmd_mail(args: argparse.Namespace) -> dict:
    """
    List mail headers.

    Shows most recent mail with optional unread filter.
    """
    query_ts = get_utc_timestamp()
    unread_only = getattr(args, "unread", False)
    limit = getattr(args, "limit", 50)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-mail.read_mail.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-mail.read_mail.v1",
            "action": "Re-run OAuth setup to authorize mail access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch mail headers
    try:
        mail_data = client.get_list(f"/characters/{char_id}/mail/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch mail: {e.message}",
            "hint": "Ensure esi-mail.read_mail.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    # Empty check
    if not mail_data:
        return {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "character_id": char_id,
            "summary": {"total_shown": 0, "unread_count": 0},
            "mail": [],
            "message": "No mail found",
        }

    # Collect sender IDs for resolution
    sender_ids = set()
    for mail in mail_data:
        if isinstance(mail, dict):
            sender_ids.add(mail.get("from", 0))

    # Resolve sender names
    sender_names = {}
    for sid in sender_ids:
        if sid:
            # Could be character, corp, or alliance
            char_info = public_client.get_dict_safe(f"/characters/{sid}/")
            if char_info and "name" in char_info:
                sender_names[sid] = char_info["name"]
            else:
                # Try corporation
                corp_info = public_client.get_dict_safe(f"/corporations/{sid}/")
                if corp_info and "name" in corp_info:
                    sender_names[sid] = corp_info["name"]
                else:
                    sender_names[sid] = f"Unknown-{sid}"

    # Process mail
    processed_mail = []
    unread_count = 0

    for mail in mail_data:
        is_read = mail.get("is_read", True)

        # Apply unread filter
        if unread_only and is_read:
            continue

        if not is_read:
            unread_count += 1

        from_id = mail.get("from", 0)

        processed_item = {
            "mail_id": mail.get("mail_id"),
            "from_id": from_id,
            "from_name": sender_names.get(from_id, f"Unknown-{from_id}"),
            "subject": mail.get("subject", "(No Subject)"),
            "timestamp": mail.get("timestamp"),
            "is_read": is_read,
            "labels": mail.get("labels", []),
            "recipients": mail.get("recipients", []),
        }

        processed_mail.append(processed_item)

        if len(processed_mail) >= limit:
            break

    # Sort: unread first, then by timestamp descending
    processed_mail.sort(key=lambda m: (m["is_read"], m["timestamp"] or ""), reverse=True)
    # Re-reverse to get unread first (is_read=False should come first)
    processed_mail.sort(
        key=lambda m: (
            m["is_read"],
            -(
                parse_datetime(m["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc)
            ).timestamp()
            if m["timestamp"]
            else 0,
        )
    )

    return {
        "query_timestamp": query_ts,
        "volatility": "volatile",
        "character_id": char_id,
        "summary": {"total_shown": len(processed_mail), "unread_count": unread_count},
        "mail": processed_mail,
        "filters": {"unread_only": unread_only, "limit": limit},
    }


# =============================================================================
# Mail Read Command
# =============================================================================


def cmd_mail_read(args: argparse.Namespace) -> dict:
    """
    Read a specific mail body.
    """
    query_ts = get_utc_timestamp()
    mail_id = getattr(args, "mail_id", None)

    if not mail_id:
        return {
            "error": "missing_argument",
            "message": "Mail ID is required",
            "usage": "python3 -m aria_esi mail-read <mail_id>",
            "query_timestamp": query_ts,
        }

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-mail.read_mail.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-mail.read_mail.v1",
            "action": "Re-run OAuth setup to authorize mail access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch mail body
    try:
        mail_data = client.get_dict(f"/characters/{char_id}/mail/{mail_id}/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch mail {mail_id}: {e.message}",
            "hint": "Check that the mail ID is correct",
            "query_timestamp": query_ts,
        }

    if not mail_data:
        return {
            "error": "not_found",
            "message": f"Mail ID {mail_id} not found",
            "hint": "Use `mail` to list available mail IDs",
            "query_timestamp": query_ts,
        }

    # Resolve sender name
    from_id = mail_data.get("from", 0)
    from_name = f"Unknown-{from_id}"
    if from_id:
        char_info = public_client.get_dict_safe(f"/characters/{from_id}/")
        if char_info and "name" in char_info:
            from_name = char_info["name"]
        else:
            corp_info = public_client.get_dict_safe(f"/corporations/{from_id}/")
            if corp_info and "name" in corp_info:
                from_name = corp_info["name"]

    # Clean up body (strip HTML)
    body = _strip_html(mail_data.get("body", ""))

    return {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "mail": {
            "mail_id": mail_id,
            "from_id": from_id,
            "from_name": from_name,
            "subject": mail_data.get("subject", "(No Subject)"),
            "timestamp": mail_data.get("timestamp"),
            "body": body,
            "labels": mail_data.get("labels", []),
            "recipients": mail_data.get("recipients", []),
        },
    }


# =============================================================================
# Mail Labels Command
# =============================================================================


def cmd_mail_labels(args: argparse.Namespace) -> dict:
    """
    List mail labels.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-mail.read_mail.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-mail.read_mail.v1",
            "action": "Re-run OAuth setup to authorize mail access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    # Fetch labels
    try:
        labels_data = client.get_dict(f"/characters/{char_id}/mail/labels/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch mail labels: {e.message}",
            "query_timestamp": query_ts,
        }

    labels = labels_data.get("labels", []) if labels_data else []
    total_unread = labels_data.get("total_unread_count", 0) if labels_data else 0

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character_id": char_id,
        "total_unread_count": total_unread,
        "labels": [
            {
                "label_id": label.get("label_id"),
                "name": label.get("name", "Unnamed"),
                "color": label.get("color"),
                "unread_count": label.get("unread_count", 0),
            }
            for label in labels
        ],
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register mail command parsers."""

    # Mail list command
    list_parser = subparsers.add_parser("mail", help="List EVE mail headers")
    list_parser.add_argument("--unread", action="store_true", help="Show only unread mail")
    list_parser.add_argument(
        "--limit", "-n", type=int, default=50, help="Limit number of results (default: 50)"
    )
    list_parser.set_defaults(func=cmd_mail)

    # Mail read command
    read_parser = subparsers.add_parser("mail-read", help="Read a specific mail")
    read_parser.add_argument("mail_id", type=int, help="Mail ID to read")
    read_parser.set_defaults(func=cmd_mail_read)

    # Mail labels command
    labels_parser = subparsers.add_parser("mail-labels", help="List mail labels")
    labels_parser.set_defaults(func=cmd_mail_labels)
