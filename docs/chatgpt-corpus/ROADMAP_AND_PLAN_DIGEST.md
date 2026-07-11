# Roadmap And Plan Digest

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

| File | Document Date | Purpose | Currency | Completed Items | Remaining Items | Notes |
|---|---|---|---|---|---|---|
| `docs/SPRINT_1C_PLAN.md` | 2026-05-26 | Sprint 1C queue/worker/readiness plan | current-ish | PostgreSQL tests, ownership, lock claim, worker skeleton, reserved recovery, readiness/preflight | submitted/running recovery, progress persistence, output collection, benchmark runner | Best planning doc after code, but phase naming drift exists |
| `docs/UI_MVP_STATUS.md` | undated, post-UI | UI run/status doc | current | React pages, integrated endpoints, disabled generation state | frontend build unverified here; no public generation | Best UI status doc |
| `README.md` | undated | repo overview/setup | stale | setup commands still useful | status says Sprint 1A and no polished frontend, now false | Do not use for current implementation status |
| `frontend/README.md` | post-UI | frontend run/build scope | current-ish | documents dashboard scope and disabled generation | build requires `npm install` | Accurate for UI intent |
| `docs/API_CONTRACT.md` | Sprint 1A | endpoint contract | stale | some endpoint list still valid | says project/campaign/job are stubs, now DB-backed | Superseded by code/UI status |
| `docs/POSTGRES_VERIFICATION.md` | Sprint 1C Slice 1 | PostgreSQL test setup | partially stale | env var/testing guidance useful | pending list says locking/ownership not implemented, now implemented | Keep command guidance only |
| `docs/SPRINT_1B_CLOSEOUT.md` | 2026-05-26 | Sprint 1B closeout | historical | accurate for Sprint 1B | limitations now partly resolved | Historical source |
| `docs/SPRINT_1A_STATUS.md` | Sprint 1A | Sprint 1A status | historical/stale | useful history | routes/frontend claims stale | Historical only |
| `docs/QUEUE_STATE_MACHINE.md` | undated | queue lifecycle | partially current | active flow/failures still relevant | omits recovery transitions and validating state nuance | Code is canonical |
| `Architecture/ARCHITECTURE_BLUEPRINT.md` | research packet | architecture vision | current as vision | safety/invariants remain useful | not implementation status | Use as architecture reference |
| `MVP/MVP_ARCHITECTURE.md` | research packet | MVP design | current as vision | component choices align | not implementation status | Use for target behavior |
| `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md` | research packet | runtime/queue policy | current as vision | single GPU, external Comfy, queue states | not implementation status | Source for safety invariants |
| `Benchmarks/BENCHMARK_PROTOCOL.md` | research packet | benchmark protocol | current as target | JSONL/gates partially implemented | real runner absent | Use before benchmark work |
| `Risk-Register/RISK_REGISTER.md` | research packet | risk inventory | current as risk source | many mitigations represented in code | risks not all retired | Keep alive |

## Contradictions

- `README.md` and `docs/API_CONTRACT.md` understate current implementation by saying Sprint 1A/stubs/no polished frontend.
- `docs/POSTGRES_VERIFICATION.md` says worker locking/recovery pending, but code implements lock claim and reserved recovery.
- `docs/SPRINT_1C_PLAN.md` still contains historical goals requiring submitted/running recovery; the latest status line explicitly says only reserved-job policy is complete and submitted/running remains future.

## Canonical Next-Step Sequence

1. Re-enable disposable PostgreSQL container and rerun PostgreSQL-gated queue/schema tests.
2. Implement progress persistence/history/output collection planning behind worker boundary.
3. Add submitted/running conservative recovery policy before real recurring worker.
4. Add real worker loop only after recovery/progress/output paths are safe.
5. Add benchmark runner orchestration before any production preset promotion.
