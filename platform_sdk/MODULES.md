# Platform SDK — Complete Module Reference

> **Purpose:** This document is the single authoritative reference for every module in `platform_sdk`.
> It defines what each module does, which tools back it, and whether it is part of the **minimal
> production stack** or deferred until a specific trigger is met.
>
> **Rule:** Any concern covered here must be satisfied through `platform_sdk`. No app or agent
> may re-implement these concerns directly. See `docs/CONTRACT.md`.

---

## How to Read This Document

Each module entry contains:
- **Path** — import location
- **Purpose** — one-line description
- **Description** — what it does and what it prevents
- **Consumer** — typical SaaS/consumer-grade tools
- **Enterprise** — enterprise-grade tools
- **OSS ★** — recommended open-source tool
- **Minimal** — `YES` (ship day one) or `DEFERRED — add when [trigger]`

---

## Minimal Stack Summary

| Tier | Count | Modules |
|------|-------|---------|
| Non-negotiable (Tier A) | 12 | identity, logging, errors, config, secrets, data, validate, context, health, audit, authorization, notifications |
| Add within sprints (Tier B) | 5 | metrics, retry, ratelimit, serialize, cache |
| GenAI additions (Tier C) | 3 | inference, llm_obs, vector |
| **Total minimal** | **20** | |
| Deferred | 24 | All others — pulled in as the platform earns the complexity |

---

## tier0_core — Foundational (zero external dependencies allowed within this tier)

---

### `identity.py`
**Path:** `platform_sdk.tier0_core.identity`
**Purpose:** Authenticate and verify identity; normalize principals; token/session validation; provider abstraction.

**Description:**
The entry gate for every request. Verifies tokens (JWT, opaque, session), normalizes the result into
a `Principal` (id, email, org_id, roles), and abstracts away which identity provider is running.
Multi-tenancy org model is baked in — `org_id` is always present on the Principal.
No app or agent ever touches raw JWT libraries or provider SDKs directly.

**Consumer:** Clerk; Firebase Auth
**Enterprise:** Auth0; Okta
**OSS ★:** Zitadel (event-sourced, cloud-native, built-in multi-tenancy); Authentik (best flow UX)

**Minimal:** `YES — Tier A`

---

### `logging.py`
**Path:** `platform_sdk.tier0_core.logging`
**Purpose:** Structured logs with levels, correlation IDs, redaction rules, sink/exporter routing.

**Description:**
Wraps structlog to produce JSON-structured log entries with automatic injection of
`request_id`, `trace_id`, and `principal_id` from context. All logs go through redaction
rules before output. Sink routing (stdout for dev, Loki/Datadog/Splunk for prod) is
configured via env vars — call sites never know or care where logs go.
Prevents: raw `print()`, unstructured log strings, accidental PII in logs.

**Consumer:** Papertrail; Logtail
**Enterprise:** Datadog; Splunk
**OSS ★:** Grafana Loki + structlog

**Minimal:** `YES — Tier A`

---

### `errors.py`
**Path:** `platform_sdk.tier0_core.errors`
**Purpose:** Standard error types/codes, capture and reporting, user-safe messages, alert triggers.

**Description:**
Defines the error taxonomy (`PlatformError`, `AuthError`, `ValidationError`, `NotFoundError`,
`RateLimitError`, `UpstreamError`) with stable numeric codes. Each error type has a
`user_message` (safe to show users) and a `detail` (internal only). Error capture
(Sentry or OTel error signals) is wired transparently — raising a `PlatformError`
automatically reports it. Prevents: raw Python exceptions leaking stack traces to users,
inconsistent error shapes across services.

**Consumer:** Sentry (free tier); Bugsnag
**Enterprise:** Sentry; internal incident tooling
**OSS ★:** Sentry OSS + OpenTelemetry error signals

**Minimal:** `YES — Tier A`

---

### `config.py`
**Path:** `platform_sdk.tier0_core.config`
**Purpose:** Typed config access, env layering, safe defaults, runtime reload strategy.

**Description:**
Pydantic-Settings based typed configuration. Loads from `.env` → environment → remote
config (etcd/AWS AppConfig) in that order, with later sources overriding earlier.
All config fields are typed; accessing an unknown key is a compile-time error, not
a runtime `KeyError`. Prevents: scattered `os.getenv()` calls, untyped config access,
missing required config discovered at runtime.

**Consumer:** python-dotenv; Vercel env vars
**Enterprise:** AWS AppConfig; Azure App Configuration
**OSS ★:** pydantic-settings + etcd (Kubernetes-native); Consul (multi-cloud)

**Minimal:** `YES — Tier A`

---

### `secrets.py`
**Path:** `platform_sdk.tier0_core.secrets`
**Purpose:** Secret retrieval and rotation hooks, least-privilege access, no secrets in code or logs.

**Description:**
Single entry point for all secret access. Retrieves secrets by name from the configured
backend (env vars for local, Infisical/Vault for prod). Supports rotation hooks — callers
register a callback that fires when a secret is rotated. All returned secret values are
wrapped in a `SecretStr` type that refuses to be serialized or logged. Prevents: secrets
in source code, secrets appearing in logs, secrets accessed via raw `os.getenv()`.

**Consumer:** Doppler; OS keychain/env vars
**Enterprise:** AWS Secrets Manager; Azure Key Vault
**OSS ★:** Infisical (MIT, modern DX); OpenBao (Linux Foundation Vault fork — note: HashiCorp Vault moved to BSL 1.1 in 2023)

**Minimal:** `YES — Tier A`

---

### `data.py`
**Path:** `platform_sdk.tier0_core.data`
**Purpose:** Typed ORM access, DB connection lifecycle, transaction boundaries, query safety, migrations pattern.

**Description:**
SQLAlchemy 2.x session factory with async support, connection pooling, and transaction
context managers. Migrations are managed via Alembic with a standard migration directory
convention. Provides `get_session()` context manager that handles commit/rollback/close.
"Session" here means DB session (transactions) — not HTTP sessions. Prevents: raw SQL
strings without parameterization, connection leaks, manual transaction management.

