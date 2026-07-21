"""Focused tests for core verification behavior."""

from __future__ import annotations

import httpx

import pytest

from verifyvat_cli.core import DiscoveryService, VerificationService, normalize_identifier, verify_once


class FakeClient:
    """Minimal client stub used by the core tests."""

    def close(self) -> None:
        """Match the SDK client's cleanup interface."""

        return None


class FakeInferrer:
    """Inference stub with a deterministic candidate."""

    def infer_id_type(self, **_: object) -> dict[str, object]:
        """Return a synthetic inference response."""

        return {
            "input": {"id": "914778271"},
            "candidates": [{"id": "914778271", "type": "no_orgnr", "confidence": 1.0}],
        }

    def pick_best_inferred_id_type(self, response: dict[str, object]) -> dict[str, object] | None:
        """Select the only inference candidate."""

        candidates = response["candidates"]
        assert isinstance(candidates, list)
        candidate = candidates[0]
        assert isinstance(candidate, dict)
        return candidate


class FakeVerifier:
    """Verification stub that returns a confirmed result."""

    def verify_id(self, **_: object) -> dict[str, object]:
        """Return a synthetic verification payload."""

        return {
            "process": {
                "output": {
                    "issues": [],
                }
            },
            "entity": None,
            "consultation_receipt": "receipt-123",
        }

    def describe_verification(self, _: dict[str, object]) -> object:
        """Return an object that mimics the SDK's decision helper."""

        class Description:
            issues: list[str] = []
            isConfirmed = True
            isSoftConfirmed = False
            isUnconfirmed = False
            isSoftUnconfirmed = False
            hasRequestError = False
            hasRegistryOutage = False
            hasStaleOutcome = False
            hasPartialCoverage = False
            isDegraded = False
            isInvalid = False
            retryRecommended = False
            reviewRecommended = False

        return Description()


class TimeoutInferrer(FakeInferrer):
    """Inference stub that simulates an upstream timeout."""

    def infer_id_type(self, **_: object) -> dict[str, object]:
        """Raise a timeout instead of returning a response."""

        raise httpx.TimeoutException("timed out")


def test_normalize_identifier_removes_separators() -> None:
    """Normalization should preserve only uppercase alphanumeric content."""

    assert normalize_identifier(" no 914-778 271 ") == "NO914778271"


def test_verify_once_returns_config_error_when_api_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config failures stay distinct in the runtime result model."""

    monkeypatch.delenv("VERIFYVAT_API_KEY", raising=False)

    result = verify_once("914778271")

    assert result.status == "CONFIG_ERROR"
    assert result.persisted_status == "NETWORK_ERROR"
    assert "VERIFYVAT_API_KEY" in result.diagnostics[0]


def test_verification_service_infers_type_and_maps_valid_result() -> None:
    """The core flow should infer the type and return a structured valid result."""

    service = VerificationService(
        client=FakeClient(),
        inferrer=FakeInferrer(),
        verifier=FakeVerifier(),
    )

    result = service.verify_identifier("914778271", country="no")

    assert result.status == "VALID"
    assert result.inferred_type == "no_orgnr"
    assert result.consultation_receipt == "receipt-123"
    assert result.provider_payload["verification"]["consultation_receipt"] == "receipt-123"


def test_verification_service_maps_timeout_to_network_error() -> None:
    """Transport failures should become handled network errors."""

    service = VerificationService(
        client=FakeClient(),
        inferrer=TimeoutInferrer(),
        verifier=FakeVerifier(),
    )

    result = service.verify_identifier("914778271", country="NO")

    assert result.status == "NETWORK_ERROR"
    assert result.persisted_status == "NETWORK_ERROR"
    assert result.diagnostics == ["timed out"]


def test_discovery_service_lists_formats_and_sources() -> None:
    """Discovery should serialize both supported ID types and registry sources."""

    class Envelope:
        """Tiny response envelope compatible with the SDK helpers."""

        def __init__(self, data: dict[str, object]) -> None:
            self.data = data

    class DiscoveryClient(FakeClient):
        """Client stub that returns synthetic domain-graph payloads."""

        def post(self, path: str, body: dict[str, object], **_: object) -> Envelope:
            """Return a small synthetic response envelope for discovery endpoints."""

            if path == "/id-types":
                assert body["country"] == "NO"
                assert body["region"] == "EMEA"
                return Envelope(
                    {
                        "types": [
                            {
                                "id": "no_orgnr",
                                "acronym": "ORGNR",
                                "name": "Organisasjonsnummer",
                                "format": ["000 000 000"],
                                "country": "NO",
                                "region": "EMEA",
                                "validation": "registry",
                                "sources": [{"id": "no-brreg", "coverage": "full"}],
                            }
                        ]
                    }
                )
            if path == "/sources":
                assert body["country"] == "NO"
                assert body["group"] == "EMEA"
                return Envelope(
                    {
                        "sources": [
                            {
                                "id": "no-brreg",
                                "acronym": "BRREG",
                                "name": "Brreg",
                                "country": "NO",
                                "active": True,
                                "jurisdictions": ["NO"],
                                "types": [
                                    {
                                        "id": "no_orgnr",
                                        "acronym": "ORGNR",
                                        "name": "Organisasjonsnummer",
                                        "format": ["000 000 000"],
                                        "country": "NO",
                                        "region": "EMEA",
                                        "validation": "registry",
                                        "coverage": "full",
                                    }
                                ],
                            }
                        ]
                    }
                )
            raise AssertionError(f"Unexpected path: {path}")

    service = DiscoveryService(client=DiscoveryClient())

    result = service.discover(
        include_formats=True,
        include_sources=True,
        country="no",
        region="emea",
    )

    assert result.country == "NO"
    assert result.region == "EMEA"
    assert result.formats[0]["id"] == "no_orgnr"
    assert result.formats[0]["coverage"] == "full"
    assert result.sources[0]["id"] == "no-brreg"
    assert result.sources[0]["active"] is True
