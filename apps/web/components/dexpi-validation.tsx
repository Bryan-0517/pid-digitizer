"use client";

import React, { useState } from "react";
import type {
  DexpiConversionReport, DexpiExportAvailability, DexpiMappingReport,
  DexpiObjectReport, PydexpiCompatibilityArtifact,
} from "../types/dexpi";

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
  const [availability, setAvailability] = useState<DexpiExportAvailability | null>(null);
  const [conversion, setConversion] = useState<DexpiConversionReport | null>(null);
  const [running, setRunning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function validate() {
    setRunning(true);
    setError(null);
    setConversion(null);
    setAvailability(null);
    try {
      const response = await fetch(`${apiUrl}/documents/${documentId}/dexpi/validate`, { method: "POST" });
      if (!response.ok) throw new Error(await errorMessage(response));
      setReport(await response.json() as DexpiMappingReport);
      const availabilityResponse = await fetch(`${apiUrl}/documents/${documentId}/dexpi/export/availability`);
      if (!availabilityResponse.ok) throw new Error(await errorMessage(availabilityResponse));
      setAvailability(await availabilityResponse.json() as DexpiExportAvailability);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "DEXPI validation failed");
    } finally {
      setRunning(false);
    }
  }

  async function exportCompatibilityJson() {
    setExporting(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/documents/${documentId}/dexpi/export`, { method: "POST" });
      if (!response.ok) throw new Error(await errorMessage(response));
      const artifact = await response.json() as PydexpiCompatibilityArtifact;
      setConversion(artifact.conversionReport);
      const blob = new Blob([JSON.stringify(artifact, null, 2) + "\n"], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = responseFilename(response, `${documentId}.dexpi-1.3.pydexpi.json`);
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "pyDEXPI compatibility export failed");
    } finally {
      setExporting(false);
    }
  }

  function select(item: DexpiObjectReport) {
    if (item.objectType === "entity") onSelectEntity(item.canonicalId);
    else onSelectConnection(item.canonicalId);
  }

  return <section className="dexpi-validation" aria-label="DEXPI Validation">
    <h3>DEXPI Validation</h3>
    <p>Version-neutral preflight only. This is not DEXPI conformance certification.</p>
    <button type="button" disabled={running || exporting} aria-busy={running} onClick={validate}>
      {running ? "Validating…" : "Run validation"}
    </button>
    {running && <p role="status">Running dependency-free DEXPI preflight…</p>}
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
      <ObjectGroup title="Supported" items={report.objects.filter((item) => item.disposition === "supported")} onSelect={select} />
      <ObjectGroup title="Partial / unmapped" items={report.objects.filter((item) => ["partial", "unmapped"].includes(item.disposition))} onSelect={select} />
      <ObjectGroup title="Blocked" items={report.objects.filter((item) => item.disposition === "blocked")} onSelect={select} />
      {availability && <section className="dexpi-export" aria-label="pyDEXPI compatibility export">
        <h4>Compatibility spike export</h4>
        <p>{availability.artifactLabel}</p>
        <p>pyDEXPI {availability.pydexpiVersion}; DEXPI {availability.targetDexpiVersion}.</p>
        <p>This JSON is not a standard DEXPI exchange file or conformance certification.</p>
        {availability.reason && <p className="dexpi-warning">{availability.reason}</p>}
        {report.status === "blocked" && <BlockingSummary report={report} />}
        {availability.available && <button type="button" onClick={exportCompatibilityJson} aria-busy={exporting}
          disabled={exporting || report.status === "blocked" || report.status === "empty"}>
          {exporting ? "Preparing download…" : "Download compatibility JSON"}
        </button>}
        {exporting && <p role="status">Preparing transient compatibility JSON download…</p>}
        {conversion && <ConversionSummary report={conversion} />}
      </section>}
    </div>}
  </section>;
}

function ObjectGroup({ title, items, onSelect }: {
  title: string; items: DexpiObjectReport[]; onSelect: (item: DexpiObjectReport) => void;
}) {
  if (items.length === 0) return null;
  return <section className="dexpi-object-group"><h4>{title}</h4>
    {items.map((item) => <details key={`${item.objectType}-${item.canonicalId}`}>
      <summary><button type="button" onClick={(event) => { event.preventDefault(); onSelect(item); }}>
        {item.canonicalId}
      </button>{` — ${item.kind}${item.label ? ` — ${item.label}` : ""} — ${item.disposition}`}</summary>
      {item.assertion && <p>Assertion: {item.assertion.mode}; review: {item.assertion.reviewStatus}</p>}
      <table><thead><tr><th>Field</th><th>Disposition</th><th>Reason</th></tr></thead>
        <tbody>{item.fields.map((field) => <tr key={field.path}><td>{field.path}</td>
          <td>{field.disposition}</td><td><code>{field.reasonCode}</code>: {field.message}</td></tr>)}</tbody>
      </table>
    </details>)}
  </section>;
}

function BlockingSummary({ report }: { report: DexpiMappingReport }) {
  return <div><strong>Export blocked</strong><ul>
    {report.objects.filter((item) => item.disposition === "blocked").map((item) => <li key={item.canonicalId}>
      {item.canonicalId}: {item.fields.filter((field) => field.disposition === "blocked")
        .map((field) => field.reasonCode).join(", ")}
    </li>)}
  </ul></div>;
}

function ConversionSummary({ report }: { report: DexpiConversionReport }) {
  return <div aria-label="Conversion report">
    <p>Included: {report.includedObjects.length}; omitted/unmapped: {report.omittedObjects.length}.</p>
    {report.warnings.map((warning) => <p className="dexpi-warning" key={warning}>{warning}</p>)}
  </div>;
}

async function errorMessage(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: string | { message?: string } } | null;
  if (typeof body?.detail === "string") return body.detail;
  return body?.detail?.message ?? `DEXPI request failed (${response.status})`;
}

function responseFilename(response: Response, fallback: string): string {
  const disposition = response.headers?.get("content-disposition");
  return disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? fallback;
}