**Consumer:** Prisma; Supabase
**Enterprise:** Amazon RDS; PlanetScale; Neon; CockroachDB
**OSS ★:** SQLAlchemy 2.x + Alembic

**Minimal:** `YES — Tier A`

---

### `metrics.py`
**Path:** `platform_sdk.tier0_core.metrics`
**Purpose:** Counters/gauges/histograms, standard naming, export to backend, SLO-friendly signals.

**Description:**
Thin wrapper over `prometheus_client` providing pre-named metric factories with standard
labels (`service`, `env`, `version`). Enforces naming conventions (snake_case, unit suffix).
Exports via `/metrics` endpoint or push gateway. Prevents: metric naming drift across
services, raw Prometheus client calls, inconsistent label sets.

**Consumer:** Grafana Cloud; New Relic
**Enterprise:** Datadog; Dynatrace
**OSS ★:** Prometheus + Grafana

**Minimal:** `YES — Tier B (add by sprint 2)`

---

### `tracing.py`
**Path:** `platform_sdk.tier0_core.tracing`
**Purpose:** Spans + propagation, trace IDs across boundaries, sampling, exporter control.

**Description:**
OpenTelemetry SDK wrapper. Provides `trace_span()` context manager, automatic W3C
trace-context propagation in HTTP headers, configurable sampling, and exporter routing
(stdout for dev, Tempo/Jaeger/Datadog for prod). Prevents: manual span management,
trace context lost across service boundaries, vendor lock-in on tracing backend.

**Consumer:** Honeycomb; Lightstep
**Enterprise:** Datadog; New Relic
**OSS ★:** OpenTelemetry → Grafana Tempo (backend, object-storage only, 60% lower cost at scale); Jaeger (better interactive UI for smaller deployments)

**Minimal:** `DEFERRED — add when you have 3+ services and logging alone doesn't pinpoint latency`

---

### `config.py` *(already listed above)*

### `flags.py`
**Path:** `platform_sdk.tier0_core.flags`
**Purpose:** Feature gates/kill-switches, rollout rules, targeting, consistent evaluation semantics.

**Description:**
OpenFeature SDK abstraction layer — vendor-neutral. Exposes `is_enabled(flag, context)` and
`get_variant(flag, context)`. Backend (Unleash/Flagsmith/GrowthBook) is swapped via env var
without changing call sites. Prevents: scattered boolean env vars used as feature flags,
inconsistent evaluation (flag returns different values in same request), direct provider SDK
calls in business logic.

**Standard:** OpenFeature SDK (CNCF, vendor-neutral abstraction)
**Consumer:** Flagsmith Cloud; GrowthBook Cloud
**Enterprise:** LaunchDarkly; Split
**OSS ★:** Unleash (CNCF trajectory) behind OpenFeature; GrowthBook (best for AI A/B + evals)

**Minimal:** `DEFERRED — add after first incident where you wish you had a kill switch`

---

### `tasks.py`
**Path:** `platform_sdk.tier0_core.tasks`
**Purpose:** Background jobs, retries/schedules, idempotency helpers, durable execution options.

**Description:**
Two distinct abstractions unified under one interface: (1) simple background jobs with
retries, scheduling, and visibility (backed by Hatchet or Celery); (2) durable execution
with guaranteed completion, state persistence, and compensation (backed by Temporal).
`enqueue_job()` for simple; `start_workflow()` for durable. Do not conflate them.
Prevents: ad-hoc threading, fire-and-forget coroutines with no retry, lost jobs on restart.

**Consumer:** Hatchet; Celery + Redis
**Enterprise:** Temporal; AWS Step Functions
**OSS ★:** Hatchet (modern, persistent history, built-in UI); Temporal OSS (durable execution); Celery (simple, high-throughput)

**Minimal:** `DEFERRED — add when you have an identifiable background job requirement`

---

### `http.py`
**Path:** `platform_sdk.tier0_core.http`
**Purpose:** Standard HTTP primitives — status codes, headers, common response helpers.

**Description:**
Thin layer over stdlib and framework HTTP primitives. Provides typed `HttpStatus` enum,
standard response constructors (`ok()`, `created()`, `not_found()`, etc.), and shared
header constants. Ensures consistent response shapes across all endpoints. Prevents:
magic status code integers scattered through code, inconsistent response envelopes.

**OSS ★:** stdlib/http + framework primitives (FastAPI/Starlette/Flask)

**Minimal:** `YES — Tier A (absorbed into framework initially; extract when shape consistency is needed)`

---

### `ids.py`
**Path:** `platform_sdk.tier0_core.ids`
**Purpose:** ID generation (UUID v7/ULID for time-ordered IDs), request IDs, trace correlation helpers.

**Description:**
Centralized ID generation. UUID v7 (time-ordered, sortable) for entity IDs; ULID as
alternative. `new_request_id()` for correlation IDs. Prevents: UUID v4 used where
sortability matters (index performance), inconsistent ID formats across services,
ad-hoc `str(uuid.uuid4())` calls without format standardization.

**OSS ★:** uuid7 library; python-ulid; stdlib uuid (v4 fallback)

**Minimal:** `YES — Tier A (absorbed into context.py initially; extract when ID generation needs standardizing)`

---

### `redact.py`
**Path:** `platform_sdk.tier0_core.redact`
**Purpose:** Redaction rules for logs/errors/audit; prevents accidental secret/PII leaks.

**Description:**
Regex and field-name based redaction engine. Scans log payloads, error details, and
audit records for known PII patterns (email, phone, SSN, credit card) and secret patterns
(API keys, tokens) and replaces with `[REDACTED]`. Integrated into `logging.py` and
`errors.py` automatically. Prevents: accidental PII in log aggregators, tokens in error
messages, SOC 2 and GDPR violations from leaky logging.

**OSS ★:** custom rules + regex; OTel semantic conventions (partial)

