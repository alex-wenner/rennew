# Rennew

Renewed agent workflows. Simple, graph first.

Rennew is a local Python coding-agent harness. Sessions, tools, memories, and
handoffs live in one LadybugDB graph. Providers plug in as adapters. You run
the agent from the CLI, the web UI, or both: CLI does the work, the web can
just watch the graph.

OpenCode and Oh My Pi informed the design. Rennew does not wrap either of them.

## What it does

- Real LLM turns through OpenAI Responses, OpenAI Completions, and Anthropic Messages
- Pluggable providers: OpenAI, Anthropic, OpenRouter, Groq, Together, Ollama, LM Studio, vLLM
- Native tools confined to the workspace, plus MCP stdio servers and on-demand skills
- Graph memory (`remember` / `recall`) and compaction instead of dumping full transcripts
- CLI for `chat` / `run`, web for chat + graph observer

## Start

```console
uv sync --extra dev
cd frontend && npm install && npm run build && cd ..
uv run ren ui
```

Connect a provider in the UI **Providers** panel, or:

```console
uv run ren connect openai
uv run ren run "Inspect this repo and summarize the agent loop."
uv run ren chat
```

Local models need no key:

```console
uv run ren run --provider ollama --model llama3.2 "List the Python packages."
```

## Modes

| Command | What it runs |
|---|---|
| `ren ui` | Full web app: chat, providers, graph, telemetry |
| `ren server` | API + graph observer; drive agents from the CLI |
| `ren chat` | Interactive agent in the terminal |
| `ren run "..."` | One-shot turn, persisted to the graph |
| `ren providers` | Connection status |
| `ren session list` | Sessions in the graph |
| `ren graph query 'MATCH (s:Session) RETURN s.title'` | Read-only Cypher |

## Configuration

Optional `rennew.toml`:

```toml
[server]
port = 7337

[storage]
path = ".rennew/rennew.lbdb"

[agent]
max_steps = 12
provider = "openai"
model = "gpt-5.6-terra"
```

Add extra providers in `.rennew/providers.json`. Keys stay in
`~/.rennew/credentials.json` or environment variables (`OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, …). Nothing is uploaded.

Current defaults (September 2026): `gpt-5.6-terra` / `gpt-5.6-sol` /
`gpt-5.6-luna`, `claude-sonnet-5` / `claude-opus-5` / `claude-haiku-4-5`.
The Providers panel can also load live `/models` lists from a connected backend.

## License

MIT
