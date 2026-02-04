"""
Tests for Political Entity Tracking.

Tests entity resolution, ESI search, and trigger result handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from aria_esi.services.redisq.notifications.political_entities import (
    PoliticalEntityTriggerResult,
    _search_entity,
    resolve_entity_names,
)

# =============================================================================
# TestPoliticalEntityTriggerResult
# =============================================================================


class TestPoliticalEntityTriggerResult:
    """Tests for PoliticalEntityTriggerResult dataclass."""

    def test_is_attacker_true(self):
        """is_attacker returns True when role is 'attacker'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="corporation",
            entity_id=98000001,
            entity_name="Test Corp",
            role="attacker",
        )

        assert result.is_attacker is True

    def test_is_attacker_false(self):
        """is_attacker returns False when role is not 'attacker'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="corporation",
            entity_id=98000001,
            entity_name="Test Corp",
            role="victim",
        )

        assert result.is_attacker is False

    def test_is_victim_true(self):
        """is_victim returns True when role is 'victim'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="alliance",
            entity_id=99001234,
            entity_name="Test Alliance",
            role="victim",
        )

        assert result.is_victim is True

    def test_is_victim_false(self):
        """is_victim returns False when role is not 'victim'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="alliance",
            entity_id=99001234,
            entity_name="Test Alliance",
            role="attacker",
        )

        assert result.is_victim is False

    def test_is_corporation_true(self):
        """is_corporation returns True when entity_type is 'corporation'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="corporation",
            entity_id=98000001,
            entity_name="Test Corp",
            role="attacker",
        )

        assert result.is_corporation is True

    def test_is_corporation_false(self):
        """is_corporation returns False when entity_type is not 'corporation'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="alliance",
            entity_id=99001234,
            entity_name="Test Alliance",
            role="attacker",
        )

        assert result.is_corporation is False

    def test_is_alliance_true(self):
        """is_alliance returns True when entity_type is 'alliance'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="alliance",
            entity_id=99001234,
            entity_name="Test Alliance",
            role="victim",
        )

        assert result.is_alliance is True

    def test_is_alliance_false(self):
        """is_alliance returns False when entity_type is not 'alliance'."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="corporation",
            entity_id=98000001,
            entity_name="Test Corp",
            role="victim",
        )

        assert result.is_alliance is False

    def test_to_dict(self):
        """to_dict returns all fields in dictionary."""
        result = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="corporation",
            entity_id=98000001,
            entity_name="Test Corp",
            role="attacker",
        )

        d = result.to_dict()

        assert d["matched"] is True
        assert d["entity_type"] == "corporation"
        assert d["entity_id"] == 98000001
        assert d["entity_name"] == "Test Corp"
        assert d["role"] == "attacker"

    def test_to_dict_unmatched(self):
        """to_dict works for unmatched results."""
        result = PoliticalEntityTriggerResult(matched=False)

        d = result.to_dict()

        assert d["matched"] is False
        assert d["entity_type"] == ""
        assert d["entity_id"] == 0
        assert d["entity_name"] == ""
        assert d["role"] == ""

    def test_default_values(self):
        """Default values are set correctly."""
        result = PoliticalEntityTriggerResult()

        assert result.matched is False
        assert result.entity_type == ""
        assert result.entity_id == 0
        assert result.entity_name == ""
        assert result.role == ""


# =============================================================================
# TestResolveEntityNames
# =============================================================================


class TestResolveEntityNames:
    """Tests for resolve_entity_names function."""

    def test_integer_ids_passthrough(self):
        """Integer IDs are passed through without ESI lookup."""
        # No mock needed - integers don't trigger search
        corps, alliances = resolve_entity_names(
            corporations=[98000001, 98000002],
            alliances=[99001234],
        )

        assert corps == {98000001, 98000002}
        assert alliances == {99001234}

    @patch(
        "aria_esi.services.redisq.notifications.political_entities._search_entity"
    )
    def test_string_names_trigger_search(self, mock_search):
        """String names trigger ESI search."""
        mock_search.return_value = 98000001

        corps, alliances = resolve_entity_names(
            corporations=["Test Corporation"],
            alliances=[],
        )

        assert 98000001 in corps
        mock_search.assert_called_once_with("Test Corporation", "corporation")

    @patch(
        "aria_esi.services.redisq.notifications.political_entities._search_entity"
    )
    def test_mixed_list(self, mock_search):
        """Mixed list of IDs and names works correctly."""
        mock_search.return_value = 98000003

        corps, alliances = resolve_entity_names(
            corporations=[98000001, "Test Corp", 98000002],
            alliances=[99001234],
        )

        # Integer IDs should be present
        assert 98000001 in corps
        assert 98000002 in corps
        # Resolved name should be present
        assert 98000003 in corps
        # Alliance should be present
        assert 99001234 in alliances

    @patch(
        "aria_esi.services.redisq.notifications.political_entities._search_entity"
    )
    def test_search_returns_none(self, mock_search):
        """Names that don't resolve are not added."""
        mock_search.return_value = None

        corps, alliances = resolve_entity_names(
            corporations=["Nonexistent Corp"],
            alliances=[],
        )

        # Should be empty since name didn't resolve
        assert len(corps) == 0

    def test_empty_lists(self):
        """Empty input lists return empty sets."""
        corps, alliances = resolve_entity_names(
            corporations=[],
            alliances=[],
        )

        assert corps == set()
        assert alliances == set()

    @patch(
        "aria_esi.services.redisq.notifications.political_entities._search_entity"
    )
    def test_alliance_name_resolution(self, mock_search):
        """Alliance names are resolved via ESI search."""
        mock_search.return_value = 99005678

        corps, alliances = resolve_entity_names(
            corporations=[],
            alliances=["Test Alliance"],
        )

        assert 99005678 in alliances
        mock_search.assert_called_once_with("Test Alliance", "alliance")

    @patch(
        "aria_esi.services.redisq.notifications.political_entities._search_entity"
    )
    def test_multiple_string_names(self, mock_search):
        """Multiple string names are resolved individually."""
        mock_search.side_effect = [98000001, 98000002]

        corps, alliances = resolve_entity_names(
            corporations=["Corp One", "Corp Two"],
            alliances=[],
        )

        assert 98000001 in corps
        assert 98000002 in corps
        assert mock_search.call_count == 2