**Minimal:** `YES — Tier A (can start as simple regex in logging.py; extract when PII rules grow complex)`

---

## tier1_runtime — Request-Level Safety

---

### `context.py`
**Path:** `platform_sdk.tier1_runtime.context`
**Purpose:** Request/correlation IDs, principal context (propagated from identity, not re-authenticated here), propagation into logs/metrics/traces.

**Description:**
Python `contextvars`-based request context. Stores `request_id`, `trace_id`, `principal_id`,
and `org_id` for the duration of a request. Automatically propagated into all log records,
metric labels, and trace spans via middleware. Context is propagated across async boundaries.
Prevents: correlation IDs lost in async code, principal context re-queried on every call,
missing context in downstream log entries.

**Consumer:** OTel context; framework middleware
**Enterprise:** platform context SDK; service-mesh headers
**OSS ★:** OpenTelemetry context API + Python contextvars

**Minimal:** `YES — Tier A`

---

### `validate.py`
**Path:** `platform_sdk.tier1_runtime.validate`
**Purpose:** Input/schema validation, contract enforcement, safe error surfaces.

**Description:**
Pydantic v2 based validation entry point. Provides `validate_input(model, data)` that
raises a standardized `ValidationError` (from `errors.py`) with field-level detail.
Schema validation for external API inputs. JSON Schema export for contract documentation.
Prevents: raw Pydantic exceptions leaking to users, validation bypassed for "internal"
APIs that later become external, inconsistent error shapes for validation failures.

**Consumer:** Pydantic v2; Zod
**Enterprise:** contract-first APIs; schema governance
**OSS ★:** Pydantic v2

**Minimal:** `YES — Tier A`

---

### `serialize.py`
**Path:** `platform_sdk.tier1_runtime.serialize`
**Purpose:** Stable serialization formats; schema evolution and forward/backward compatibility; versioning rules; canonical JSON; Protobuf support.

**Description:**
Serialization abstraction supporting JSON (via msgspec for performance) and Protobuf.
`serialize(obj, format)` and `deserialize(data, model, format)`. Schema evolution is the
hard part — forwards/backwards compatibility rules enforced via field defaults and
`PLATFORM_SERIALIZE_FORMAT` env var. Prevents: inconsistent JSON serialization (datetime
formats, None vs missing fields), schema breakage between service versions, direct
`json.dumps()` calls without format standardization.

**Consumer:** JSON; Protobuf
**Enterprise:** Protobuf; Avro (if evented)
**OSS ★:** msgspec (fastest Python JSON/MessagePack) + Protobuf

**Minimal:** `YES — Tier B`

---

### `retry.py`
**Path:** `platform_sdk.tier1_runtime.retry`
**Purpose:** Standard retry/backoff/timeout policy; jitter; per-error classification.

**Description:**
Tenacity-backed retry decorator and context manager with standard platform policy:
exponential backoff with jitter, configurable max attempts, per-error-class
classification (retryable vs non-retryable). `@retry_policy()` decorator applies
the standard policy; `@retry_policy(max_attempts=5)` overrides. Prevents: ad-hoc
retry loops, retry storms from missing jitter, retrying non-retryable errors
(e.g., 400 Bad Request).

**Consumer:** Tenacity (py); axios-retry (js)
**Enterprise:** centralized policy in SDK; gateway/client policy controls
**OSS ★:** Tenacity

**Minimal:** `YES — Tier B`

---

### `ratelimit.py`
**Path:** `platform_sdk.tier1_runtime.ratelimit`
**Purpose:** Local and distributed rate limiting; quotas; burst control; abuse protection.

**Description:**
Token bucket algorithm with optional Redis backend for distributed limiting.
`check_rate_limit(key, limit, window)` returns `(allowed, retry_after)`.
Default keys: `ip:<addr>`, `user:<id>`, `org:<id>`, `endpoint:<path>`.
Raises `RateLimitError` (from `errors.py`) with standard headers.
Prevents: abuse/scraping without limits, inconsistent rate limit enforcement
across services, missing `Retry-After` headers.

**Consumer:** Upstash; in-process Redis token bucket
**Enterprise:** Kong/Tyk API gateway built-in quotas; Gubernator (distributed)
**OSS ★:** Redis token bucket; Envoy Rate Limit

**Minimal:** `YES — Tier B`

---

### `clock.py`
**Path:** `platform_sdk.tier1_runtime.clock`
**Purpose:** Mockable time source; monotonic vs wall time; consistent timezone handling.

**Description:**
Thin wrapper over `datetime` that enables time-mocking in tests. `now()` returns
UTC datetime. `monotonic()` returns monotonic time for duration measurements.
All timezone handling normalized to UTC at the boundary. Prevents: `datetime.now()`
(no timezone) vs `datetime.utcnow()` confusion, untestable time-dependent code,
timezone bugs from mixing aware/naive datetimes.

**OSS ★:** stdlib datetime + Freezegun (tests only)

**Minimal:** `DEFERRED — use stdlib directly; extract when time-dependent code becomes painful to test`

---

### `runtime.py`
**Path:** `platform_sdk.tier1_runtime.runtime`
**Purpose:** Env detection, build/version metadata, feature compatibility gates, diagnostics.

**Description:**
Exposes `is_production()`, `is_development()`, `get_version()`, `get_build_metadata()`.
Version and build info injected at build time via env vars (`APP_VERSION`, `APP_BUILD`).
Feature compatibility gates allow modules to behave differently based on runtime env.
Prevents: `os.getenv("ENV") == "prod"` scattered throughout code, inconsistent env
detection, version info unavailable in error reports.

**OSS ★:** custom env detection; no external dep needed

**Minimal:** `DEFERRED — nice to have; add when debugging env-specific issues`

---

### `middleware.py`
**Path:** `platform_sdk.tier1_runtime.middleware`
**Purpose:** Shared middleware wiring for common frameworks — context injection, auth verification, logging correlation, tracing propagation.

