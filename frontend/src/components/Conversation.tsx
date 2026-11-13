import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, ArrowUpRight, Code2, FolderOpen, GitBranch, Loader2, Sparkles } from "lucide-react";
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { createSession, listMessages, listSessionChanges, promptSession } from "../api";
import { useProviders } from "../hooks/useProviders";
import type { LiveSession } from "../hooks/useAgentEvents";
import type { FileChange, ModelInfo, ProviderInfo, Session, SessionMessage } from "../types";
import { ToolCard, type ToolCardData } from "./ToolCard";

interface ConversationProps {
  session: Session | null;
  live: LiveSession;
  onOpenProviders: () => void;
  onSessionCreated?: (session: Session) => void;
  defaultWorkspace: string;
}

export function Conversation({ session, live, onOpenProviders, onSessionCreated, defaultWorkspace }: ConversationProps) {
  const [draft, setDraft] = useState("");
  const [provider, setProvider] = useState(session?.provider ?? "");
  const [model, setModel] = useState(session?.model ?? "");
  const [error, setError] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState("");
  const [pendingId, setPendingId] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const providersQuery = useProviders();
  const connected = useMemo(
    () => (providersQuery.data ?? []).filter((p) => p.connected),
    [providersQuery.data],
  );
  const active: ProviderInfo | undefined =
    connected.find((p) => p.id === provider) ?? connected[0];
  const models = active?.models ?? [];

  useEffect(() => {
    setProvider(session?.provider ?? "");
    setModel(session?.model ?? "");
    setDraft("");
    setError(null);
    setWorkspace("");
  }, [session?.id, session?.provider, session?.model]);

  useEffect(() => {
    if (!active) return;
    if (provider !== active.id) { setProvider(active.id); setModel(active.models[0]?.id ?? ""); }
    if (!model) setModel(active.models[0]?.id ?? "");
  }, [active, model, provider]);

  const messagesQuery = useQuery({
    queryKey: ["messages", session?.id],
    queryFn: () => listMessages(session!.id),
    enabled: Boolean(session),
  });
  const changesQuery = useQuery({
    queryKey: ["changes", session?.id],
    queryFn: () => listSessionChanges(session!.id),
    enabled: Boolean(session),
  });

  const changesByTool = useMemo(() => {
    const map = new Map<string, FileChange>();
    for (const change of changesQuery.data ?? []) {
      if (change.tool_call_id) map.set(change.tool_call_id, change);
    }
    return map;
  }, [changesQuery.data]);

  const send = useMutation({
    mutationFn: async (text: string) => {
      let sid = session?.id;
      if (!sid) {
        const created = await createSession({
          title: text.split("\n")[0]!.slice(0, 80) || "Session",
          provider,
            model,
            workspace: workspace.trim() || defaultWorkspace || undefined,
        });
        sid = created.id;
        onSessionCreated?.(created);
        await queryClient.invalidateQueries({ queryKey: ["sessions"] });
        await queryClient.invalidateQueries({ queryKey: ["graph"] });
      }
      setPendingId(sid);
      return promptSession(sid, { prompt: text, provider, model });
    },
    onMutate: () => {
      setError(null);
      setDraft("");
    },
    onError: (cause, text) => { setError(cause instanceof Error ? cause.message : "Request failed."); setDraft((current) => current || text); },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ["messages"] });
      await queryClient.invalidateQueries({ queryKey: ["changes"] });
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
      await queryClient.invalidateQueries({ queryKey: ["graph"] });
    },
  });

  const messages = messagesQuery.data ?? [];
  const busy = (send.isPending && pendingId === (session?.id ?? null)) || live.running;

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) { textarea.style.height = "auto"; textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`; }
  }, [draft]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, live.text, live.tools.length]);

  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };
  const submit = () => {
    const text = draft.trim();
    if (!text || send.isPending || busy || !provider || !model) return;
    setPendingId(session?.id ?? null);
    send.mutate(text);
  };

  return (
    <div className={`conv ${messages.length === 0 && !busy ? "conv--empty" : ""}`}>
      <div className="conv__header"><div><span className="eyebrow">CONVERSATION</span><h1>{session?.title ?? "New session"}</h1></div><span className={`session-state ${busy ? "session-state--busy" : ""}`}><i className={`dot ${busy ? "dot--live" : ""}`} />{busy ? "Working" : "Ready"}</span></div>
      <div className="conv__scroll">
        <div className="conv__inner">
          {messagesQuery.isPending && session ? <div className="panel__empty">Loading conversation…</div> : messages.length === 0 && !busy && <div className="welcome">
            <div className="welcome__mark"><GitBranch size={28} strokeWidth={1.4} /></div>
            <span className="eyebrow">A LITTLE CONTEXT. A LOT OF POSSIBILITY.</span>
            <h2>What are we building?</h2>
            <p>Explore your code, make a change, or pick up where you left off. Your work stays connected in the graph.</p>
            <div className="welcome__suggestions">
              {[{ icon: Code2, title: "Explore the codebase", prompt: "Explore this repository and explain its architecture and main entry points." }, { icon: Sparkles, title: "Find the next improvement", prompt: "Inspect this project and suggest the most useful improvement, with a concrete plan." }].map(({ icon: Icon, title, prompt }) => <button key={title} onClick={() => { setDraft(prompt); textareaRef.current?.focus(); }}><Icon size={17} /><span>{title}</span><ArrowUpRight size={14} /></button>)}
            </div>
            {!providersQuery.isPending && connected.length === 0 && <button className="btn welcome__connect" onClick={onOpenProviders}>Connect your first provider <ArrowUpRight size={14} /></button>}
          </div>}
          {messagesQuery.error && <div className="error" role="alert">{messagesQuery.error.message}</div>}

          {messages.map((message) => (
            <MessageView key={message.id} message={message} changesByTool={changesByTool} />
          ))}

          {(live.text || live.tools.length > 0 || live.reasoning) && (
            <div className="turn turn--assistant turn--live">
              {live.reasoning && <details className="reasoning"><summary>Thinking</summary><pre>{live.reasoning}</pre></details>}
              {live.tools.length > 0 && (
                <div className="tools">
                  {live.tools.map((tool) => (
                    <ToolCard
                      key={tool.id}
                      tool={{
                        id: tool.id,
                        name: tool.name,
                        arguments: tool.arguments,
                        status: tool.status,
                        duration_ms: tool.duration_ms,
                        result: tool.preview,
                      }}
                    />
                  ))}
                </div>
              )}
              {live.text && (
                <div className="prose">
                  <ReactMarkdown rehypePlugins={[rehypeHighlight]} remarkPlugins={[remarkGfm]}>
                    {live.text}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          )}

          {busy && !live.text && live.tools.length === 0 && (
            <div className="working">
              <Loader2 className="spin" size={13} />
              <span>Working</span>
            </div>
          )}
          {live.notice && <div className="notice">{live.notice}</div>}
          {(error || live.error) && <div className="error" role="alert">{error ?? live.error}</div>}
          <div ref={endRef} />
        </div>
      </div>

      <div className="composer">
        {!session && <label className="composer__workspace"><FolderOpen size={13} /><input aria-label="Session workspace" placeholder={defaultWorkspace || "Workspace path (optional)"} value={workspace} onChange={(event) => setWorkspace(event.target.value)} /></label>}
        <div className="composer__box">
          <textarea
            ref={textareaRef}
            aria-label="Message Rennew"
            placeholder={connected.length ? "Ask Rennew to build, explore, or improve…" : "Describe your task, then connect a provider…"}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            rows={2}
            value={draft}
          />
          <div className="composer__row">
            <select
              className="pill"
              aria-label="Provider"
              onChange={(e) => {
                setProvider(e.target.value);
                const next = connected.find((p) => p.id === e.target.value);
                setModel(next?.models[0]?.id ?? "");
              }}
              value={provider}
            >
              {connected.length === 0 && <option value="">{providersQuery.isPending ? "Loading providers…" : "No provider"}</option>}
              {connected.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
            <ModelPicker models={models} onChange={setModel} value={model} />
            {session && (
              <span className="composer__meta">
                {(session.total_input_tokens + session.total_output_tokens).toLocaleString()} tok ·
                ${session.total_cost_usd.toFixed(3)}
              </span>
            )}
            <button
              aria-label="Send message"
              className="composer__send"
              disabled={!draft.trim() || busy || !provider || !model}
              onClick={submit}
              type="button"
            >
              {busy ? <Loader2 className="spin" size={15} /> : <ArrowUp size={15} />}
            </button>
          </div>
        </div>
        <div className="composer__footer"><span><kbd>Enter</kbd> to send · <kbd>Shift Enter</kbd> for a new line</span><span>Graph-native context</span></div>
        {providersQuery.error && <div className="error" role="alert">{providersQuery.error.message} <button className="link" onClick={() => void providersQuery.refetch()}>Retry</button></div>}
      </div>
    </div>
  );
}

function ModelPicker({
  models,
  value,
  onChange,
}: {
  models: ModelInfo[];
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const shown = models
    .filter((m) => m.id.toLowerCase().includes(filter.toLowerCase()))
    .slice(0, 40);

  return (
    <div className="picker" ref={ref}>
      <button className="pill" aria-label="Select model" aria-expanded={open} onClick={() => setOpen(!open)} type="button">
        {value || "Select model"}
      </button>
      {open && (
        <div className="picker__menu">
          <input
            autoFocus
            aria-label="Search models or enter a model ID"
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); if (event.key === "Enter" && filter.trim()) { onChange(filter.trim()); setOpen(false); setFilter(""); } }}
            placeholder="Search or enter a model ID…"
            value={filter}
          />
          <div className="picker__list">
            {shown.map((m) => (
              <button
                className={m.id === value ? "on" : ""}
                key={m.id}
                onClick={() => {
                  onChange(m.id);
                  setOpen(false);
                  setFilter("");
                }}
                type="button"
              >
                <span className="picker__id">{m.id}</span>
                <span className="picker__cost">
                  {m.input_per_m != null ? `$${m.input_per_m}/$${m.output_per_m} per M` : ""}
                </span>
              </button>
            ))}
            {shown.length === 0 && <div className="picker__empty">{filter ? "No discovered models match." : "Enter a model ID from your provider."}</div>}
            {filter.trim() && !models.some((item) => item.id === filter.trim()) && <button onClick={() => { onChange(filter.trim()); setOpen(false); setFilter(""); }}>Use “{filter.trim()}” <ArrowUpRight size={13} /></button>}
          </div>
        </div>
      )}
    </div>
  );
}

function MessageView({
  message,
  changesByTool,
}: {
  message: SessionMessage;
  changesByTool: Map<string, FileChange>;
}) {
  if (message.role === "user") {
    return (
      <div className="turn turn--user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }
  const tools: ToolCardData[] = message.tool_calls.map((tool) => ({
    id: tool.id,
    name: tool.name,
    arguments: tool.input,
    status: tool.status === "failed" ? "failed" : "completed",
    duration_ms: tool.duration_ms,
    result: tool.output ? String(tool.output.result ?? "") : undefined,
  }));
  return (
    <div className="turn turn--assistant">
      {message.reasoning && (
        <details className="reasoning">
          <summary>Thinking · {message.tokens.reasoning} tok</summary>
          <pre>{message.reasoning}</pre>
        </details>
      )}
      {tools.length > 0 && (
        <div className="tools">
          {tools.map((tool) => (
            <ToolCard key={tool.id} tool={tool} change={changesByTool.get(tool.id)} />
          ))}
        </div>
      )}
      {message.content && (
        <div className="prose">
          <ReactMarkdown rehypePlugins={[rehypeHighlight]} remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
