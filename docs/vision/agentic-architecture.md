# Vision: Agentic architecture for Chat2DB

**Status:** directional design notes — not a commitment to ship any specific framework.  
**Product name:** Chat2DB (repository: `majidmosadegh/chat2db`)

## Why this document exists

Chat2DB today uses a custom FastAPI chat engine and SQL pipeline with pluggable LLM providers. That design reflects an earlier generation of LLM application architecture: prompt assembly, multi-stage generation, and guarded execution without a general-purpose agent runtime.

The next phase is to evaluate a more **agentic** architecture—one that can plan, call tools, inspect results, refine SQL, and keep humans in control—without pretending that work is already done.

Contributors are invited to challenge, refine, and help select this direction.

## Goals

- Separate **reasoning / planning** from **tool execution** and **SQL safety**.
- Support iterative loops: explore schema → plan → generate SQL → validate → execute (read-only) → observe → refine.
- Preserve inspectability: generated SQL, tool traces, and decisions should be auditable.
- Keep database permissions and destructive-query rejection as hard boundaries, not prompt suggestions.
- Allow framework choices to be evidence-based (prototypes, cost, operability), not marketing-driven.

## Non-goals (for now)

- Declaring LangChain, LangGraph, Hermes, or any other stack as mandatory.
- Adding heavy dependencies solely to improve documentation.
- Claiming production-grade multi-agent reliability before evaluation and tests exist.

## Evaluation candidates

These are **candidates to evaluate**, not adoption decisions:

| Candidate | Why it may be relevant | Open questions |
| --- | --- | --- |
| [LangChain](https://github.com/langchain-ai/langchain) | Broad model/tool integration patterns; large ecosystem | Overhead vs. Chat2DB’s existing `backend/llm` providers; ownership of prompt/tool contracts |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Stateful workflows, checkpoints, controlled orchestration, human-in-the-loop | Fit with current chat session model; persistence story vs. SQLite metadata |
| [Hermes Agent (Nous Research)](https://github.com/NousResearch/hermes-agent) | Agent runtime with tools, memory, and multi-provider LLM support | Overlap vs. product scope (database assistant vs. general agent); integration surface; licensing/ops fit |
| Other agent frameworks | Only after a short written evaluation against Chat2DB goals | Maintainership, Python/Next.js fit, SQL-tool safety model |

If you propose another framework, open an issue with: problem statement, fit to the separation of concerns below, prototype plan, and exit criteria.

## Intended separation of concerns

```text
┌────────────────────────────┐
│  Reasoning & planning      │  Intent, table selection, query plan, refinement strategy
└─────────────┬──────────────┘
              │
┌─────────────▼──────────────┐
│  Workflow orchestration    │  Steps, state, retries, HITL checkpoints, audit trail
└─────────────┬──────────────┘
              │
┌─────────────▼──────────────┐
│  Tool execution            │  Schema peek, dictionary lookup, SQL generate/validate/run
└─────────────┬──────────────┘
              │
┌─────────────▼──────────────┐
│  SQL safety & permissions  │  Read-only guards, credential scope, deny destructive ops
└─────────────┬──────────────┘
              │
┌─────────────▼──────────────┐
│  Observability & audit     │  Traces, SQL text, outcomes, operator review surfaces
└────────────────────────────┘
```

Hard rules that should survive any framework choice:

1. Clients and LLM arguments never silently expand database privileges.
2. Destructive SQL remains rejected by validators (and ideally by DB roles).
3. Humans can inspect SQL before trusting results; HITL gates are first-class for risky actions.
4. Encryption key and credential handling remain environment-driven and fail closed.

## Possible migration stages (illustrative)

These stages are a discussion scaffold, not a release schedule:

1. **Document current pipeline** — map today’s chat engine / SQL pipeline steps to the layers above.
2. **Define tool contracts** — schema explore, sample rows, validate SQL, execute read-only, explain error.
3. **Prototype orchestration** — spike LangGraph (or alternative) behind a feature flag; compare to current path.
4. **Safety parity tests** — destructive SQL rejection, missing encryption key, connector error handling.
5. **UI affordances** — show plan/tool traces; optional approve-before-execute.
6. **Decision record** — adopt, defer, or reject each candidate with written rationale.

## How to contribute

- Open an issue tagged for architecture discussion before large prototypes.
- Prefer small spikes with clear success/fail criteria over broad refactors.
- Keep today’s experimental product usable while exploring the next phase.
- See also [database connector contribution guide](../contributing/database-connectors.md) for adapter work that complements agent tools.

## Related reading in this repo

- Current chat flow notes: `backend/chat/` (engine, SQL guard, executor)
- LLM providers: `backend/llm/`
- Security policy: [`SECURITY.md`](../../SECURITY.md)
- Encryption: [`ENCRYPTION_KEY.md`](../ENCRYPTION_KEY.md)
