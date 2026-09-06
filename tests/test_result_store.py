"""Tests for result store staleness vectors.

The staleness_vectors.json file is shared with phasesweep and must stay
byte-identical. These tests verify the staleness logic matches the contract.

The vectors reference model keys from phasesweep's registry, so we test
the abstract staleness rules (record_is_current, _attached) directly
with mock registry lookups rather than the heatsweep registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from heatsweep.registry import ModelInfo
from heatsweep.result_store import _attached, record_is_current

_VECTORS_PATH = Path(__file__).parent / "staleness_vectors.json"


@pytest.fixture
def vectors() -> dict:
    return json.loads(_VECTORS_PATH.read_text())


def _mock_registry(model: str, live_version: int | None) -> dict[str, ModelInfo]:
    """Build a mock registry with one model at the given live version."""
    if live_version is None:
        return {}
    return {
        model: ModelInfo(
            name=model, source="computed", cost="fast",
            produces=frozenset(), needs=frozenset(), hash_fields=frozenset(),
            version=live_version,
        ),
    }


class TestStalenessVectors:
    """Staleness vectors from the shared contract."""

    def test_vectors_file_exists(self) -> None:
        assert _VECTORS_PATH.exists()

    def test_staleness_vectors(self, vectors: dict) -> None:
        for vec in vectors["staleness"]["cases"]:
            source = vec["source"]
            if source is None:
                source = "computed"  # default per contract
            model = vec["model"]
            stamped = vec.get("stamped_version")
            live = vec.get("live_version")
            expected_serve = vec["expect"] == "serve"

            mock_reg = _mock_registry(model, live)
            with patch("heatsweep.registry.MODEL_REGISTRY", mock_reg):
                result = record_is_current(source, model, stamped)
            assert result == expected_serve, (
                f"staleness vector '{vec['label']}': "
                f"expected {'serve' if expected_serve else 'stale'}, "
                f"got {'serve' if result else 'stale'}"
            )

    def test_attachment_vectors(self, vectors: dict) -> None:
        for vec in vectors["attachment"]["cases"]:
            source = vec["source"]
            rec_cid = vec["record_config_id"]
            rec_name = vec["record_name"]
            tgt_cid = vec["target_config_id"]
            tgt_name = vec["target_name"]
            expected_attached = vec["expect"] == "attached"

            result = _attached(source, rec_cid, rec_name, tgt_cid, tgt_name)
            assert result == expected_attached, (
                f"attachment vector '{vec['label']}': "
                f"expected {'attached' if expected_attached else 'detached'}, "
                f"got {'attached' if result else 'detached'}"
            )

    def test_partial_staleness_conformance(self, vectors: dict) -> None:
        """Verify partial staleness rules from the contract (empty for now)."""
        cases = vectors.get("partial_staleness_conformance", {}).get("cases", [])
        for vec in cases:
            source = vec.get("source", "computed")
            model = vec["model"]
            stamped = vec.get("stamped_version")
            live = vec.get("live_version")
            expected_serve = vec["expect"] == "serve"

            mock_reg = _mock_registry(model, live)
            with patch("heatsweep.registry.MODEL_REGISTRY", mock_reg):
                result = record_is_current(source, model, stamped)
            assert result == expected_serve
