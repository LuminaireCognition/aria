"""
Routes Signal for Interest Engine v2.

Scores kills on configured travel routes.

Prefetch capable: NO (requires route membership check with full kill context)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider

if TYPE_CHECKING:
    from ...models import ProcessedKill


class RouteSignal(BaseSignalProvider):
    """
    Named travel route scoring signal.

    Scores kills occurring on configured travel routes with optional ship filtering.

    Config:
        routes: List of route definitions
                [{"name": str, "systems": [int], "score": float, "ship_filter": [str]}]

    Prefetch capable: NO (ship type filtering requires ESI)
    """

    _name = "routes"
    _category = "routes"
    _prefetch_capable = False

    # Built-in ship category mappings
    SHIP_CATEGORIES = {
        "freighter": {34328, 20183, 20187, 20185, 20189},  # Freighter type IDs
        "jump_freighter": {28844, 28846, 28848, 28850},  # JF type IDs
        "dst": {12753, 12729, 12733, 12743},  # DST type IDs
        "blockade_runner": {12731, 12735, 12745, 12747},  # BR type IDs
        "industrial": {},  # Too many to list, use group ID check
        "orca": {28606},
        "bowhead": {34328},
    }

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on route membership."""
        routes = config.get("routes", [])

        if not routes:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No routes configured",
                prefetch_capable=False,
            )

        # Build system -> routes lookup
        system_routes = {}
        for route in routes:
            systems = route.get("systems", [])
            for sys_id in systems:
                if sys_id not in system_routes:
                    system_routes[sys_id] = []
                system_routes[sys_id].append(route)

        if system_id not in system_routes:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="System not on any route",
                prefetch_capable=False,
            )

        # System is on at least one route
        matched_routes = system_routes[system_id]
        best_score = 0.0
        best_route = None

        for route in matched_routes:
            route_name = route.get("name", "Unnamed")
            route_score = route.get("score", 0.9)
            ship_filter = route.get("ship_filter", [])

            # Check ship filter if specified
            if ship_filter and kill:
                if not self._matches_ship_filter(kill.victim_ship_type_id, ship_filter):
                    continue

            if route_score > best_score:
                best_score = route_score
                best_route = route_name

        if best_score == 0:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="Ship type not in route filter",
                prefetch_capable=False,
            )

        return SignalScore(
            signal=self._name,
            score=best_score,
            reason=f"On route: {best_route}",
            prefetch_capable=False,
            raw_value={"route": best_route},
        )

    def _matches_ship_filter(
        self,
        ship_type_id: int | None,
        ship_filter: list[str],
    ) -> bool:
        """Check if ship type matches filter categories."""
        if ship_type_id is None:
            return False

        for category in ship_filter:
            category = category.lower().replace(" ", "_")
            type_ids = self.SHIP_CATEGORIES.get(category, set())

            if ship_type_id in type_ids:
                return True

        return False

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate routes signal config."""
        errors = []
        routes = config.get("routes", [])

        if not routes:
            errors.append("At least one route must be configured")
            return errors

        for i, route in enumerate(routes):
            if not isinstance(route, dict):
                errors.append(f"routes[{i}] must be a dictionary")
                continue

            if "systems" not in route or not route["systems"]:
                errors.append(f"routes[{i}] must have 'systems' list")

            if "score" in route:
                score = route["score"]
                if not isinstance(score, (int, float)) or not (0 <= score <= 1):
                    errors.append(f"routes[{i}].score must be between 0 and 1")

        return errors
