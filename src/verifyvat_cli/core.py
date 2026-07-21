"""Core verification flow for the VerifyVAT CLI."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from verifyvat_sdk import TypeInferrer, Verifier, VerifyVatClient
from verifyvat_sdk.client.errors import VerifyVatError
from verifyvat_sdk.entity import describe_entity
from verifyvat_sdk.infer_type.types import InferTypeCandidate, InferTypeResponse
from verifyvat_sdk.verify_id.describe import VerificationDescription
from verifyvat_sdk.verify_id.types import Verification

DEFAULT_TIMEOUT_MS = 10_000

RuntimeStatus = Literal["VALID", "INVALID", "NETWORK_ERROR", "CONFIG_ERROR"]
PersistedStatus = Literal["VALID", "INVALID", "NETWORK_ERROR"]


class ConfigError(Exception):
    """Raised when required local configuration is missing or invalid."""


@dataclass(slots=True)
class VerificationResult:
    """Structured verification result shared across CLI, storage, and tests."""

    raw_identifier: str
    normalized_identifier: str
    inferred_type: str | None
    status: RuntimeStatus
    persisted_status: PersistedStatus
    execution_timestamp: str
    consultation_receipt: str | None
    legal_name: str | None
    address: str | None
    diagnostics: list[str]
    provider_payload: dict[str, Any]

    def provider_payload_json(self) -> str:
        """Serialize the provider payload for durable audit storage."""

        return json.dumps(self.provider_payload, sort_keys=True, default=str)

    def to_json_dict(self, *, audit_db_path: str | None = None) -> dict[str, Any]:
        """Shape the result into the stable `--json` output contract."""

        return {
            "raw_identifier": self.raw_identifier,
            "normalized_identifier": self.normalized_identifier,
            "inferred_type": self.inferred_type,
            "verification_result": {
                "status": self.status,
                "consultation_receipt": self.consultation_receipt,
                "legal_name": self.legal_name,
                "address": self.address,
                "diagnostics": self.diagnostics,
            },
            "audit_record": {
                "execution_timestamp": self.execution_timestamp,
                "internal_resolution_state": self.persisted_status,
                "database_path": audit_db_path,
            },
            "provider_payload": self.provider_payload,
        }


@dataclass(slots=True)
class VerificationService:
    """Wraps the SDK objects behind a narrow domain-oriented interface."""

    client: VerifyVatClient
    inferrer: TypeInferrer
    verifier: Verifier

    @classmethod
    def from_environment(cls, *, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> VerificationService:
        """Build an SDK-backed service using environment configuration only."""

        api_key = os.environ.get("VERIFYVAT_API_KEY")
        if not api_key:
            raise ConfigError(
                "Missing VERIFYVAT_API_KEY. Export the environment variable and retry."
            )

        client = VerifyVatClient(api_key=api_key, timeout_ms=timeout_ms)
        return cls(
            client=client,
            inferrer=TypeInferrer(client),
            verifier=Verifier(client),
        )

    def close(self) -> None:
        """Release the underlying SDK client resources."""

        self.client.close()

    def verify_identifier(
        self,
        raw_identifier: str,
        *,
        country: str | None = None,
        explicit_type: str | None = None,
    ) -> VerificationResult:
        """Verify one raw identifier and return a structured result."""

        execution_timestamp = _utc_now_iso()
        normalized_identifier = normalize_identifier(raw_identifier)
        normalized_country = normalize_country_hint(country)
        normalized_type = normalize_explicit_type(explicit_type)

        if not normalized_identifier:
            return _build_local_invalid_result(
                raw_identifier=raw_identifier,
                normalized_identifier=normalized_identifier,
                inferred_type=normalized_type,
                execution_timestamp=execution_timestamp,
                diagnostics=["The raw identifier is empty after normalization."],
            )

        inference_payload: InferTypeResponse | None = None
        inference_candidate: InferTypeCandidate | None = None

        try:
            if normalized_type is None:
                inference_payload = self.inferrer.infer_id_type(
                    id=normalized_identifier,
                    country=normalized_country,
                )
                inference_candidate = self.inferrer.pick_best_inferred_id_type(inference_payload)

                if inference_candidate is None:
                    return _build_local_invalid_result(
                        raw_identifier=raw_identifier,
                        normalized_identifier=normalized_identifier,
                        inferred_type=None,
                        execution_timestamp=execution_timestamp,
                        diagnostics=[
                            "Unable to infer a supported identifier type from the normalized identifier."
                        ],
                        provider_payload={
                            "inference": _coerce_jsonable(inference_payload),
                        },
                    )

                normalized_type = str(inference_candidate["type"])
                normalized_identifier = str(inference_candidate.get("id", normalized_identifier))

            verification = self.verifier.verify_id(
                id=normalized_identifier,
                type=normalized_type,
                country=normalized_country,
            )
            description = self.verifier.describe_verification(verification)
        except ConfigError:
            raise
        except (VerifyVatError, httpx.TimeoutException, httpx.HTTPError, json.JSONDecodeError) as exc:
            return _build_network_error_result(
                raw_identifier=raw_identifier,
                normalized_identifier=normalized_identifier,
                inferred_type=normalized_type,
                execution_timestamp=execution_timestamp,
                diagnostics=[_sanitize_error_message(str(exc))],
                provider_payload={
                    "inference": _coerce_jsonable(inference_payload),
                    "error": {
                        "message": _sanitize_error_message(str(exc)),
                        "type": exc.__class__.__name__,
                    },
                },
            )

        return _build_verification_result(
            raw_identifier=raw_identifier,
            normalized_identifier=normalized_identifier,
            inferred_type=normalized_type,
            execution_timestamp=execution_timestamp,
            verification=verification,
            description=description,
            inference_payload=inference_payload,
            inference_candidate=inference_candidate,
        )


def verify_once(
    raw_identifier: str,
    *,
    country: str | None = None,
    explicit_type: str | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> VerificationResult:
    """Verify one identifier with an ephemeral SDK client."""

    execution_timestamp = _utc_now_iso()

    try:
        service = VerificationService.from_environment(timeout_ms=timeout_ms)
    except ConfigError as exc:
        return _build_config_error_result(
            raw_identifier=raw_identifier,
            normalized_identifier=normalize_identifier(raw_identifier),
            inferred_type=normalize_explicit_type(explicit_type),
            execution_timestamp=execution_timestamp,
            diagnostics=[str(exc)],
        )

    try:
        return service.verify_identifier(
            raw_identifier,
            country=country,
            explicit_type=explicit_type,
        )
    finally:
        service.close()


def normalize_identifier(raw_identifier: str) -> str:
    """Normalize a raw identifier by trimming whitespace and removing separators."""

    return "".join(character for character in raw_identifier.strip().upper() if character.isalnum())


def normalize_country_hint(country: str | None) -> str | None:
    """Normalize a user-provided country hint into an ISO-like uppercase token."""

    if country is None:
        return None

    cleaned_country = "".join(character for character in country.strip().upper() if character.isalpha())
    return cleaned_country or None


def normalize_explicit_type(explicit_type: str | None) -> str | None:
    """Normalize a user-provided explicit type without changing its semantic token."""

    if explicit_type is None:
        return None

    cleaned_type = explicit_type.strip().lower()
    return cleaned_type or None


def _build_verification_result(
    *,
    raw_identifier: str,
    normalized_identifier: str,
    inferred_type: str | None,
    execution_timestamp: str,
    verification: Verification,
    description: VerificationDescription,
    inference_payload: InferTypeResponse | None,
    inference_candidate: InferTypeCandidate | None,
) -> VerificationResult:
    """Map raw SDK output into the internal verification-result model."""

    legal_name, address = _extract_entity_details(verification)
    diagnostics = _description_to_diagnostics(description)
    consultation_receipt = _extract_consultation_receipt(verification)
    status = _map_runtime_status(description)

    return VerificationResult(
        raw_identifier=raw_identifier,
        normalized_identifier=normalized_identifier,
        inferred_type=inferred_type,
        status=status,
        persisted_status=_fold_persisted_status(status),
        execution_timestamp=execution_timestamp,
        consultation_receipt=consultation_receipt,
        legal_name=legal_name,
        address=address,
        diagnostics=diagnostics,
        provider_payload={
            "inference": _coerce_jsonable(inference_payload),
            "inference_candidate": _coerce_jsonable(inference_candidate),
            "verification": _coerce_jsonable(verification),
        },
    )


def _build_local_invalid_result(
    *,
    raw_identifier: str,
    normalized_identifier: str,
    inferred_type: str | None,
    execution_timestamp: str,
    diagnostics: list[str],
    provider_payload: dict[str, Any] | None = None,
) -> VerificationResult:
    """Build a local invalid result without making a network call."""

    return VerificationResult(
        raw_identifier=raw_identifier,
        normalized_identifier=normalized_identifier,
        inferred_type=inferred_type,
        status="INVALID",
        persisted_status="INVALID",
        execution_timestamp=execution_timestamp,
        consultation_receipt=None,
        legal_name=None,
        address=None,
        diagnostics=diagnostics,
        provider_payload=provider_payload or {"verification": None},
    )


def _build_network_error_result(
    *,
    raw_identifier: str,
    normalized_identifier: str,
    inferred_type: str | None,
    execution_timestamp: str,
    diagnostics: list[str],
    provider_payload: dict[str, Any],
) -> VerificationResult:
    """Build a handled runtime-failure result."""

    return VerificationResult(
        raw_identifier=raw_identifier,
        normalized_identifier=normalized_identifier,
        inferred_type=inferred_type,
        status="NETWORK_ERROR",
        persisted_status="NETWORK_ERROR",
        execution_timestamp=execution_timestamp,
        consultation_receipt=None,
        legal_name=None,
        address=None,
        diagnostics=diagnostics,
        provider_payload=provider_payload,
    )


def _build_config_error_result(
    *,
    raw_identifier: str,
    normalized_identifier: str,
    inferred_type: str | None,
    execution_timestamp: str,
    diagnostics: list[str],
) -> VerificationResult:
    """Build a safe configuration failure result.

    SQLite stores only three states, so config failures are folded into
    `NETWORK_ERROR` for persistence while staying distinct in user output.
    """

    return VerificationResult(
        raw_identifier=raw_identifier,
        normalized_identifier=normalized_identifier,
        inferred_type=inferred_type,
        status="CONFIG_ERROR",
        persisted_status="NETWORK_ERROR",
        execution_timestamp=execution_timestamp,
        consultation_receipt=None,
        legal_name=None,
        address=None,
        diagnostics=diagnostics,
        provider_payload={
            "error": {
                "message": diagnostics[0] if diagnostics else "Configuration error",
                "type": "ConfigError",
            }
        },
    )


def _extract_entity_details(verification: Verification) -> tuple[str | None, str | None]:
    """Extract legal-name and address details without assuming they are always present."""

    entity = verification.get("entity")
    if entity is None:
        return None, None

    entity_description = describe_entity(entity)
    legal_name = _read_nested_value(entity_description, ("name", "value"))
    address = _read_nested_value(entity_description, ("address", "value"))

    return _as_string(legal_name), _as_string(address)


def _extract_consultation_receipt(verification: Verification) -> str | None:
    """Locate a consultation receipt using several likely provider key names."""

    return _find_first_string(
        verification,
        {
            "consultation_receipt",
            "consultationReceipt",
            "receipt",
            "trace_id",
            "traceId",
            "request_id",
            "requestId",
        },
    )


def _description_to_diagnostics(description: VerificationDescription) -> list[str]:
    """Flatten SDK decision signals into concise diagnostic strings."""

    diagnostics = [str(issue) for issue in description.issues]
    if diagnostics:
        return diagnostics

    if description.isConfirmed:
        return ["The identifier was confirmed by at least one registry source."]
    if description.isInvalid:
        return ["The identifier failed syntactic or registry validation."]
    if description.hasRequestError:
        return ["The verification request failed before a reliable outcome was returned."]
    if description.isDegraded:
        return ["The verification result is degraded and should be treated cautiously."]

    return ["The provider returned a structured result without additional diagnostic issues."]


def _map_runtime_status(description: VerificationDescription) -> RuntimeStatus:
    """Map SDK reasoning helpers into the CLI's internal status model."""

    if description.hasRequestError or description.hasRegistryOutage:
        return "NETWORK_ERROR"
    if description.isConfirmed or description.isSoftConfirmed:
        return "VALID"
    if description.isInvalid or description.isUnconfirmed or description.isSoftUnconfirmed:
        return "INVALID"
    if description.isDegraded:
        return "NETWORK_ERROR"
    return "INVALID"


