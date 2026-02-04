"""
ARIA ESI Wallet Commands

Financial data: wallet balance, transaction journal.
All commands require authentication.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ..core import (
    REF_TYPE_CATEGORIES,
    REF_TYPE_NAMES,
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
)

# =============================================================================
# Wallet Command
# =============================================================================


def cmd_wallet(args: argparse.Namespace) -> dict:
    """
    Fetch current ISK balance.

    This data is VOLATILE - it changes with every transaction.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Get wallet balance (authenticated)
    try:
        balance = client.get(f"/characters/{char_id}/wallet/", auth=True)
    except ESIError as e:
        return {
            "error": "wallet_error",
            "message": f"Could not fetch wallet: {e.message}",
            "query_timestamp": query_ts,
        }

    return {"query_timestamp": query_ts, "volatility": "volatile", "balance_isk": balance}


# =============================================================================
# Wallet Journal Command
# =============================================================================


def cmd_wallet_journal(args: argparse.Namespace) -> dict:
    """
    Fetch wallet journal and transaction history.

    Provides income/expense breakdown by category.
    """
    query_ts = get_utc_timestamp()
    days = getattr(args, "days", 7)
    filter_type = getattr(args, "filter_type", None)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Calculate date filter
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch wallet journal
    try:
        journal = client.get(f"/characters/{char_id}/wallet/journal/", auth=True)
    except ESIError as e:
        return {
            "error": "api_error",
            "message": f"Failed to fetch wallet journal: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(journal, list):
        journal = []

    # Fetch wallet transactions (market)
    try:
        transactions = client.get(f"/characters/{char_id}/wallet/transactions/", auth=True)
    except ESIError:
        transactions = []

    if not isinstance(transactions, list):
        transactions = []

    # Filter journal by date and optionally by type
    filtered_journal = []
    for entry in journal:
        entry_date = entry.get("date", "")
        if entry_date < cutoff_str:
            continue

        ref_type = entry.get("ref_type", "").lower()

        # Apply type filter if specified
        if filter_type:
            category_types = REF_TYPE_CATEGORIES.get(filter_type.lower(), [])
            if ref_type not in category_types and ref_type != filter_type.lower():
                continue

        filtered_journal.append(entry)

    # Filter transactions by date
    filtered_transactions = []
    for tx in transactions:
        tx_date = tx.get("date", "")
        if tx_date >= cutoff_str:
            filtered_transactions.append(tx)

    # Calculate summary statistics
    total_income = 0.0
    total_expenses = 0.0
    income_breakdown = defaultdict(float)
    expense_breakdown = defaultdict(float)

    for entry in filtered_journal:
        amount = entry.get("amount", 0)
        ref_type = entry.get("ref_type", "unknown")

        if amount > 0:
            total_income += amount
            income_breakdown[ref_type] += amount
        elif amount < 0:
            total_expenses += abs(amount)
            expense_breakdown[ref_type] += abs(amount)

    # Sort breakdowns by amount
    sorted_income = sorted(income_breakdown.items(), key=lambda x: -x[1])
    sorted_expenses = sorted(expense_breakdown.items(), key=lambda x: -x[1])

    # Format income breakdown with friendly names (top 10)
    income_summary = {}
    for ref_type, amount in sorted_income[:10]:
        friendly_name = REF_TYPE_NAMES.get(ref_type, ref_type.replace("_", " ").title())
        income_summary[friendly_name] = round(amount, 2)

    # Format expense breakdown with friendly names (top 10)
    expense_summary = {}
    for ref_type, amount in sorted_expenses[:10]:
        friendly_name = REF_TYPE_NAMES.get(ref_type, ref_type.replace("_", " ").title())
        expense_summary[friendly_name] = round(amount, 2)

    # Prepare recent journal entries (most recent first, max 25)
    recent_journal = []
    sorted_journal = sorted(filtered_journal, key=lambda x: x.get("date", ""), reverse=True)
    for entry in sorted_journal[:25]:
        ref_type = entry.get("ref_type", "unknown")
        recent_journal.append(
            {
                "date": entry.get("date", ""),
                "ref_type": ref_type,
                "ref_type_name": REF_TYPE_NAMES.get(ref_type, ref_type.replace("_", " ").title()),
                "amount": entry.get("amount", 0),
                "balance": entry.get("balance", 0),
                "description": entry.get("description", "")[:100],
                "first_party_id": entry.get("first_party_id"),
                "second_party_id": entry.get("second_party_id"),
            }
        )

    # Prepare recent transactions (max 15)
    recent_transactions = []
    type_cache = {}
    sorted_transactions = sorted(
        filtered_transactions, key=lambda x: x.get("date", ""), reverse=True
    )

    for tx in sorted_transactions[:15]:
        type_id = tx.get("type_id")
        if type_id and type_id not in type_cache:
            type_info = public_client.get_dict_safe(f"/universe/types/{type_id}/")
            type_cache[type_id] = (
                type_info.get("name", f"Type {type_id}") if type_info else f"Type {type_id}"
            )

        recent_transactions.append(
            {
                "date": tx.get("date", ""),
                "type_id": type_id,
                "type_name": type_cache.get(type_id, f"Type {type_id}"),
                "quantity": tx.get("quantity", 0),
                "unit_price": tx.get("unit_price", 0),
                "is_buy": tx.get("is_buy", False),
                "location_id": tx.get("location_id"),
            }
        )

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "period_days": days,
        "filter_type": filter_type if filter_type else None,
        "summary": {
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_change": round(total_income - total_expenses, 2),
            "journal_entries": len(filtered_journal),
            "market_transactions": len(filtered_transactions),
            "income_breakdown": income_summary,
            "expense_breakdown": expense_summary,
        },
        "journal": recent_journal,
        "transactions": recent_transactions,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register wallet command parsers."""

    # Wallet command
    wallet_parser = subparsers.add_parser("wallet", help="Fetch current ISK balance (volatile)")
    wallet_parser.set_defaults(func=cmd_wallet)

    # Wallet journal command
    journal_parser = subparsers.add_parser(
        "wallet-journal", help="Fetch wallet journal and transaction history"
    )
    journal_parser.add_argument(
        "--days", type=int, default=7, help="Number of days to include (default: 7)"
    )
    journal_parser.add_argument(
        "--type",
        dest="filter_type",
        choices=[
            "bounty",
            "market",
            "industry",
            "tax",
            "transfer",
            "contract",
            "mission",
            "insurance",
        ],
        help="Filter by transaction type",
    )
    journal_parser.set_defaults(func=cmd_wallet_journal)
