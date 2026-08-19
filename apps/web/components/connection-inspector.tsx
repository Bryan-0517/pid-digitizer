"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import type { EngineeringConnection, EngineeringEntity, JsonValue } from "../types/engineering-graph";
import ReviewStatus from "./review-status";

type Props = {
  apiUrl: string;
  documentId: string;
  entities: EngineeringEntity[];
  connections: EngineeringConnection[];
  connection: EngineeringConnection | null;
  onSelect: (id: string) => void;
  onCreated: (connection: EngineeringConnection) => void;
  onSaved: (connection: EngineeringConnection, before: EngineeringConnection) => void;
  onDeleteRequested: () => Promise<void>;
};

const kinds: EngineeringConnection["kind"][] = ["process", "utility", "signal", "ownership", "reference", "unknown"];
const directions: NonNullable<EngineeringConnection["direction"]>[] = ["source_to_target", "target_to_source", "undirected", "unknown"];
const statuses: EngineeringConnection["assertion"]["reviewStatus"][] = ["unreviewed", "confirmed", "corrected", "rejected", "needs_source"];

export function entityOptionLabel(entity: EngineeringEntity) {
  return entity.tag ?? entity.displayName ?? entity.id;
}

export default function ConnectionInspector(props: Props) {
  const [creating, setCreating] = useState(false);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [kind, setKind] = useState<EngineeringConnection["kind"]>("unknown");
  const [medium, setMedium] = useState("");
  const [direction, setDirection] = useState<NonNullable<EngineeringConnection["direction"]>>("unknown");
  const [properties, setProperties] = useState("{}");
  const [reviewStatus, setReviewStatus] = useState<EngineeringConnection["assertion"]["reviewStatus"]>("unreviewed");
  const [allowSelfLoop, setAllowSelfLoop] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    const selected = props.connection;
    setSource(selected?.sourceEntityId ?? props.entities[0]?.id ?? "");
    setTarget(selected?.targetEntityId ?? props.entities[1]?.id ?? props.entities[0]?.id ?? "");
    setKind(selected?.kind ?? "unknown");
    setMedium(selected?.medium ?? "");
    setDirection(selected?.direction ?? "unknown");
    setProperties(JSON.stringify(selected?.properties ?? {}, null, 2));
    setReviewStatus(selected?.assertion.reviewStatus ?? "unreviewed");
    setAllowSelfLoop(selected?.allowSelfLoop ?? false);
    setError(null);
  }, [props.connection, props.entities]);

  useEffect(() => { reset(); if (props.connection) setCreating(false); }, [props.connection, reset]);

  async function save(event: FormEvent) {
    event.preventDefault();
    let parsed: Record<string, JsonValue>;
    try {
      const value = JSON.parse(properties) as unknown;
      if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("Properties must be a JSON object");
      parsed = value as Record<string, JsonValue>;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Properties must be valid JSON"); return;
    }
    setSaving(true); setError(null);
    try {
      const url = creating
        ? `${props.apiUrl}/documents/${props.documentId}/connections`
        : `${props.apiUrl}/connections/${props.connection!.id}`;
      const response = await fetch(url, {
        method: creating ? "POST" : "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sourceEntityId: source, targetEntityId: target, kind, medium: medium || null, direction, properties: parsed, assertion: { reviewStatus }, allowSelfLoop }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const saved = await response.json() as EngineeringConnection;
      if (creating) { props.onCreated(saved); setCreating(false); } else props.onSaved(saved, props.connection!);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Connection save failed"); }
    finally { setSaving(false); }
  }

  async function remove() {
    if (!props.connection) return;
    setSaving(true); setError(null);
    try {
      await props.onDeleteRequested();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Connection delete failed"); }
    finally { setSaving(false); }
  }

  const active = creating || props.connection;
  return <aside className="connection-inspector">
    <h2>Connections</h2>
    <button type="button" disabled={saving} onClick={() => { setCreating(true); reset(); }}>Create connection</button>
    <ul className="connection-list">{props.connections.map((item) => <li key={item.id}>
      <button type="button" onClick={() => props.onSelect(item.id)}>{item.kind}: {entityName(item.sourceEntityId, props.entities)} → {entityName(item.targetEntityId, props.entities)}</button>
      {!item.geometry?.polyline && <span> No diagram geometry</span>}
    </li>)}</ul>
    {!active && <p>Select a rendered connection or choose one from the semantic list.</p>}
    {active && <form onSubmit={save}>
      <h3>{creating ? "New connection" : "Connection Inspector"}</h3>
      <label>Source<select aria-label="Source entity" value={source} onChange={e => setSource(e.target.value)}>{props.entities.map(entity => <option key={entity.id} value={entity.id}>{entityOptionLabel(entity)}</option>)}</select></label>
      <label>Target<select aria-label="Target entity" value={target} onChange={e => setTarget(e.target.value)}>{props.entities.map(entity => <option key={entity.id} value={entity.id}>{entityOptionLabel(entity)}</option>)}</select></label>
      <label>Kind<select value={kind} onChange={e => setKind(e.target.value as EngineeringConnection["kind"])}>{kinds.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Medium<input value={medium} onChange={e => setMedium(e.target.value)} /></label>
      <label>Direction<select value={direction} onChange={e => setDirection(e.target.value as NonNullable<EngineeringConnection["direction"]>)}>{directions.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Review status<select value={reviewStatus} onChange={e => setReviewStatus(e.target.value as EngineeringConnection["assertion"]["reviewStatus"])}>{statuses.map(value => <option key={value}>{value}</option>)}</select></label>
      <label><input type="checkbox" checked={allowSelfLoop} onChange={e => setAllowSelfLoop(e.target.checked)} /> Allow self-loop</label>
      {!creating && !props.connection?.geometry?.polyline && <p>No diagram geometry; this semantic connection is not rendered on Canvas.</p>}
      <div className="inspector-actions"><button type="submit" disabled={saving} aria-busy={saving}>{saving ? "Saving…" : "Save"}</button><button type="button" disabled={saving} onClick={reset}>Cancel</button>{!creating && <button type="button" disabled={saving} onClick={remove}>Delete</button>}</div>
      <details className="inspector-details"><summary>Advanced properties</summary>
        <label>Properties JSON<textarea rows={4} value={properties} onChange={e => setProperties(e.target.value)} /></label>
      </details>
      {error && <p role="alert" className="error">{error}</p>}
      {saving && <p role="status">Saving canonical connection…</p>}
      {!creating && props.connection && <><ReviewStatus confidence={props.connection.confidence} assertion={props.connection.assertion} /><dl className="read-only-fields"><dt>ID</dt><dd>{props.connection.id}</dd><dt>Document ID</dt><dd>{props.connection.documentId}</dd><dt>Created</dt><dd>{props.connection.createdAt}</dd></dl><details><summary>Read-only engineering metadata</summary><pre>{JSON.stringify({ provenance: props.connection.provenance, geometry: props.connection.geometry }, null, 2)}</pre></details></>}
    </form>}
  </aside>;
}

function entityName(id: string, entities: EngineeringEntity[]) { const entity = entities.find(item => item.id === id); return entity ? entityOptionLabel(entity) : id; }
async function responseError(response: Response) { const body = await response.json().catch(() => null) as { detail?: string } | null; return body?.detail ?? `Connection request failed (${response.status})`; }