**Description:**
Framework-agnostic middleware factory that wires context.py, identity.py, logging.py,
and tracing.py into a single middleware stack. `create_middleware(app, framework)` returns
middleware for FastAPI/Starlette/Flask that: extracts/generates request IDs, verifies
auth tokens (optional), injects context, logs request/response, and propagates trace
context. Prevents: each service hand-wiring the same 5 middleware pieces inconsistently.

**OSS ★:** framework-native (FastAPI/Starlette/Flask)

**Minimal:** `DEFERRED — add when 2+ services need consistent cross-cutting middleware`

---

## tier2_reliability — Production Operations

---

### `health.py`
**Path:** `platform_sdk.tier2_reliability.health`
**Purpose:** Liveness/readiness endpoints; dependency checks; degradations surfaced.

**Description:**
`HealthChecker` registry where modules register their health checks. `/health/live`
returns 200 if the process is alive. `/health/ready` runs all registered checks
(DB connection, Redis ping, etc.) and returns 200 only if all pass, or 503 with
detail of failed checks. Checks can be marked `critical` (blocks readiness) or
`informational` (reported but not blocking). Required by K8s, ECS, and load balancers.
Prevents: K8s routing traffic to an unhealthy pod, silent dependency failures.

**Consumer:** /healthz + shallow checks
**Enterprise:** readiness + dependency probing; compliance-aware checks
**OSS ★:** custom /healthz pattern (no dep needed)

**Minimal:** `YES — Tier A`

---

### `audit.py`
**Path:** `platform_sdk.tier2_reliability.audit`
**Purpose:** Append-only audit trail; tamper-evidence; actor/action/resource records.

**Description:**
Structured audit log writer. Every audit record contains: `timestamp`, `actor_id`,
`actor_org_id`, `action`, `resource_type`, `resource_id`, `outcome`, `metadata`.
Written to an append-only store (DB table with no UPDATE/DELETE grants, or log stream).
GDPR Article 30 requires records of processing activities. SOC 2 processing integrity
requires this from day one. Prevents: no audit trail at compliance review time,
retroactively trying to reconstruct who did what from application logs.

**Consumer:** append-only DB table; immutable log file
**Enterprise:** SIEM pipeline; WORM retention (Splunk, AWS CloudTrail)
**OSS ★:** structlog → Grafana Loki (with retention policies)

**Minimal:** `YES — Tier A`

---

### `cache.py`
**Path:** `platform_sdk.tier2_reliability.cache`
**Purpose:** Cache interface (local/redis), TTL strategy, stampede protection, invalidation patterns. Also handles semantic caching for LLM responses.

**Description:**
`get_cache()` returns a cache client backed by in-memory dict (dev) or Redis (prod).
`cache.get(key)`, `cache.set(key, value, ttl)`, `cache.delete(key)`, `cache.get_or_set(key, fn, ttl)`.
`get_or_set` implements stampede protection (mutex on cache miss). Semantic caching for
LLM responses (via LiteLLM integration) available via `semantic_cache`. Prevents: every
service rolling its own cache layer, cache stampedes under load, no TTL discipline.

**Consumer:** Redis; local LRU
**Enterprise:** managed Redis; multi-tenant cache policies
**OSS ★:** Redis

**Minimal:** `YES — Tier B`

---

### `circuit.py`
**Path:** `platform_sdk.tier2_reliability.circuit`
**Purpose:** Circuit breaker and bulkhead; failure thresholds; fallback strategy.

**Description:**
Circuit breaker state machine (closed → open → half-open) with configurable
failure threshold, timeout, and fallback. `@circuit_breaker(name, fallback)` decorator.
Bulkhead pattern for isolating downstream failures. Prevents: cascading failures
when a downstream service degrades, retry storms amplifying outages.

**Consumer:** simple counters/time windows
**Enterprise:** proxy/service-mesh policies; central reliability policy
**OSS ★:** custom implementation; Resilience4j pattern; Envoy (at mesh layer)

**Minimal:** `DEFERRED — add after first cascading failure from a downstream dependency`

---

### `storage.py`
**Path:** `platform_sdk.tier2_reliability.storage`
**Purpose:** Blob/file abstraction; signed URLs; retention; content-type and integrity checks.

**Description:**
S3-compatible blob storage abstraction. `upload(key, data, content_type)`,
`download(key)`, `get_signed_url(key, expiry)`, `delete(key)`. Backend is
MinIO (local/self-hosted) or S3/GCS/Azure Blob (cloud). Content-type validation
and hash verification on upload. Prevents: raw boto3/gcs SDK calls in business
logic, unsigned URLs exposing private files, missing integrity checks on upload.

**Consumer:** Supabase Storage; S3-compatible providers
**Enterprise:** AWS S3; GCS/Azure Blob
**OSS ★:** MinIO (S3-compatible, self-hosted)

**Minimal:** `DEFERRED — add when you need to store user-uploaded files or generated artifacts`

---

### `crypto.py`
**Path:** `platform_sdk.tier2_reliability.crypto`
**Purpose:** Safe crypto primitives; key management integration; signing/verifying helpers.

**Description:**
High-level crypto operations using libsodium (PyNaCl) — safe defaults prevent footguns.
`encrypt(data, key)`, `decrypt(data, key)`, `sign(data, private_key)`,
`verify(data, signature, public_key)`, `hash_password(password)`, `verify_password(hash, password)`.
Key management integrated with `secrets.py`. Prevents: custom crypto implementations,
insecure key storage, MD5/SHA1 for password hashing.

**Consumer:** PyNaCl/libsodium; OS crypto APIs
**Enterprise:** AWS KMS; HSM-backed key services
**OSS ★:** PyNaCl/libsodium

**Minimal:** `DEFERRED — add when you need at-rest encryption for PII or signing operations`

---

### `fallback.py`
**Path:** `platform_sdk.tier2_reliability.fallback`
**Purpose:** Standardized fallback behavior (cached response, degraded mode) to prevent ad-hoc degradation hacks.

