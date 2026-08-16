"use client";

import React, { FormEvent, useState } from "react";
import type { ChatResponse } from "../types/graph-chat";

type GraphChatProps = {
  apiUrl: string;
  documentId: string;
  onHighlight: (entityIds: string[], connectionIds: string[]) => void;
};

export default function GraphChat({ apiUrl, documentId, onHighlight }: GraphChatProps) {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch(`${apiUrl}/documents/${documentId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message.trim(), verbalize: false }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const next = await response.json() as ChatResponse;
      setResult(next);
      onHighlight(next.highlight.entityIds, next.highlight.connectionIds);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Graph query failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="graph-chat" aria-label="Graph chat">
      <h3>Graph query</h3>
      <p>Supported: connected, upstream, downstream, exact lookup, and shortest path.</p>
      <form onSubmit={submit}>
        <label htmlFor="graph-chat-message">Question</label>
        <input
          id="graph-chat-message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="What is connected to P-101?"
          required
        />
        <button type="submit" disabled={submitting || !message.trim()} aria-busy={submitting}>{submitting ? "Querying…" : "Ask graph"}</button>
      </form>
      {submitting && <p role="status">Querying the canonical graph…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {result && <div aria-live="polite">
        <p className="chat-answer">{result.answer}</p>
        {result.warnings.length > 0 && <ul aria-label="Graph query warnings">
          {result.warnings.map((warning, index) => (
            <li key={`${warning.code}-${warning.objectId ?? index}`}>{warning.message}</li>
          ))}
        </ul>}
        <dl className="chat-supporting-ids">
          <dt>Supporting entities</dt>
          <dd>{result.supportingEntityIds.join(", ") || "None"}</dd>
          <dt>Supporting connections</dt>
          <dd>{result.supportingConnectionIds.join(", ") || "None"}</dd>
        </dl>
        {result.supportingEntityIds.length === 0 && result.supportingConnectionIds.length === 0
          && <p className="empty-state">No supporting canonical IDs were returned.</p>}
      </div>}
    </section>
  );
}

async function errorMessage(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  return body?.detail ?? `Graph query failed (${response.status})`;
}
