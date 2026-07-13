# ADR: Research & Semantic Embeddings Stack (L4)

Status: **Accepted — research Sonar wired; semantic still OFF until embeddings.**  
Date: 2026-07-13 (updated same day: Sonar via OpenRouter)  
Related: `PRODUCT_GOAL.md` §14 L4, H2 feature guards, `CAPABILITY_MATRIX.md`

## Context

Product claims market/competitive research and semantic memory, but:

- `research_enabled=False` / `semantic_memory_enabled=False` by default
- Research now has a real backend: **Perplexity Sonar via OpenRouter** (`SonarResearchProvider`)
- Semantic path still uses `stub_embed` until embeddings are implemented
- H2 fail-closes enable without Sonar+OpenRouter key or test escape hatches

## Decision

### Research (web intelligence)

**Chosen (implemented):** Perplexity **Sonar** via existing **OpenRouter** (`RESEARCH_PROVIDER=sonar`, model `perplexity/sonar`).

- Code: `SonarResearchProvider` → OpenRouter chat completions; maps `citations` / `search_results`
- Not a headless browser — grounded web search inside Sonar
- Mock remains for tests (`research_allow_mock=True`)

**Why not alternatives (now):**

| Option | Pros | Cons |
|--------|------|------|
| Stay on Mock | Zero cost | Cannot claim research in product |
| Serper / Brave SERP | Cheap structured hits | Extra vendor + API key |
| Tavily | Agent-oriented | Another vendor; we already pay OpenRouter |
| Pure LLM without Sonar | Simple | Hallucinated sources |
| Browser automation | Deep pages | Ops heavy; not pilot scope |

**Enable rule:** `RESEARCH_ENABLED=true` + `RESEARCH_PROVIDER=sonar` + real `OPENROUTER_API_KEY`. H2 fail-closes otherwise.

### Semantic embeddings

**Chosen:** OpenRouter embeddings endpoint with `openai/text-embedding-3-small` (or current OpenRouter equivalent), dimensions aligned with Qdrant collection (migrate off 64-d stub).

**Why not alternatives (now):**

| Option | Pros | Cons |
|--------|------|------|
| Keep `stub_embed` | Deterministic tests | Useless semantic recall |
| Local sentence-transformers | No API cost | Ops + image size; not pilot |
| OpenAI direct | Mature | Second billing account; we already use OpenRouter |

**Enable rule:** `semantic_memory_enabled=True` only when embeddings provider is implemented and configured; refuse `stub_embed` in prod (H2).

## Cost envelope (order-of-magnitude)

Assumptions: closed pilot ~50 research runs / month, ~5k semantic upserts+queries / month.

| Component | Unit | Estimate |
|-----------|------|----------|
| Serper search | ~$0.001–0.002 / query | N/A — not chosen |
| Sonar via OpenRouter | per-token + search surcharge | Dominant research cost; reuse OpenRouter billing |
| Page fetch | infra only (httpx) | N/A for Sonar path |
| Embeddings (small) | ~$0.02 / 1M tokens | ≪ $5 / mo at pilot volume |
| LLM synthesis (existing OpenRouter) | already budgeted | Second pass after Sonar for structured findings |

**Pilot budget gate:** keep research+embeddings incremental under control via OpenRouter usage dashboards. Revisit before open beta.

## Implementation sequence

1. ~~Sonar research provider via OpenRouter~~ **done** (`SonarResearchProvider`, `RESEARCH_PROVIDER=sonar`)
2. Implement OpenRouter `embeddings()` (today: `NotImplementedError`).
3. Settings for embedding model; drop stub dims in Qdrant when enabling semantic.
4. Staging smoke: `RESEARCH_ENABLED=true` → `strategy_ready=True` with real citations.
5. Flip semantic flag only after embeddings land.

## Non-goals

- Rewriting Runtime / LangGraph
- Enabling research in prompt/registry while still on Mock
- PDF research exports

## Consequences

- Closed pilot stays **flags OFF** until steps 1–4 land.
- Product copy must not claim live web research / semantic memory until flags are on with real backends.
- Tests keep mock/stub via explicit allow flags only.
