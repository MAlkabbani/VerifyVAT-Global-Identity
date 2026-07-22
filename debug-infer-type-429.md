# Debug Session: infer-type-429

Status: OPEN

## Symptom

- CLI requests that require `/infer-type` sometimes end with `NETWORK_ERROR`.
- The visible diagnostic is: `VerifyVAT request to /infer-type failed with status 429`.
- SDK backoff messages indicate repeated retries against `/infer-type`.

## Expected

- The CLI should distinguish an exhausted subscription/quota condition from generic network failures when evidence supports that conclusion.
- The user-facing error should explain the likely cause and next steps in plain language.

## Hypotheses

1. The VerifyVAT free-tier monthly request allowance has been exhausted, and the upstream service returns `429` for further `/infer-type` calls.
2. The upstream service is applying a short-term rate limit unrelated to the monthly free-tier cap, so the current evidence does not yet justify quota-specific messaging.
3. The SDK or transport layer exposes response text/headers that can reliably differentiate quota exhaustion from other `429` conditions.
4. The CLI currently collapses upstream `429` failures into a generic `NETWORK_ERROR`, which causes user confusion even when the response is otherwise actionable.
5. Local logs and audit records can establish the timing/frequency of failures, but official product documentation or account evidence is required to validate the specific 50-call free-tier explanation.

## Evidence Collection Plan

- Inspect current CLI/core error handling for `/infer-type` failures and `429` propagation.
- Inspect local audit/log artifacts for recent failing calls and timestamps.
- Cross-check official VerifyVAT plan or pricing documentation for the stated free-tier limit.
- Determine whether the current evidence is strong enough to present a quota-exhaustion message or whether the wording must stay conditional.

## Notes

- No business logic modified yet.

## Evidence Collected

- Local operational evidence:
  - No separate application log files were present under `~/.verifyvat`; the local SQLite audit database was the only durable runtime evidence source.
  - `verification_logs` currently contains `76` audit rows between `2026-07-21T20:53:38.049993Z` and `2026-07-22T05:39:52.494940Z`.
  - `15` rows are recorded as `NETWORK_ERROR`.
  - Multiple recent failures store the message `VerifyVAT request to /infer-type failed with status 429`.
- Official VerifyVAT documentation:
  - Pricing documents that the free Flex tier includes `50 requests included every month`.
  - Billing documents that new accounts without a payment method are blocked once the included quota is exhausted.
  - Error-handling documents define `monthly-quota-exceeded` as a `429` condition meaning the monthly included quota is exhausted and billing cannot continue automatically.
- SDK evidence:
  - `VerifyVatError` already carries `status`, `code`, and `trace_id`, but the CLI was only surfacing `str(exc)`, which hid the canonical API error code from users and local persistence.

## Conclusion

- The observed failures align with VerifyVAT returning HTTP `429` from `/infer-type`.
- The free-tier limit hypothesis is strongly supported by the combination of:
  - the official `50 requests included every month` pricing rule,
  - the official `monthly-quota-exceeded` 429 error model,
  - and the local audit volume exceeding 50 recorded verification attempts in the current investigation window.
- Absolute confirmation of the account's current plan and billing state still depends on the end user checking VerifyVAT `Profile > Billing`, because the local CLI does not have direct access to the account dashboard.

## Implemented Fix

- Preserved structured upstream error metadata (`status`, `code`, `trace_id`) in the stored provider error payload.
- Added a plain-language diagnostic for `monthly-quota-exceeded`.
- Added local runtime-event logging for handled `429` failures to support future counting and capacity review.
- Added focused regression coverage plus a manual runtime validation path.