**Description:**
`FallbackChain` — ordered list of strategies tried in sequence on failure. Built-in
strategies: `CachedFallback` (return last known good), `DefaultFallback` (static value),
`DegradedFallback` (reduced functionality response). Prevents: every feature hand-coding
its own "if upstream fails, return X" logic, inconsistent degraded-mode UX.

**OSS ★:** custom implementation

**Minimal:** `DEFERRED — add after you've identified recurring degradation patterns worth standardizing`

---

## tier3_platform — Cross-Service Patterns

---

### `authorization.py`
**Path:** `platform_sdk.tier3_platform.authorization`
**Purpose:** Fine-grained resource-level permissions — who can do X on resource Y. RBAC/ABAC; relationship-based access control.

**Description:**
Relationship-based access control following the Google Zanzibar model. `can(principal, action, resource)`
returns bool. `require_permission(action, resource)` raises `AuthError` if denied.
Backend is SpiceDB for production (distributed, built-in audit and debugging) or a
simple in-memory RBAC for dev/tests. Distinct from `policy.py`: this is per-resource
decisions; policy.py is cross-cutting system-wide rules. Prevents: ad-hoc `if user.role == "admin"`
checks scattered through business logic, permission checks bypassed in internal APIs.

**Consumer:** simple role checks
**Enterprise:** centralized authz service; Zanzibar-model at scale
**OSS ★:** SpiceDB (Zanzibar, distributed, built-in audit + debugging); Casbin (embedded, lightweight)

**Minimal:** `YES — Tier A`

---

### `notifications.py`
**Path:** `platform_sdk.tier3_platform.notifications`
**Purpose:** Multi-channel notification delivery — email, SMS, push, in-app, Slack, webhook. Template management; delivery status tracking; user preferences.

**Description:**
`send_notification(recipient, template, channel, data)` sends across any configured
channel. Templates stored and versioned in Novu. User notification preferences
respected automatically. Delivery status tracked (sent/delivered/failed).
Unsubscribe handling built in (CAN-SPAM/GDPR compliant). Prevents: transactional
email sent via raw SMTP with no tracking, duplicate notification sends, ignoring
user unsubscribe preferences, no delivery audit trail.

**Consumer:** Resend (transactional email); OneSignal (push)
**Enterprise:** Amazon SES + SNS; Twilio; internal pipelines
**OSS ★:** Novu (MIT, 37k+ GitHub stars, multi-channel, self-hosted or cloud)

**Minimal:** `YES — Tier A`

---

### `api_client.py`
**Path:** `platform_sdk.tier3_platform.api_client`
**Purpose:** Standard HTTP/gRPC client wrapper; auth injection; retries; timeouts; telemetry.

**Description:**
HTTPX-based client factory with automatic: auth token injection from `identity.py`,
retry policy from `retry.py`, timeout defaults, OTel span creation per request,
response deserialization via `serialize.py`, and standardized error mapping.
`get_client(service_name)` returns a configured client. Prevents: each service
hand-building HTTP clients with inconsistent auth/retry/timeout behavior.

**Consumer:** HTTPX wrappers; Axios wrapper
**Enterprise:** shared client SDK; gateway-based clients
**OSS ★:** HTTPX + OpenTelemetry instrumentation

**Minimal:** `DEFERRED — add when service-to-service calls need consistent auth/retry/telemetry`

---

### `discovery.py`
**Path:** `platform_sdk.tier3_platform.discovery`
**Purpose:** Resolve service endpoints; environment routing; failover rules.

**Description:**
Service endpoint resolution abstracted from call sites. `get_endpoint(service_name)`
returns the correct URL for the current environment. Backend: static config dict
(dev), etcd (Kubernetes), Consul (multi-cloud). Prevents: hardcoded service URLs,
environment-specific URL logic in business code, endpoint changes requiring
code deployments.

**Consumer:** static config/URLs
**Enterprise:** service discovery (Consul/Eureka/etc.); mesh DNS
**OSS ★:** etcd (Kubernetes-native); Consul (multi-cloud + health checks)

**Minimal:** `DEFERRED — add when you have 5+ services and static config becomes unwieldy`

---

### `policy.py`
**Path:** `platform_sdk.tier3_platform.policy`
**Purpose:** System-wide compliance rules crossing service boundaries — cost limits, geographic restrictions, regulatory constraints, quota enforcement; policy-as-code; explain decisions.

**Description:**
OPA (Open Policy Agent) integration for cross-cutting system policy. Distinct from
`authorization.py` (per-resource permissions): this enforces rules like "no EU user
data may be processed outside EU regions", "free tier orgs may not exceed 1000 API
calls/day", "feature X is unavailable in country Y". `evaluate_policy(policy_name, input)`
returns decision with explanation. Prevents: compliance rules implemented as ad-hoc
if-statements in business logic, policy drift across services.

**Consumer:** simple rule engine
**Enterprise:** policy-as-code enforcement; automated compliance reporting
**OSS ★:** OPA (Open Policy Agent, stateless, high-perf); Cedar (AWS, structured)

**Minimal:** `DEFERRED — add when compliance requirements demand policy-as-code (SOC 2 audit)`

---

### `experiments.py`
**Path:** `platform_sdk.tier3_platform.experiments`
**Purpose:** Experimentation API; bucketing; assignment persistence; metrics linkage. Works alongside evals.py — experiments answer "do users prefer it?", evals answer "can the model do it?". Both are needed.

**Description:**
A/B test and multi-variate experiment management. `get_assignment(experiment, user_id)`
returns stable variant assignment (same user always gets same variant). Assignments
persisted for analytics linkage. Metrics events linked to experiment assignments for
significance analysis. GrowthBook backend with MCP server support for agent-driven
experiments. Prevents: ad-hoc feature flag misuse as experiments, no statistical
significance measurement, experiment results unlinked to user metrics.

**Consumer:** GrowthBook OSS; PostHog
**Enterprise:** Split; LaunchDarkly experiments
**OSS ★:** GrowthBook (OSS, MCP server support, offline+online A/B); PostHog

