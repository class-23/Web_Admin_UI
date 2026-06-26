# ADR-0001: Architecture Unification via Seam Convergence

- **Status**: Accepted (Phase-1)
- **Date**: 2026-06-26
- **Deciders**: Cloud (architect), Project Owner
- **Supersedes**: —
- **Related**: CONTEXT.md

---

## 1. Context

The repo currently contains **two parallel subsystems** that overlap and have drifted:

| Dimension | Legacy surface | Canonical target |
|---|---|---|
| App entry | `main.py` | `app/app_factory.py` |
| Device management | `quantclaw_receiver/` (root) | `app/utils/quantclaw_receiver/` |
| Auth | `login/` package (psycopg2 + cookie) | `app/services/auth_service.py` + `app/routers/auth.py` (SQLAlchemy + JWT) |
| DB access | `login/database.py` (psycopg2 pool, raw SQL) | `app/core/database.py` (SQLAlchemy 2.x) |
| Settings | `login/config.py` (`os.getenv`) | `app/core/config.py` (`pydantic-settings`) |
| Models | implicit (raw SQL) | `app/models/*.py` (ORM) |
| Schemas | `login/schemas.py` | `app/schemas/*.py` |

### Evidence of drift

SHA-256 comparison of `quantclaw_receiver/*.py` (root) vs `app/utils/quantclaw_receiver/*.py`:

| File | Hash equal? |
|---|---|
| `__init__.py` | ✅ identical |
| `exceptions.py` | ✅ identical |
| `config.py` | ❌ different (legacy has `pg_*`, canonical has `db_path`) |
| `database.py` | ❌ different |
| `device_manager.py` | ❌ different (canonical `__init__` requires `session_factory`) |
| `udp_receiver.py` | ❌ different |
| `utils.py` | ❌ different |

### Why now

- New contributors can't tell which surface is canonical.
- Bug fixes applied to one path don't reach the other → silent regressions.
- Tests diverge (`test_main_*` vs `test_quantclaw_*`) so coverage claims are misleading.
- Migrations are split between raw `DO $$ ... ALTER ...` blocks and SQLAlchemy `create_all`.

## 2. Decision

We adopt a **phased seam convergence** strategy: the canonical target is `app/`; legacy surfaces stay functional but are marked and routed through thin seams until they can be deleted. **No business logic is rewritten in Phase-1.**

### Single Source of Truth (SoT) assignments

| Concern | Canonical SoT | Legacy bridge |
|---|---|---|
| `QuantClawDeviceManager` impl | `app/utils/quantclaw_receiver/device_manager.py` | root `quantclaw_receiver/device_manager.py` (deprecated, kept working) |
| `DatabaseManager` impl | `app/utils/quantclaw_receiver/database.py` | root `quantclaw_receiver/database.py` (deprecated) |
| `QuantClawConfig` (canonical shape) | `app/utils/quantclaw_receiver/config.py` | root `quantclaw_receiver/config.py` (kept with legacy `pg_*` shape) |
| `UDPBroadcastReceiver` impl | `app/utils/quantclaw_receiver/udp_receiver.py` | root `quantclaw_receiver/udp_receiver.py` (deprecated) |
| Exception classes | `app/utils/quantclaw_receiver/exceptions.py` | re-exported from root (already identical) |
| Utilities | `app/utils/quantclaw_receiver/utils.py` | root `quantclaw_receiver/utils.py` (deprecated) |
| App settings | `app/core/config.py` | `login/config.py` (Phase-1: forwarded) |
| Auth flow | `app/services/auth_service.py` + `app/routers/auth.py` | `login/` package (Phase-2) |
| DB access | `app/core/database.py` (SQLAlchemy) | `login/database.py` (psycopg2; Phase-2) |
| Templates | `templates/*.html` (kebab-case) | duplicates with underscores (Phase-2 cleanup) |

### Phase plan

#### Phase-1 (this PR) — Seam Layer

