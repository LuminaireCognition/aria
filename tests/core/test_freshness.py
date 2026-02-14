"""
Tests for ARIA Freshness-Gated Auto-Sync Library.

Covers: parse_sync_marker, SyncResult, check_freshness, is_esi_available,
ensure_fresh, and cmd_ensure_fresh.
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.core.freshness import (
    SECTION_REGISTRY,
    SyncResult,
    check_freshness,
    ensure_fresh,
    is_esi_available,
    parse_sync_marker,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pilot_dir(tmp_path: Path) -> Path:
    """Create a minimal pilot directory."""
    d = tmp_path / "12345_TestPilot"
    d.mkdir()
    return d


def _make_marker(pattern: str, synced_at: datetime) -> str:
    """Build an enhanced ESI-SYNC marker line."""
    ts = synced_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (synced_at + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"<!-- {pattern} ttl_hours=24 synced_at={ts} stale_after={stale} -->"


def _make_profile(pilot_dir: Path, synced_at: datetime) -> Path:
    """Write a profile.md with 3 standings markers at the given timestamp."""
    markers = [
        "ESI-SYNC:STANDINGS-EMPIRE:START",
        "ESI-SYNC:STANDINGS-CORPS:START",
        "ESI-SYNC:STANDINGS-PIRATES:START",
    ]
    lines = ["# Test Profile\n"]
    for m in markers:
        lines.append(_make_marker(m, synced_at))
        lines.append(f"| Test | 1.0 | Aligned |")
        lines.append(f"*Synced: {synced_at.strftime('%Y-%m-%d %H:%M')} UTC*\n")
    profile = pilot_dir / "profile.md"
    profile.write_text("\n".join(lines))
    return profile


@pytest.fixture
def fresh_profile(pilot_dir: Path) -> Path:
    """Profile with markers timestamped now (fresh)."""
    return _make_profile(pilot_dir, datetime.now(UTC))


@pytest.fixture
def stale_profile(pilot_dir: Path) -> Path:
    """Profile with markers timestamped 48h ago (stale)."""
    return _make_profile(pilot_dir, datetime.now(UTC) - timedelta(hours=48))


def _make_skills_json(pilot_dir: Path, synced_at: datetime) -> Path:
    """Write a skills.json with _meta.synced_at at given timestamp."""
    data = {
        "_meta": {
            "synced_at": synced_at.isoformat(),
            "character_id": 12345,
            "total_skills": 10,
        },
        "skills": {"3436": 5, "33699": 4},
    }
    path = pilot_dir / "skills.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def fresh_skills_json(pilot_dir: Path) -> Path:
    """Skills JSON with timestamp now (fresh)."""
    return _make_skills_json(pilot_dir, datetime.now(UTC))


@pytest.fixture
def stale_skills_json(pilot_dir: Path) -> Path:
    """Skills JSON with timestamp 24h ago (stale)."""
    return _make_skills_json(pilot_dir, datetime.now(UTC) - timedelta(hours=24))


# =============================================================================
# TestParseSyncMarker
# =============================================================================


class TestParseSyncMarker:
    """Tests for parse_sync_marker()."""

    def test_enhanced_marker(self) -> None:
        content = "<!-- ESI-SYNC:STANDINGS-EMPIRE:START ttl_hours=24 synced_at=2026-01-25T04:59:00Z stale_after=2026-01-26T04:59:00Z -->"
        result = parse_sync_marker(content, "ESI-SYNC:STANDINGS-EMPIRE:START")
        assert result is not None
        assert result["format"] == "enhanced"
        assert result["synced_at"] == "2026-01-25T04:59:00Z"
        assert result["ttl_hours"] == 24.0

    def test_legacy_marker_with_timestamp(self) -> None:
        content = (
            "<!-- ESI-SYNC:STANDINGS-EMPIRE:START -->\n"
            "| Caldari State | 1.50 | Aligned |\n"
            "*Synced: 2026-01-25 04:59 UTC*\n"
        )
        result = parse_sync_marker(content, "ESI-SYNC:STANDINGS-EMPIRE:START")
        assert result is not None
        assert result["format"] == "legacy"
        assert "2026-01-25" in result["synced_at"]

    def test_missing_marker(self) -> None:
        content = "# Just a regular markdown file"
        result = parse_sync_marker(content, "ESI-SYNC:STANDINGS-EMPIRE:START")
        assert result is None

    def test_legacy_marker_without_timestamp(self) -> None:
        content = "<!-- ESI-SYNC:STANDINGS-EMPIRE:START -->\n| No timestamp here |"
        result = parse_sync_marker(content, "ESI-SYNC:STANDINGS-EMPIRE:START")
        assert result is None


# =============================================================================
# TestSyncResult
# =============================================================================


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_frozen(self) -> None:
        result = SyncResult(
            section="standings",
            fresh=True,
            synced_at="2026-01-25T04:59:00+00:00",
            age_hours=1.5,
            ttl_hours=24,
            refreshed=False,
            esi_available=None,
            error=None,
            source="marker",
        )
        with pytest.raises(AttributeError):
            result.fresh = False  # type: ignore[misc]

    def test_to_dict_all_fields(self) -> None:
        result = SyncResult(
            section="skills",
            fresh=False,
            synced_at=None,
            age_hours=None,
            ttl_hours=12,
            refreshed=False,
            esi_available=None,
            error=None,
            source="missing",
        )
        d = result.to_dict()
        assert set(d.keys()) == {
            "section",
            "fresh",
            "synced_at",
            "age_hours",
            "ttl_hours",
            "refreshed",
            "esi_available",
            "error",
            "source",
        }
        # None values preserved
        assert d["synced_at"] is None
        assert d["age_hours"] is None
        assert d["error"] is None

    def test_default_values(self) -> None:
        result = SyncResult(
            section="test",
            fresh=True,
            synced_at="2026-01-25T00:00:00+00:00",
            age_hours=0.5,
            ttl_hours=24,
            refreshed=False,
            esi_available=None,
            error=None,
            source="marker",
        )
        assert result.refreshed is False
        assert result.esi_available is None
        assert result.error is None


# =============================================================================
# TestCheckFreshness
# =============================================================================


class TestCheckFreshness:
    """Tests for check_freshness()."""

    def test_fresh_standings(self, pilot_dir: Path, fresh_profile: Path) -> None:
        result = check_freshness("standings", pilot_dir)
        assert result.fresh is True
        assert result.section == "standings"
        assert result.source == "marker"
        assert result.synced_at is not None
        assert result.age_hours is not None
        assert result.age_hours < 24

    def test_stale_standings(self, pilot_dir: Path, stale_profile: Path) -> None:
        result = check_freshness("standings", pilot_dir)
        assert result.fresh is False
        assert result.age_hours is not None
        assert result.age_hours > 24

    def test_missing_profile(self, pilot_dir: Path) -> None:
        result = check_freshness("standings", pilot_dir)
        assert result.fresh is False
        assert result.source == "missing"

    def test_no_pilot_dir(self) -> None:
        with patch("aria_esi.core.freshness._resolve_pilot_dir", return_value=None):
            result = check_freshness("standings")
        assert result.fresh is False
        assert result.source == "error"
        assert "pilot directory" in result.error.lower()

    def test_fresh_skills(self, pilot_dir: Path, fresh_skills_json: Path) -> None:
        result = check_freshness("skills", pilot_dir)
        assert result.fresh is True
        assert result.section == "skills"
        assert result.source == "json_meta"

    def test_stale_skills(self, pilot_dir: Path, stale_skills_json: Path) -> None:
        result = check_freshness("skills", pilot_dir)
        assert result.fresh is False
        assert result.source == "json_meta"

    def test_invalid_section(self, pilot_dir: Path) -> None:
        with pytest.raises(KeyError):
            check_freshness("nonexistent_section", pilot_dir)

    def test_composite_oldest_marker_determines_freshness(self, pilot_dir: Path) -> None:
        """Two fresh markers + one stale marker = stale overall."""
        now = datetime.now(UTC)
        stale = now - timedelta(hours=48)
        markers = {
            "ESI-SYNC:STANDINGS-EMPIRE:START": now,
            "ESI-SYNC:STANDINGS-CORPS:START": now,
            "ESI-SYNC:STANDINGS-PIRATES:START": stale,  # This one is old
        }
        lines = ["# Test Profile\n"]
        for m, ts in markers.items():
            lines.append(_make_marker(m, ts))
            lines.append(f"| Test | 1.0 | Aligned |")
            lines.append(f"*Synced: {ts.strftime('%Y-%m-%d %H:%M')} UTC*\n")
        (pilot_dir / "profile.md").write_text("\n".join(lines))

        result = check_freshness("standings", pilot_dir)
        assert result.fresh is False
        assert result.age_hours is not None
        assert result.age_hours > 24

    def test_missing_one_of_three_markers(self, pilot_dir: Path) -> None:
        """Profile with only 2 of 3 markers = missing."""
        now = datetime.now(UTC)
        markers = [
            "ESI-SYNC:STANDINGS-EMPIRE:START",
            "ESI-SYNC:STANDINGS-CORPS:START",
            # Missing PIRATES marker
        ]
        lines = ["# Test Profile\n"]
        for m in markers:
            lines.append(_make_marker(m, now))
            lines.append(f"| Test | 1.0 | Aligned |\n")
        (pilot_dir / "profile.md").write_text("\n".join(lines))

        result = check_freshness("standings", pilot_dir)
        assert result.fresh is False
        assert result.source == "missing"


# =============================================================================
# TestIsEsiAvailable
# =============================================================================


class TestIsEsiAvailable:
    """Tests for is_esi_available()."""

    def test_auth_succeeds(self) -> None:
        mock_client = MagicMock()
        mock_creds = MagicMock()
        with patch(
            "aria_esi.core.auth.get_authenticated_client",
            return_value=(mock_client, mock_creds),
        ):
            assert is_esi_available(timeout=5.0) is True

    def test_credentials_error(self) -> None:
        from aria_esi.core.auth import CredentialsError

        with patch(
            "aria_esi.core.auth.get_authenticated_client",
            side_effect=CredentialsError("No credentials"),
        ):
            assert is_esi_available(timeout=5.0) is False

    def test_timeout(self) -> None:
        import time

        def slow_auth() -> None:
            time.sleep(10)

        with patch(
            "aria_esi.core.auth.get_authenticated_client",
            side_effect=slow_auth,
        ):
            assert is_esi_available(timeout=0.1) is False


# =============================================================================
# TestEnsureFresh
# =============================================================================


class TestEnsureFresh:
    """Tests for ensure_fresh()."""

    def test_fresh_returns_immediately(self, pilot_dir: Path, fresh_profile: Path) -> None:
        """Fresh data → no ESI probe, no sync."""
        with patch("aria_esi.core.freshness.is_esi_available") as mock_esi:
            result = ensure_fresh("standings", pilot_dir)
        assert result.fresh is True
        assert result.refreshed is False
        mock_esi.assert_not_called()

    def test_stale_esi_available_syncs(self, pilot_dir: Path, stale_profile: Path) -> None:
        """Stale + ESI available → sync called, refreshed=True."""
        now = datetime.now(UTC)

        def fake_sync(pd: Path) -> None:
            # Simulate sync by writing fresh markers
            _make_profile(pd, now)

        with (
            patch("aria_esi.core.freshness.is_esi_available", return_value=True),
            patch("aria_esi.core.freshness._resolve_sync_fn", return_value=fake_sync),
        ):
            result = ensure_fresh("standings", pilot_dir)

        assert result.refreshed is True
        assert result.esi_available is True
        assert result.fresh is True

    def test_stale_esi_unavailable(self, pilot_dir: Path, stale_profile: Path) -> None:
        """Stale + ESI unavailable → no sync, esi_available=False."""
        with patch("aria_esi.core.freshness.is_esi_available", return_value=False):
            result = ensure_fresh("standings", pilot_dir)
        assert result.esi_available is False
        assert result.refreshed is False
        assert result.fresh is False

    def test_sync_raises_exception(self, pilot_dir: Path, stale_profile: Path) -> None:
        """Sync raises → error populated, refreshed=False."""

        def bad_sync(pd: Path) -> None:
            raise RuntimeError("ESI exploded")

        with (
            patch("aria_esi.core.freshness.is_esi_available", return_value=True),
            patch("aria_esi.core.freshness._resolve_sync_fn", return_value=bad_sync),
        ):
            result = ensure_fresh("standings", pilot_dir)

        assert result.refreshed is False
        assert result.error is not None
        assert "ESI exploded" in result.error

    def test_noop_sync_markers_dont_advance(self, pilot_dir: Path, stale_profile: Path) -> None:
        """Sync completes but markers don't advance → specific error."""

        def noop_sync(pd: Path) -> None:
            pass  # Does nothing

        with (
            patch("aria_esi.core.freshness.is_esi_available", return_value=True),
            patch("aria_esi.core.freshness._resolve_sync_fn", return_value=noop_sync),
        ):
            result = ensure_fresh("standings", pilot_dir)

        assert result.refreshed is False
        assert result.error is not None
        assert "markers did not advance" in result.error

    def test_force_syncs_when_fresh(self, pilot_dir: Path, fresh_profile: Path) -> None:
        """force=True → triggers sync even when fresh."""
        now = datetime.now(UTC)

        def fake_sync(pd: Path) -> None:
            _make_profile(pd, now)

        with (
            patch("aria_esi.core.freshness.is_esi_available", return_value=True),
            patch("aria_esi.core.freshness._resolve_sync_fn", return_value=fake_sync),
        ):
            result = ensure_fresh("standings", pilot_dir, force=True)

        assert result.esi_available is True
        assert result.refreshed is True