**Minimal:** `DEFERRED — add post-launch when optimizing funnels or AI output quality`

---

### `vector.py`
**Path:** `platform_sdk.tier3_platform.vector`
**Purpose:** Vector store abstraction for embeddings/RAG; similarity search with metadata filtering; index lifecycle management; hybrid search (vector + keyword).

**Description:**
Abstraction over vector databases for embedding storage and similarity retrieval.
`upsert(collection, id, vector, metadata)`, `search(collection, query_vector, top_k, filter)`,
`delete(collection, id)`. Hybrid search (vector + keyword) available where backend supports.
Backend: Qdrant (prod), in-memory (dev/test). Part of the GenAI minimal stack because
RAG is now table stakes for AI applications. Prevents: each AI feature implementing
its own embedding storage, vendor lock-in on vector DB, inconsistent similarity
search semantics.

**Consumer:** Pinecone; Supabase pgvector
**Enterprise:** Weaviate Enterprise; Azure AI Search
**OSS ★:** Qdrant (Rust, ACID, high-perf, horizontal scaling); Weaviate (hybrid vector + knowledge graph); pgvector (stays in Postgres)

**Minimal:** `YES — Tier C (GenAI)`

---

### `agent.py`
**Path:** `platform_sdk.tier3_platform.agent`
**Purpose:** Agent identity and service accounts; resource quotas (token budgets, compute limits); structured audit trail of agent decisions; RBAC for agent capabilities; agent lifecycle management.

**Description:**
Agents are first-class platform citizens, not apps that happen to call APIs.
`register_agent(name, capabilities)` provisions agent identity (service account in Zitadel).
`check_agent_quota(agent_id, resource_type)` enforces token/compute budgets.
`audit_agent_decision(agent_id, action, reasoning, outcome)` records decisions.
`authorize_capability(agent_id, capability)` gates what an agent is allowed to do.
Prevents: agents with no identity (invisible in audit logs), agents with uncapped
token spend, unauthorized agent capability escalation.

**Consumer:** custom agent identity layer
**Enterprise:** platform agent governance SDK; internal agent registry
**OSS ★:** Zitadel (identity + service accounts) + OPA (capability policy) + OTel (decision audit)

**Minimal:** `DEFERRED — add when agents graduate from experimental to production platform citizens`

---

### `multi_tenancy.py`
**Path:** `platform_sdk.tier3_platform.multi_tenancy`
**Purpose:** Tenant isolation; per-tenant config and limits; data partitioning rules; tenant-aware middleware; cross-tenant access prevention.

**Description:**
Tenant context propagated throughout the request lifecycle. `get_current_tenant()`
returns the active tenant from context. `tenant_scope(query)` automatically adds
tenant filter to all DB queries. Per-tenant config overrides (rate limits, feature
flags, quotas). Cross-tenant data access raises `AuthError` automatically.
Prevents: data leakage between tenants, one tenant's configuration affecting another,
missing tenant filter in DB queries (catastrophic data exposure).

**Consumer:** simple org/workspace model
**Enterprise:** strict tenant isolation; compliance boundaries; WORM per tenant
**OSS ★:** Zitadel (org model) + SpiceDB (tenant isolation policy)

**Minimal:** `DEFERRED — add when first enterprise customer requires data isolation`

---

### `clients/`
**Path:** `platform_sdk.tier3_platform.clients`
**Purpose:** Typed clients for internal/external APIs using api_client.py conventions.

**Description:**
Directory of generated or hand-written typed clients for specific services,
all built on `api_client.py`. Each client file is one external/internal service.
See `clients/README.md` for generation rules and versioning policy.

**Minimal:** `DEFERRED — add clients as services are integrated`

---

## tier4_advanced — Add Only When Needed

---

### `workflow.py`
**Path:** `platform_sdk.tier4_advanced.workflow`
**Purpose:** Long-running workflows; durable state; retries; compensation. For AI: multi-step agent pipelines with human-in-the-loop, branching, and guaranteed execution.

**Description:**
Temporal-backed durable workflow execution. `@workflow_definition` decorator marks
a class as a workflow. `start_workflow(name, input)` returns a handle. Workflows
survive process restarts. Human-in-the-loop via `wait_for_signal()`. Compensation
(saga pattern) via `compensate()`. For AI workloads: Prefect available for
dynamic/iterative ML workflows where Temporal's determinism is too strict.
Prevents: long-running processes lost on restart, no compensation on partial failure,
multi-step agent pipelines with no visibility.

**Consumer:** simple job chains; Prefect (dynamic/iterative)
**Enterprise:** Temporal; AWS Step Functions
**OSS ★:** Temporal (OSS core, durable, deterministic); Prefect (ML/AI iteration, dynamic branching); Dagster (data asset-first, lineage + governance)

**Minimal:** `DEFERRED — add when you need multi-step orchestration with compensation logic`

---

### `messaging.py`
**Path:** `platform_sdk.tier4_advanced.messaging`
**Purpose:** Queues/pubsub/streams; delivery semantics; dead-letter; retries; ordering.

**Description:**
Redpanda/Kafka abstraction for event streaming. `publish(topic, event)`,
`subscribe(topic, handler)`. Delivery semantics configurable (at-least-once,
exactly-once where supported). Dead-letter queue per topic. Consumer group
management. Prevents: point-to-point HTTP calls for events that should be async,
message loss with no dead-letter, ordering violations in event streams.

**Consumer:** managed queues (SQS-like); lightweight pubsub
**Enterprise:** Kafka; managed pub/sub platforms
**OSS ★:** Redpanda (Kafka-compatible, C++, no JVM/ZooKeeper, lower latency); RabbitMQ (simple queues, easier ops); Kafka (if you need the full ecosystem)

**Minimal:** `DEFERRED — add when you need event-driven communication between services`

---

### `schemas.py`
**Path:** `platform_sdk.tier4_advanced.schemas`
**Purpose:** Data contracts; schema evolution and compatibility checks; registry integration. Tightly coupled to messaging.py — schema registry only matters with event streams.

