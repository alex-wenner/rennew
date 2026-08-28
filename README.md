# Rennew

Rennew is a local-first, Python coding-agent runtime where sessions are the
first-class unit of work. Sessions can hand work to one another, validate one
another, and overlap through shared tasks, code, memory, and artifacts. The
complete execution model is stored as a queryable local graph.

Rennew is in its initial architecture phase. The current foundation provides:

- A session-centric LadybugDB graph
- A local FastAPI server
- A bundled React and TypeScript interface
- Read-only Cypher querying from the CLI and web UI
- Explicit homes for providers, orchestration modes, skills, tools, and prompts
- Initial handoff and overlap primitives

## Development

Requirements:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+

Install the Python environment:

```console
uv sync --extra dev
```

Install and build the web interface:

```console
cd frontend
npm install
npm run build
```

Start Rennew:

```console
uv run ren ui
```

During frontend development, run Vite separately and point it at the local API:

```console
uv run ren server --reload
cd frontend
npm run dev
```

## Configuration

Rennew runs without a project configuration file. Add `rennew.toml` only when
you need to override a default:

```toml
[server]
port = 7337

[storage]
path = ".rennew/rennew.lbdb"
```

Credentials are never stored in `rennew.toml`. Provider adapters read them from
the operating-system keyring, official provider login, or environment variables.

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for package boundaries and design rules.

## License

MIT
