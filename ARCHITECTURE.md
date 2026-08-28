# Rennew Architecture

## Design Rules

1. A Rennew session is the durable anchor for execution data.
2. Sessions are connected, not nested. Handoffs are explicit; overlaps are explainable.
3. The Python runtime is the only read-write owner of the embedded graph.
4. The React application communicates through the versioned local API.
5. Provider-specific capabilities are represented, not flattened away.
6. Skills, tools, and prompts are separate extension surfaces.
7. Transport code does not contain domain or graph-storage logic.
8. Secrets never enter configuration files, graph records, logs, or browser state.
9. Zero-cloud guarantee: Rennew contains no telemetry, analytics, or remote sync. All state is local.
10. Non-blocking persistence: Handoffs, telemetry, and checkpoint writes must not block agent execution loops.

## Package Map

| Package | Responsibility |
| --- | --- |
| `api` | FastAPI routes and browser delivery |
| `config` | Defaults and `rennew.toml` loading |
| `graph` | LadybugDB schema, persistence, and safe Cypher access |
| `sessions` | Session, handoff, compaction, and overlap domain models and use cases |
| `providers` | Raw-model and coding-agent backend contracts (OpenAI, Anthropic, Bedrock, Copilot, Codex, OpenCode Go) |
| `security` | Local OS-keyring credential vault without cloud leakage |
| `orchestration` | Built-in modes and validation policy |
| `memory` | Memory contracts and retrieval policy |
| `skills` | Discoverable instruction and workflow packages |
| `tools` | Executable capability contracts and registry |
| `prompts` | Versioned prompt templates and catalog |
| `runtime` | Dependency composition and database lifecycle |
| `web` | Compiled React application assets |

## Dependency Direction

```text
api / cli
    |
    v
sessions / orchestration / memory
    |
    v
graph / providers / skills / tools / prompts
```

`sessions` owns its domain contracts. `graph` implements persistence for those
contracts. `api` translates HTTP requests into use-case calls and does not issue
Cypher directly.

## Local Runtime

LadybugDB permits one read-write database owner. Rennew therefore uses one local
runtime process as the owner. Browser clients, CLI clients, and future worker
processes communicate with that runtime instead of opening the database file.

## Frontend

The frontend is a React and TypeScript application built with Vite. Its compiled
assets are copied to `src/rennew/web/static` and included in the Python wheel. A
Node.js runtime is not required to use Rennew.