- Add `CONTEXT.md` + ADR-0000 + ADR-0001 (this file)
- `quantclaw_receiver/exceptions.py` → re-export from canonical (was identical)
- `quantclaw_receiver/*.py` (other 6 files) → mark `DEPRECATED`, keep code, add docstring pointing to canonical + this ADR
- `login/config.py` → re-export all symbols from `app.core.config.settings` (variable forwarding, zero risk)
- No business logic changes
- Tests must still pass (legacy surface unchanged)

#### Phase-2 — Config + Auth Migration

- Migrate `main.py` to use `app.app_factory.create_app()`
- Replace `login/database.py` raw SQL with `app.core.database` SQLAlchemy
- Merge `login/auth.py` + `login/routers/auth_router.py` into `app/services/auth_service.py`
- Delete `login/` package
- Add Alembic for migrations; remove `DO $$` blocks

#### Phase-3 — Device Module Unification

- Migrate `main.py`'s `QuantClawConfig(pg_host=...)` construction to canonical `db_path` form (or accept pg_* as compatibility shim)
- Update `QuantClawDeviceManager` instantiation in `main.py` to provide SQLAlchemy `session_factory`
- Delete root `quantclaw_receiver/` directory

#### Phase-4 — Cleanup

- Delete legacy test files (`test_main_*`, `test_legacy_*`)
- Update README to reflect canonical structure
- Add CI check that asserts no file outside `app/` or `docs/` is imported by production code (enforce SoT)

## 3. Consequences

**Positive**:
- Phase-1 has near-zero risk (only deprecation comments + variable forwarding)
- Drift is **stopped** at the source (no more edits to legacy files); the canonical keeps evolving
- The path to a clean tree is fully documented; each Phase is independently shippable

**Negative / Risks**:
- Temporary duplication still exists in Phase-1; reviewers may push to "just delete it now"
- Phase-3 will require migrating `main.py`'s `QuantClawConfig(pg_host=...)` callsite; this is non-trivial because canonical `DatabaseManager` requires `session_factory`
- If a future engineer reads only `main.py` + legacy `quantclaw_receiver/`, they'll get a wrong mental model → mitigate via CONTEXT.md + prominent deprecation headers

## 4. Alternatives Considered

| Alternative | Why rejected |
|---|---|
| **Big-bang rewrite**: delete legacy, port everything at once | Too risky, no rollback path, would break `main.py` which is the production entry today |
| **Status quo**: ignore the drift | Already causing silent divergence; bug fixes don't propagate |
| **Symbolic link** legacy files to canonical | Loses deprecation signal; hides the boundary |

## 5. Rollback Plan

Each Phase-1 change is independent:
- Removing a deprecation header → no-op revert
- Reverting `login/config.py` to `os.getenv` form → single-file revert
- Reverting `quantclaw_receiver/exceptions.py` re-export → single-file revert

If any Phase-1 self-test fails, abort the Phase and ship only the docs (CONTEXT.md + ADR-0000 + ADR-0001) without code changes.

## 6. Self-Test Matrix (Phase-1 acceptance)

```bash
# A. Seams are importable
python -c "from quantclaw_receiver import QuantClawDeviceManager, QuantClawConfig; print('Seam-OK')"
python -c "from app.utils.quantclaw_receiver import QuantClawDeviceManager; print('Canonical-OK')"

# B. login/config drift eliminated
python -c "from login import config; assert config.PG_HOST; assert config.PG_PORT; print('Login-Config-OK')"

# C. Exceptions canonical
python -c "from quantclaw_receiver.exceptions import QuantClawError; assert QuantClawError.__module__.startswith('app.utils'); print('Exceptions-Canonical-OK')"

# D. Full regression
python -m pytest tests/ -v --tb=short
```

Phase-1 ships when all four pass.

## 7. Reference

- `CONTEXT.md` — domain glossary
- `docs/adr/0000-tech-stack.md` — stack pin
- `MODIFICATIONS_RECORD.md` — historical record of past changes