**Description:**
Schema registry client for registering, versioning, and compatibility-checking
event schemas. `register_schema(topic, schema)`, `validate_against_registry(topic, data)`,
`check_compatibility(topic, new_schema)`. Backed by Karapace (Apache 2.0, Confluent-API-
compatible) or Apicurio (multi-format). Prevents: schema breakage silently corrupting
event streams, producers/consumers out of sync on schema version.

**Consumer:** JSON Schema docs + tests
**Enterprise:** Schema Registry + compatibility gates
**OSS ★:** Karapace (Apache 2.0, drop-in Confluent replacement); Apicurio (multi-format: Avro/Protobuf/JSON Schema/AsyncAPI/OpenAPI)

**Minimal:** `DEFERRED — add when messaging.py needs schema evolution contracts`

---

### `inference.py`
**Path:** `platform_sdk.tier4_advanced.inference`
**Purpose:** LLM/model inference client; provider routing and fallback (100+ models); rate limiting; cost tracking; semantic caching hooks; eval integration.

**Description:**
LiteLLM-backed unified inference client. `complete(messages, model, options)` works
across OpenAI, Anthropic, Gemini, local Ollama, and 100+ other providers with the same
interface. Provider fallback chain configurable via env. Semantic caching hooks plugged
into `cache.py`. Cost per call tracked and emitted as metrics. Eval hooks fire for
`llm_obs.py`. 8ms P95 latency overhead at 1k RPS. Prevents: direct provider SDK calls,
no fallback on provider outage, uncapped token spend, inconsistent model parameters
across the codebase.

**Consumer:** hosted model APIs (OpenAI, Anthropic, Gemini)
**Enterprise:** internal model gateway; managed AI platforms
**OSS ★:** LiteLLM (unified interface, cost tracking, fallback, 470k+ weekly downloads); Ollama (local inference, model management); vLLM (high-perf GPU serving, PagedAttention)

**Minimal:** `YES — Tier C (GenAI)`

---

### `llm_obs.py`
**Path:** `platform_sdk.tier4_advanced.llm_obs`
**Purpose:** LLM-specific observability distinct from general tracing — token usage and cost per call, latency per model/prompt, prompt versioning, multi-turn conversation tracing, hallucination signals, eval result storage.

**Description:**
Langfuse-backed LLM observability. Automatically captures all `inference.py` calls:
trace per conversation, span per LLM call, token count, cost, latency, model version,
prompt template version. Prompt versioning with playground. Eval results stored and
linked to traces. Cost dashboards. This is NOT a replacement for `tracing.py` (which
handles distributed service tracing) — it is the LLM-specific layer on top.
Without this you are flying blind on cost and quality. Most teams that skip it
overspend within the first month of production AI traffic.

**Consumer:** Langfuse Cloud; Helicone
**Enterprise:** Langfuse self-hosted; Arize AI
**OSS ★:** Langfuse (MIT, 19k+ GitHub stars, prompt versioning, evals, cost tracking); Arize Phoenix (OTel-native, 7.8k+ stars); OpenLLMetry/Traceloop (vendor-neutral, plugs into existing APM)

**Minimal:** `YES — Tier C (GenAI)`

---

### `evals.py`
**Path:** `platform_sdk.tier4_advanced.evals`
**Purpose:** LLM output evaluation — semantic accuracy, hallucination detection, task completion, factuality, safety; LLM-as-judge scoring. Offline evals in CI/CD + online integration with experiments.py.

**Description:**
DeepEval and Langfuse evals integration. `run_eval(output, expected, metrics)` runs
LLM-as-judge evaluation across configured metrics (hallucination, answer relevancy,
contextual precision, task completion). Results stored in `llm_obs.py`. CI/CD integration
via pytest plugin. Online evals sampled from production traffic. `experiments.py` links
eval results to A/B assignment for AI experiments. Prevents: shipping LLM features
with no quality measurement, hallucination going undetected in production, no baseline
to compare prompt improvements against.

**Consumer:** Langfuse evals; Braintrust
**Enterprise:** custom eval pipelines; Arize AI
**OSS ★:** DeepEval (pytest-like, research-backed, G-Eval/hallucination metrics); Langfuse evals (integrated with llm_obs.py); Arize Phoenix evals (OTel-native)

**Minimal:** `DEFERRED — add post-launch when measuring and improving AI output quality`

---

### `cost.py`
**Path:** `platform_sdk.tier4_advanced.cost`
**Purpose:** Usage metering; budgets; quotas; unit economics attribution; LLM token cost tracking. Unified view of infra cost (OpenCost) and AI cost (llm_obs.py).

**Description:**
OpenCost + Prometheus based cost attribution. `record_usage(resource, quantity, unit, org_id)`
meters any resource. Budget enforcement: `check_budget(org_id, resource)` raises when
over budget. Unit economics: cost per user/request/token attributed to org/team.
LLM token costs from `llm_obs.py` unified with infrastructure costs in one dashboard.
Prevents: no visibility into cost per customer, overspend discovered at month-end bill,
no per-team chargeback for enterprise.

**Consumer:** simple counters + dashboards
**Enterprise:** FinOps tooling + tagging; internal chargeback
**OSS ★:** OpenCost (CNCF incubating, FinOps certified, LLM cost plugins in 2025); Prometheus-based LLM metering

**Minimal:** `DEFERRED — add when LLM spend is large enough to require attribution and budgeting`

---

## Documentation Tools

These are not Python modules — they are the tooling stack for documenting the SDK and applications built on it.

---

### API Reference Generator
**Tool:** MkDocs Material + mkdocstrings
**Purpose:** Auto-generate typed Python API reference from docstrings.

Python-native, zero-friction for a Python SDK. `mkdocstrings` reads module docstrings
and type annotations → generates full API reference pages with cross-links.
`MkDocs Material` wraps it with search, versioning (`mike`), dark mode, and navigation.
Auto-run in CI on every merge to main.

**Config:** `platform_sdk/docs/mkdocs.yml`
**Build:** `mkdocs build` or `mkdocs serve` for local preview

