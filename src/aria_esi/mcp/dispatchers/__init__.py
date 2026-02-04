"""
MCP Tool Dispatchers Package.

Consolidates ~45 individual MCP tools into 7 domain dispatcher tools
to reduce LLM attention degradation.

Dispatchers:
- universe(): Navigation, routing, borders, activity
- market(): Prices, orders, arbitrage, scopes
- sde(): Item info, blueprints, corporations, agents
- skills(): Training time, easy 80%, activities
- fitting(): Fit statistics calculation
- killmails(): Query and stats for stored killmails
- status(): Unified cache status across domains
"""

from .fitting import register_fitting_dispatcher
from .killmails import register_killmails_dispatcher
from .market import register_market_dispatcher
from .sde import register_sde_dispatcher
from .skills import register_skills_dispatcher
from .status import register_status_tool
from .universe import register_universe_dispatcher

__all__ = [
    "register_universe_dispatcher",
    "register_market_dispatcher",
    "register_sde_dispatcher",
    "register_skills_dispatcher",
    "register_fitting_dispatcher",
    "register_killmails_dispatcher",
    "register_status_tool",
]
