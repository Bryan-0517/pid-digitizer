"use client";

import React, { useState } from "react";
import type { DexpiMappingReport, DexpiObjectReport } from "../types/dexpi";

type DexpiValidationProps = {
  apiUrl: string;
  documentId: string;
  onSelectEntity: (id: string) => void;
  onSelectConnection: (id: string) => void;
};

export default function DexpiValidation({
  apiUrl, documentId, onSelectEntity, onSelectConnection,
}: DexpiValidationProps) {
  const [report, setReport] = useState<DexpiMappingReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function validate() {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/documents/${documentId}/dexpi/validate`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      setReport(await response.json() as DexpiMappingReport);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "DEXPI validation failed");
    } finally {
      setRunning(false);
    }
  }

  function select(item: DexpiObjectReport) {
    if (item.objectType === "entity") onSelectEntity(item.canonicalId);
    else onSelectConnection(item.canonicalId);
  }

  return (
    <section className="dexpi-validation" aria-label="DEXPI Validation">
      <h3>DEXPI Validation</h3>
      <p>Version-neutral preflight only. This is not DEXPI conformance certification.</p>
      <button type="button" disabled={running} onClick={validate}>
        {running ? "Validating…" : "Run validation"}
      </button>
      {error && <p className="error" role="alert">{error}</p>}
      {report && <div aria-live="polite">
        <dl className="dexpi-counts">
          <dt>Overall status</dt><dd>{report.status}</dd>
          <dt>Supported objects</dt><dd>{report.counts.supportedObjects}</dd>
          <dt>Partial objects</dt><dd>{report.counts.partialObjects}</dd>
          <dt>Unmapped objects</dt><dd>{report.counts.unmappedObjects}</dd>
          <dt>Blocked objects</dt><dd>{report.counts.blockedObjects}</dd>
          <dt>Supported fields</dt><dd>{report.counts.supportedFields}</dd>
          <dt>Unmapped fields</dt><dd>{report.counts.unmappedFields}</dd>
          <dt>Blocked fields</dt><dd>{report.counts.blockedFields}</dd>
        </dl>
        {report.warnings.map((warning) => <p className="dexpi-warning" key={warning}>{warning}</p>)}
        <ObjectGroup
          title="Supported"
          items={report.objects.filter((item) => item.disposition === "supported")}
          onSelect={select}
        />
        <ObjectGroup
          title="Partial / unmapped"
          items={report.objects.filter((item) => ["partial", "unmapped"].includes(item.disposition))}
          onSelect={select}
        />
        <ObjectGroup
          title="Blocked"
          items={report.objects.filter((item) => item.disposition === "blocked")}
          onSelect={select}
        />
      </div>}
    </section>
  );
}

function ObjectGroup({
  title, items, onSelect,
}: { title: string; items: DexpiObjectReport[]; onSelect: (item: DexpiObjectReport) => void }) {
  if (items.length === 0) return null;
  return <section className="dexpi-object-group">
    <h4>{title}</h4>
    {items.map((item) => <details key={`${item.objectType}-${item.canonicalId}`}>
      <summary>
        <button type="button" onClick={(event) => { event.preventDefault(); onSelect(item); }}>
          {item.canonicalId}
        </button>
        {` — ${item.kind}${item.label ? ` — ${item.label}` : ""} — ${item.disposition}`}
      </summary>
      {item.assertion && <p>
        Assertion: {item.assertion.mode}; review: {item.assertion.reviewStatus}
      </p>}
      <table>
        <thead><tr><th>Field</th><th>Disposition</th><th>Reason</th></tr></thead>
        <tbody>{item.fields.map((field) => <tr key={field.path}>
          <td>{field.path}</td><td>{field.disposition}</td>
          <td><code>{field.reasonCode}</code>: {field.message}</td>
        </tr>)}</tbody>
      </table>
    </details>)}
  </section>;
}

async function errorMessage(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  return body?.detail ?? `DEXPI validation failed (${response.status})`;
}
