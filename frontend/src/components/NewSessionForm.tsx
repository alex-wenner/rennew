import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { createSession } from "../api";

export function NewSessionForm() {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createSession,
    onSuccess: async () => {
      setTitle("");
      setOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sessions"] }),
        queryClient.invalidateQueries({ queryKey: ["graph"] }),
      ]);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = title.trim();
    if (value) mutation.mutate({ title: value });
  }

  if (!open) {
    return (
      <button className="new-session-button" onClick={() => setOpen(true)} type="button">
        <span>+</span> NEW SESSION
      </button>
    );
  }

  return (
    <form className="new-session-form" onSubmit={submit}>
      <input
        autoFocus
        maxLength={200}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Session objective"
        value={title}
      />
      <button disabled={mutation.isPending} type="submit">
        CREATE
      </button>
      <button onClick={() => setOpen(false)} type="button">
        CANCEL
      </button>
    </form>
  );
}
