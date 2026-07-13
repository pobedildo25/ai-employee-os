# Decision Contract — NOVA

## Sole owner

**Executive** is the only component that accepts a Product Decision.

Allowed decisions:

`RESPOND` | `ASK_CLARIFICATION` | `EXECUTE` | `CREATE_PLAN`

No other layer may invent, mutate, or substitute a Product Decision.

## Who does **not** decide

| Component | Role |
|-----------|------|
| Runtime | Executes an already accepted decision |
| Telegram / any channel | Map / send / UI only |
| Planner | Builds a plan only after `CREATE_PLAN` |
| Capability Resolver | Builds / orders capability graph after `EXECUTE` / `CREATE_PLAN` (owns final list; Executive hints are soft) |
| Orchestrator | Runs DAG steps / statuses only |
| Context Builder | Aggregates context; never changes request meaning |
| Skills | Independent capabilities; no product routing |
| Learning | Preferences only; never DecisionType |

## Forbidden decision paths

- Keyword / regex routing of intent.
- Document-type / extension routing (`document_type` → special branch).
- Adapter-side Revision ↔ New Task switches.
- Runtime mutating `DecisionType` or starting Planner on its own.

## Runtime invariants (summary)

Runtime **must not**:

- change `DecisionType`;
- start Planner by itself;
- build a capability pipeline instead of Capability Resolver;
- turn Revision into New Task (or the reverse);
- turn `RESPOND` into `EXECUTE`;
- turn `EXECUTE` into `CREATE_PLAN` (or the reverse without an explicit demotion policy for an already accepted `CREATE_PLAN`).

See `docs/PRODUCT_GOAL.md` §3–§4 for the full invariant table.

## Decision eval honesty

Catalog / fixture scenario tests (e.g. `test_executive_decision_scenarios.py`) exercise
routing policies with fixture decisions. They are **not** live LLM proof of Executive quality.

Live spot-eval harness: `tests/test_executive_live_eval.py` (marked `@pytest.mark.live`).
Skipped unless `LIVE_EXECUTIVE_EVAL=1` and `OPENROUTER_API_KEY` are set. Opt-in only —
passing CI with the harness skipped does **not** prove live Executive quality.