# =============================================================================
# TestSearchEntity
# =============================================================================


class TestSearchEntity:
    """Tests for _search_entity function."""

    @patch("requests.get")
    def test_corporation_lookup_success(self, mock_get):
        """Successful corporation lookup returns ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"corporation": [98000001, 98000002]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = _search_entity("Test Corp", "corporation")

        # Should return first match
        assert result == 98000001

    @patch("requests.get")
    def test_alliance_lookup_success(self, mock_get):
        """Successful alliance lookup returns ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"alliance": [99001234]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = _search_entity("Test Alliance", "alliance")

        assert result == 99001234

    @patch("requests.get")
    def test_request_timeout(self, mock_get):
        """Request timeout returns None."""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = _search_entity("Test Corp", "corporation")

        assert result is None

    @patch("requests.get")
    def test_connection_error(self, mock_get):
        """Connection error returns None."""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = _search_entity("Test Corp", "corporation")

        assert result is None

    @patch("requests.get")
    def test_invalid_json_response(self, mock_get):
        """Invalid JSON response returns None."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = _search_entity("Test Corp", "corporation")

        assert result is None

    @patch("requests.get")
    def test_empty_search_results(self, mock_get):
        """Empty search results return None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # No matches at all
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = _search_entity("Nonexistent", "corporation")

        assert result is None

    @patch("requests.get")
    def test_empty_category_results(self, mock_get):
        """Empty category in results returns None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"corporation": []}  # Empty list
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = _search_entity("Test", "corporation")

        assert result is None

    @patch("requests.get")
    def test_wrong_category_in_response(self, mock_get):
        """Wrong category in response returns None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"alliance": [99001234]}  # Wrong category
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = _search_entity("Test", "corporation")

        assert result is None

    @patch("requests.get")
    def test_http_error_status(self, mock_get):
        """HTTP error status returns None."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_get.return_value = mock_response

        result = _search_entity("Test Corp", "corporation")

        assert result is None

    @patch("requests.get")
    def test_strict_search_parameter(self, mock_get):
        """Search uses strict parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"corporation": [98000001]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        _search_entity("Test Corp", "corporation")

        # Check that strict=true was passed
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["strict"] == "true"

    @patch("requests.get")
    def test_categories_parameter(self, mock_get):
        """Search passes correct category parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"alliance": [99001234]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        _search_entity("Test Alliance", "alliance")

        # Check that categories parameter was set
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["categories"] == "alliance"

    @patch("requests.get")
    def test_search_parameter(self, mock_get):
        """Search passes search term parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"corporation": [98000001]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        _search_entity("My Test Corp", "corporation")

        # Check that search parameter was set
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["search"] == "My Test Corp"

    @patch("requests.get")
    def test_timeout_parameter(self, mock_get):
        """Search uses timeout parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"corporation": [98000001]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        _search_entity("Test Corp", "corporation")

        # Check that timeout was passed
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["timeout"] == 10


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for political entity tracking."""

    @patch(
        "aria_esi.services.redisq.notifications.political_entities._search_entity"
    )
    def test_resolve_mixed_types_both_categories(self, mock_search):
        """Resolve both corporations and alliances with mixed types."""
        # Return different IDs for corp and alliance searches
        mock_search.side_effect = [98000099, 99009999]

        corps, alliances = resolve_entity_names(
            corporations=[98000001, "Named Corp"],
            alliances=[99001234, "Named Alliance"],
        )

        # Integer IDs should be present
        assert 98000001 in corps
        assert 99001234 in alliances

        # Resolved names should be present
        assert 98000099 in corps
        assert 99009999 in alliances

    def test_trigger_result_full_workflow(self):
        """Full workflow of creating and using trigger results."""
        # Create attacker match
        attacker = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="alliance",
            entity_id=99001234,
            entity_name="Hostile Alliance",
            role="attacker",
        )

        # Create victim match
        victim = PoliticalEntityTriggerResult(
            matched=True,
            entity_type="corporation",
            entity_id=98000001,
            entity_name="Our Corp",
            role="victim",
        )

        # Verify properties
        assert attacker.is_attacker and attacker.is_alliance
        assert victim.is_victim and victim.is_corporation

        # Verify serialization
        attacker_dict = attacker.to_dict()
        victim_dict = victim.to_dict()

        assert attacker_dict["entity_name"] == "Hostile Alliance"
        assert victim_dict["entity_name"] == "Our Corp"