# =============================================================================
# TestCmdEnsureFresh
# =============================================================================


class TestCmdEnsureFresh:
    """Tests for cmd_ensure_fresh()."""

    def test_single_section_fresh(self, pilot_dir: Path, fresh_profile: Path) -> None:
        from aria_esi.commands.freshness import cmd_ensure_fresh

        args = argparse.Namespace(section="standings", check_only=True, force=False)
        with patch("aria_esi.core.freshness._resolve_pilot_dir", return_value=pilot_dir):
            payload, exit_code = cmd_ensure_fresh(args)
        assert exit_code == 0
        assert isinstance(payload, dict)
        assert payload["fresh"] is True

    def test_single_section_stale(self, pilot_dir: Path, stale_profile: Path) -> None:
        from aria_esi.commands.freshness import cmd_ensure_fresh

        args = argparse.Namespace(section="standings", check_only=True, force=False)
        with patch("aria_esi.core.freshness._resolve_pilot_dir", return_value=pilot_dir):
            payload, exit_code = cmd_ensure_fresh(args)
        assert exit_code == 1
        assert isinstance(payload, dict)
        assert payload["fresh"] is False

    def test_all_sections(self, pilot_dir: Path, fresh_profile: Path, fresh_skills_json: Path) -> None:
        from aria_esi.commands.freshness import cmd_ensure_fresh

        args = argparse.Namespace(section="all", check_only=True, force=False)
        with patch("aria_esi.core.freshness._resolve_pilot_dir", return_value=pilot_dir):
            payload, exit_code = cmd_ensure_fresh(args)
        assert isinstance(payload, list)
        assert len(payload) == len(SECTION_REGISTRY)
        assert exit_code == 0  # All fresh

    def test_check_only_does_not_call_ensure(
        self, pilot_dir: Path, stale_profile: Path
    ) -> None:
        from aria_esi.commands.freshness import cmd_ensure_fresh

        args = argparse.Namespace(section="standings", check_only=True, force=False)
        with (
            patch("aria_esi.core.freshness._resolve_pilot_dir", return_value=pilot_dir),
            patch("aria_esi.core.freshness.is_esi_available") as mock_esi,
        ):
            payload, exit_code = cmd_ensure_fresh(args)
        # check_only should not probe ESI
        mock_esi.assert_not_called()
        assert exit_code == 1  # Stale