def _fold_persisted_status(status: RuntimeStatus) -> PersistedStatus:
    """Fold runtime-only states into the SQLite-compatible status set."""

    if status == "VALID":
        return "VALID"
    if status == "INVALID":
        return "INVALID"
    return "NETWORK_ERROR"


def _coerce_jsonable(value: Any) -> Any:
    """Convert SDK objects into JSON-serializable Python primitives."""

    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _coerce_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_coerce_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_coerce_jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key: _coerce_jsonable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def _read_nested_value(value: Any, path: tuple[str, ...]) -> Any:
    """Read a nested attribute or mapping path without raising lookup errors."""

    current: Any = value
    for key in path:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(key)
            continue
        current = getattr(current, key, None)
    return current


def _find_first_string(value: Any, candidate_keys: set[str]) -> str | None:
    """Recursively locate the first string value whose key matches the candidate set."""

    if isinstance(value, dict):
        for key, child in value.items():
            if key in candidate_keys and isinstance(child, str) and child:
                return child
            nested_match = _find_first_string(child, candidate_keys)
            if nested_match is not None:
                return nested_match
        return None

    if isinstance(value, list):
        for child in value:
            nested_match = _find_first_string(child, candidate_keys)
            if nested_match is not None:
                return nested_match
        return None

    return None


def _sanitize_error_message(message: str) -> str:
    """Redact any configured API key from surfaced error messages."""

    api_key = os.environ.get("VERIFYVAT_API_KEY")
    if api_key:
        return message.replace(api_key, "[REDACTED]")
    return message


def _utc_now_iso() -> str:
    """Return an ISO 8601 UTC timestamp suitable for audit storage."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _as_string(value: Any) -> str | None:
    """Normalize optional string-like values into plain strings."""

    if value is None:
        return None
    return str(value)
