"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import type { EngineeringEntity, JsonValue } from "../types/engineering-graph";

type EntityInspectorProps = {
  entity: EngineeringEntity | null;
  apiUrl: string;
  onSaved: (entity: EngineeringEntity) => void;
};

const kinds: EngineeringEntity["kind"][] = [
  "equipment", "valve", "instrument", "boundary", "text", "unknown",
];
const reviewStatuses: EngineeringEntity["assertion"]["reviewStatus"][] = [
  "unreviewed", "confirmed", "corrected", "rejected", "needs_source",
];

export default function EntityInspector({ entity, apiUrl, onSaved }: EntityInspectorProps) {
  const [kind, setKind] = useState<EngineeringEntity["kind"]>("unknown");
  const [subtype, setSubtype] = useState("");
  const [tag, setTag] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [properties, setProperties] = useState("{}");
  const [reviewStatus, setReviewStatus] = useState<EngineeringEntity["assertion"]["reviewStatus"]>("unreviewed");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback((selected: EngineeringEntity | null = entity) => {
    if (!selected) return;
    setKind(selected.kind);
    setSubtype(selected.subtype ?? "");
    setTag(selected.tag ?? "");
    setDisplayName(selected.displayName ?? "");
    setProperties(JSON.stringify(selected.properties, null, 2));
    setReviewStatus(selected.assertion.reviewStatus);
    setError(null);
  }, [entity]);

  useEffect(() => reset(entity), [entity, reset]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!entity) return;
    let parsedProperties: Record<string, JsonValue>;
    try {
      const parsed = JSON.parse(properties) as unknown;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("Properties must be a JSON object");
      }
      parsedProperties = parsed as Record<string, JsonValue>;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Properties must be valid JSON");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/entities/${entity.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind,
          subtype: subtype || null,
          tag: tag || null,
          displayName: displayName || null,
          properties: parsedProperties,
          assertion: { reviewStatus },
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      onSaved((await response.json()) as EngineeringEntity);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Entity save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!entity) {
    return <aside className="entity-inspector"><h2>Inspector</h2><p>Select an entity to inspect it.</p></aside>;
  }

  return (
    <aside className="entity-inspector">
      <h2>Inspector</h2>
      <form onSubmit={save}>
        <label>Kind<select value={kind} onChange={(event) => setKind(event.target.value as EngineeringEntity["kind"])}>{kinds.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Subtype<input value={subtype} onChange={(event) => setSubtype(event.target.value)} /></label>
        <label>Tag<input value={tag} onChange={(event) => setTag(event.target.value)} /></label>
        <label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
        <label>Properties<textarea rows={8} value={properties} onChange={(event) => setProperties(event.target.value)} /></label>
        <label>Review status<select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as EngineeringEntity["assertion"]["reviewStatus"])}>{reviewStatuses.map((value) => <option key={value}>{value}</option>)}</select></label>
        <div className="inspector-actions">
          <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
          <button type="button" disabled={saving} onClick={() => reset()}>Cancel</button>
        </div>
        {error && <p role="alert" className="error">{error}</p>}
      </form>
      <dl className="read-only-fields">
        <dt>ID</dt><dd>{entity.id}</dd>
        <dt>Document ID</dt><dd>{entity.documentId}</dd>
        <dt>Page ID</dt><dd>{entity.pageId}</dd>
        <dt>Confidence</dt><dd>{entity.confidence ?? "Not provided"}</dd>
        <dt>Created</dt><dd>{entity.createdAt}</dd>
      </dl>
      <details><summary>Read-only engineering metadata</summary><pre>{JSON.stringify({ provenance: entity.provenance, geometry: entity.geometry, dexpi: entity.dexpi }, null, 2)}</pre></details>
    </aside>
  );
}

async function responseError(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null;
  return body?.detail ?? `Entity save failed (${response.status})`;
}
