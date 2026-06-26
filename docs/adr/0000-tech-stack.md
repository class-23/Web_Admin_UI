# ADR-0000: Tech Stack Pin (2026-Q2)

- **Status**: Accepted
- **Date**: 2026-06-26
- **Deciders**: Cloud (architect), Project Owner
- **Scope**: All Python services in this repo

---

## 1. Context

Project needs a pinned, boring, production-grade Python stack with clear upgrade paths. We avoid bleeding-edge unless there is a concrete reason.

## 2. Decision

| Layer | Choice | Version Pin | Reason |
|---|---|---|---|
| Runtime | Python | `3.11.x` | LTS, matches `FROM python:3.11-slim` in Dockerfile |
| Web framework | FastAPI | `>=0.110,<0.116` | Async, OpenAPI native, type-driven |
| ASGI server | Uvicorn | `>=0.30` | Standard FastAPI runner |
| ORM | SQLAlchemy | `2.0.x` | Modern 2.x style, async-ready |
| Validation | Pydantic | `2.9.x` | Pydantic v2 baseline |
| Settings | pydantic-settings | `>=2.0` | Type-safe env loading |
| Auth (JWT) | python-jose | `>=3.3` | Mature JWT lib |
| Hashing | passlib[bcrypt] + bcrypt 4.0.1 | pinned | Compat with passlib 1.7 |
| Templates | Jinja2 | `>=3.1` | FastAPI native |
| Rate limit | slowapi | `>=0.1.9` | Per-IP login throttle |
| SSH | paramiko | `>=3.4` | Remote file ops |
| DB driver | psycopg2-binary | `>=2.9` | PG driver for SQLAlchemy |
| Cache / queue | redis | `>=5.0` | Optional, used by login.code_store if Redis present |
| Migrations | (deferred) | — | Currently raw `init_db()`; consider Alembic in Phase-2 |
| Container | Docker | python:3.11-slim | Already in repo |

## 3. Consequences

**Positive**:
- Stable, boring, well-supported versions
- No Pydantic v1 → v2 transition debt
- bcrypt pinned to avoid passlib incompatibility (`bcrypt 4.1+` breaks passlib 1.7)

**Negative / Risks**:
- No migration tool; schema drift handled by `DO $$ ... ALTER TABLE ... $$` blocks (current pattern, fragile)
- pydantic-settings 2.x changed API from v1; old code patterns won't apply

## 4. Rejected Alternatives

| Alternative | Why rejected |
|---|---|
| Flask | No native async, weaker type story |
| Django + DRF | Heavier than needed; no async-first |
| Tortoise ORM | Smaller community than SQLAlchemy |
| Pydantic v1 | EOL path; we'd have to migrate eventually |

## 5. Upgrade Strategy

- **Minor**: bump within pin range, run full test suite
- **Major**: open new ADR, do spike branch, do not merge until CI green
- **Security**: critical CVEs backport via patch pin (e.g., `cryptography>=43.0.1`)

## 6. Reference

- `requirements.txt` — production deps
- `requirements-dev.txt` — test/lint deps
- `Dockerfile` — runtime base image