---

### Interactive API Docs
**Tool:** Scalar
**Purpose:** Interactive API docs rendered from OpenAPI spec; code snippet generation in 8+ languages.

Scalar renders an OpenAPI spec into a beautiful interactive explorer with live request
testing and auto-generated client code (Python, TypeScript, Go, curl, etc.). Becoming
the new standard for API docs (Microsoft's default in .NET 9). Replaces Swagger UI for
new projects.

**Config:** Point Scalar at your `openapi.json` endpoint
**Alternative:** Redoc (static/read-only, cleaner for reference-only docs)

---

### Developer Portal / Guides
**Tool:** Docusaurus or Starlight (Astro)
**Purpose:** Narrative docs, guides, tutorials, versioning, developer portal.

| | Docusaurus | Starlight (Astro) |
|---|---|---|
| Versioning | Native | Beta (developing) |
| CSS | Infima (tightly coupled) | Tailwind out-of-box |
| 2025 momentum | Stable, mature | Actively gaining |
| Best for | Large, complex, multi-version | Modern, lighter weight |

For this SDK: **Starlight** recommended (newer, Tailwind-ready, good for SDK docs).

---

### SDK Generator (upgrade path)
**Tool:** Fern
**Purpose:** When you need to generate client SDKs in multiple languages from the OpenAPI/Fern spec.

Fern accepts your API spec and generates idiomatic Python, TypeScript, Go, Java, C# SDKs
with docs included. Auto-publishes to PyPI. OSS core. Add this when platform_sdk needs
to be consumed by non-Python clients.

---

## Stack Reference Card

| Module | Tool | OSS | Consumer ✓ | Enterprise ✓ | Minimal |
|--------|------|-----|-----------|--------------|---------|
| identity | Zitadel | ✓ MIT | ✓ | ✓ | Tier A |
| logging | structlog + Grafana Loki | ✓ | ✓ | ✓ | Tier A |
| errors | Sentry OSS + OTel | ✓ | ✓ | ✓ | Tier A |
| config | pydantic-settings + etcd | ✓ | ✓ | ✓ | Tier A |
| secrets | Infisical / OpenBao | ✓ MIT | ✓ | ✓ | Tier A |
| data | SQLAlchemy + Alembic | ✓ | ✓ | ✓ | Tier A |
| validate | Pydantic v2 | ✓ | ✓ | ✓ | Tier A |
| context | OTel context + contextvars | ✓ | ✓ | ✓ | Tier A |
| health | custom /healthz | ✓ | ✓ | ✓ | Tier A |
| audit | structlog → Grafana Loki | ✓ | ✓ | ✓ | Tier A |
| authorization | SpiceDB | ✓ | ✓ | ✓ | Tier A |
| notifications | Novu | ✓ MIT | ✓ | ✓ | Tier A |
| metrics | Prometheus + Grafana | ✓ | ✓ | ✓ | Tier B |
| retry | Tenacity | ✓ | ✓ | ✓ | Tier B |
| ratelimit | Redis token bucket | ✓ | ✓ | ✓ | Tier B |
| serialize | msgspec + Protobuf | ✓ | ✓ | ✓ | Tier B |
| cache | Redis | ✓ | ✓ | ✓ | Tier B |
| inference | LiteLLM + Ollama | ✓ | ✓ | ✓ | Tier C (GenAI) |
| llm_obs | Langfuse | ✓ MIT | ✓ | ✓ | Tier C (GenAI) |
| vector | Qdrant | ✓ | ✓ | ✓ | Tier C (GenAI) |
| tracing | OTel → Grafana Tempo | ✓ | ✓ | ✓ | Deferred |
| flags | OpenFeature + Unleash | ✓ | ✓ | ✓ | Deferred |
| tasks | Hatchet / Temporal | ✓ | ✓ | ✓ | Deferred |
| http | stdlib | ✓ | ✓ | ✓ | Deferred |
| ids | uuid7 / python-ulid | ✓ | ✓ | ✓ | Deferred |
| redact | custom rules | ✓ | ✓ | ✓ | Deferred |
| clock | stdlib + Freezegun | ✓ | ✓ | ✓ | Deferred |
| runtime | custom | ✓ | ✓ | ✓ | Deferred |
| middleware | framework-native | ✓ | ✓ | ✓ | Deferred |
| circuit | custom | ✓ | ✓ | ✓ | Deferred |
| storage | MinIO | ✓ | ✓ | ✓ | Deferred |
| crypto | PyNaCl/libsodium | ✓ | ✓ | ✓ | Deferred |
| fallback | custom | ✓ | ✓ | ✓ | Deferred |
| api_client | HTTPX + OTel | ✓ | ✓ | ✓ | Deferred |
| discovery | etcd / Consul | ✓ | ✓ | ✓ | Deferred |
| policy | OPA | ✓ | ✓ | ✓ | Deferred |
| experiments | GrowthBook | ✓ | ✓ | ✓ | Deferred |
| agent | Zitadel + OPA + OTel | ✓ | ✓ | ✓ | Deferred |
| multi_tenancy | Zitadel + SpiceDB | ✓ | ✓ | ✓ | Deferred |
| workflow | Temporal | ✓ | ✓ | ✓ | Deferred |
| messaging | Redpanda | ✓ | ✓ | ✓ | Deferred |
| schemas | Karapace / Apicurio | ✓ | ✓ | ✓ | Deferred |
| evals | DeepEval + Langfuse | ✓ | ✓ | ✓ | Deferred |
| cost | OpenCost + Prometheus | ✓ | ✓ | ✓ | Deferred |
| **Docs (API ref)** | MkDocs + mkdocstrings | ✓ | ✓ | ✓ | — |
| **Docs (interactive)** | Scalar | ✓ | ✓ | ✓ | — |
| **Docs (portal)** | Starlight / Docusaurus | ✓ | ✓ | ✓ | — |

**100% open-source. No proprietary dependencies required at any tier.**
