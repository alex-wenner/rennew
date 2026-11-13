import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, KeyRound, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  connectProvider,
  disconnectProvider,
  githubStart,
  githubStatus,
  listProviders,
  openaiStart,
  openaiStatus,
} from "../api";
import type { AuthStatus, ProviderInfo } from "../types";

export function ProviderPanel() {
  const queryClient = useQueryClient();
  const providersQuery = useQuery({
    queryKey: ["providers"],
    queryFn: () => listProviders(true),
    refetchInterval: 5000,
  });
  const [error, setError] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["providers"] });
  const providers = providersQuery.data ?? [];
  const connected = providers.filter((p) => p.connected).length;

  return (
    <div className="panel">
      <div className="panel__bar">
        <span>
          <strong>{connected}</strong> <span className="muted">connected</span>
        </span>
        <button className="link" onClick={() => providersQuery.refetch()} type="button">
          refresh
        </button>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="panel__scroll">
        <div className="prov-grid">
          {providers.map((p) => (
            <ProviderCard key={p.id} onError={setError} onRefresh={refresh} provider={p} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ProviderCard({
  provider,
  onRefresh,
  onError,
}: {
  provider: ProviderInfo;
  onRefresh: () => Promise<void>;
  onError: (m: string | null) => void;
}) {
  const canApiKey = provider.auth.includes("api_key");
  const canGithub = provider.auth === "github";
  const canOauth = provider.auth.includes("oauth");

  return (
    <div className={`pcard ${provider.connected ? "pcard--on" : ""}`}>
      <div className="pcard__head">
        <i className={`dot ${provider.connected ? "dot--on" : ""}`} />
        <div className="pcard__title">
          <strong>{provider.label}</strong>
          <span className="muted">{provider.api}</span>
        </div>
        {provider.connected && (
          <Disconnect onRefresh={onRefresh} providerId={provider.id} />
        )}
      </div>
      {provider.models.length > 0 && (
        <div className="pcard__models">
          {provider.models.length} models · {provider.models.slice(0, 3).map((m) => m.id).join(" · ")}
        </div>
      )}

      {!provider.connected && canApiKey && (
        <ApiKeyForm onError={onError} onRefresh={onRefresh} providerId={provider.id} />
      )}
      {!provider.connected && canGithub && <GitHubAuth onError={onError} onRefresh={onRefresh} />}
      {!provider.connected && canOauth && <OAuthAuth onError={onError} onRefresh={onRefresh} />}
    </div>
  );
}

function ApiKeyForm({
  providerId,
  onRefresh,
  onError,
}: {
  providerId: string;
  onRefresh: () => Promise<void>;
  onError: (m: string | null) => void;
}) {
  const [key, setKey] = useState("");
  const connect = useMutation({
    mutationFn: () => connectProvider(providerId, key.trim()),
    onSuccess: async () => {
      setKey("");
      onError(null);
      await onRefresh();
    },
    onError: (c) => onError(c instanceof Error ? c.message : "Could not connect."),
  });
  return (
    <form
      className="pcard__form"
      onSubmit={(e) => {
        e.preventDefault();
        if (key.trim()) connect.mutate();
      }}
    >
      <KeyRound size={13} />
      <input
        autoComplete="off"
        onChange={(e) => setKey(e.target.value)}
        placeholder="API key"
        spellCheck={false}
        type="password"
        value={key}
      />
      <button disabled={!key.trim() || connect.isPending} type="submit">
        {connect.isPending ? <Loader2 className="spin" size={13} /> : "Connect"}
      </button>
    </form>
  );
}

function useAuthPoller(
  statusFn: () => Promise<AuthStatus>,
  onDone: () => Promise<void>,
  onError: (m: string | null) => void,
) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const timer = useRef<number | null>(null);
  const stop = () => {
    if (timer.current) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
  };
  useEffect(() => () => stop(), []);
  const begin = () => {
    stop();
    timer.current = window.setInterval(async () => {
      try {
        const s = await statusFn();
        setStatus(s);
        if (s.status === "complete") {
          stop();
          setStatus(null);
          await onDone();
        } else if (s.status === "error") {
          stop();
          setStatus(null);
          onError(s.error ?? "Sign-in failed.");
        }
      } catch {
        stop();
        setStatus(null);
      }
    }, 1500);
  };
  return { status, begin, stop };
}

function GitHubAuth({ onRefresh, onError }: { onRefresh: () => Promise<void>; onError: (m: string | null) => void }) {
  const { status, begin, stop } = useAuthPoller(githubStatus, onRefresh, onError);
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setBusy(true);
    onError(null);
    try {
      const s = await githubStart();
      if (s.user_code) window.open(s.verification_uri ?? "https://github.com/login/device", "_blank", "noopener");
      begin();
    } catch (c) {
      onError(c instanceof Error ? c.message : "Could not start GitHub sign-in.");
    } finally {
      setBusy(false);
    }
  };

  if (status?.status === "pending") {
    return (
      <div className="flow">
        <div className="flow__code">
          <span>{status.user_code}</span>
          <button
            className="icon"
            onClick={() => navigator.clipboard.writeText(status.user_code ?? "")}
            type="button"
          >
            <Copy size={13} />
          </button>
        </div>
        <p className="muted">Enter the code at github.com/login/device, then approve.</p>
        <button className="link" onClick={() => { stop(); }} type="button">
          cancel
        </button>
      </div>
    );
  }
  return (
    <button className="btn btn--ghost" disabled={busy} onClick={start} type="button">
      {busy ? <Loader2 className="spin" size={13} /> : "Sign in with GitHub"}
    </button>
  );
}

function OAuthAuth({ onRefresh, onError }: { onRefresh: () => Promise<void>; onError: (m: string | null) => void }) {
  const { status, begin, stop } = useAuthPoller(openaiStatus, onRefresh, onError);
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setBusy(true);
    onError(null);
    try {
      const s = await openaiStart();
      if (s.url) window.open(s.url, "_blank", "noopener");
      begin();
    } catch (c) {
      onError(c instanceof Error ? c.message : "Could not start sign-in.");
    } finally {
      setBusy(false);
    }
  };

  if (status?.status === "pending") {
    return (
      <div className="flow">
        <p className="muted">Complete sign-in in the browser tab. Waiting…</p>
        <button className="link" onClick={() => { stop(); }} type="button">
          cancel
        </button>
      </div>
    );
  }
  return (
    <button className="btn btn--ghost" disabled={busy} onClick={start} type="button">
      {busy ? <Loader2 className="spin" size={13} /> : "Sign in with ChatGPT"}
    </button>
  );
}

function Disconnect({ providerId, onRefresh }: { providerId: string; onRefresh: () => Promise<void> }) {
  const disconnect = useMutation({ mutationFn: () => disconnectProvider(providerId), onSuccess: onRefresh });
  return (
    <button className="pcard__disc" disabled={disconnect.isPending} onClick={() => disconnect.mutate()} type="button">
      disconnect
    </button>
  );
}
