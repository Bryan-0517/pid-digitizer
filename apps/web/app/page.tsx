"use client";

import React, { FormEvent, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { Document, DocumentPage, EngineeringConnection, EngineeringEntity, EngineeringGraph } from "../types/engineering-graph";
import { sourceTypeForFilename, supportedInputMessage } from "./upload-validation";
import EntityInspector from "../components/entity-inspector";
import ConnectionInspector from "../components/connection-inspector";
import BenchmarkSummary, { BenchmarkPageFixture } from "../components/benchmark-summary";
import GraphChat from "../components/graph-chat";
import DexpiValidation from "../components/dexpi-validation";

type DocumentDetail = { document: Document; page?: DocumentPage };
type BenchmarkData = { page: BenchmarkPageFixture; graph: EngineeringGraph };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DiagramViewer = dynamic(() => import("../components/diagram-viewer"), {
  ssr: false,
  loading: () => <p>Loading diagram viewer…</p>,
});

export default function Home() {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [graph, setGraph] = useState<EngineeringGraph | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  const [highlightedEntityIds, setHighlightedEntityIds] = useState<string[]>([]);
  const [highlightedConnectionIds, setHighlightedConnectionIds] = useState<string[]>([]);
  const [loadingDocument, setLoadingDocument] = useState(false);
  const [benchmark, setBenchmark] = useState<BenchmarkData | null>(null);

  useEffect(() => {
    const parameters = new URLSearchParams(window.location.search);
    if (parameters.get("benchmark") === "hydrolysis" && parameters.get("screen") === "IMG_6807.JPG") {
      void loadBenchmark();
      return;
    }
    const documentId = parameters.get("documentId");
    if (documentId) void loadDocument(documentId);
  }, []);

  async function loadBenchmark() {
    setLoadingDocument(true); setError(null);
    try {
      const response = await fetch("/api/benchmark/hydrolysis?screen=IMG_6807.JPG");
      if (!response.ok) throw new Error(await errorMessage(response));
      setBenchmark(await response.json() as BenchmarkData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Benchmark page could not be loaded");
    } finally { setLoadingDocument(false); }
  }

  async function loadDocument(documentId: string) {
    setLoadingDocument(true);
    setError(null);
    try {
      const [documentResponse, graphResponse] = await Promise.all([
        fetch(`${apiUrl}/documents/${documentId}`),
        fetch(`${apiUrl}/documents/${documentId}/graph`),
      ]);
      if (!documentResponse.ok) throw new Error(await errorMessage(documentResponse));
      if (!graphResponse.ok) throw new Error(await errorMessage(graphResponse));
      setDetail((await documentResponse.json()) as DocumentDetail);
      setGraph((await graphResponse.json()) as EngineeringGraph);
      setSelectedEntityId(null);
      setSelectedConnectionId(null);
      setHighlightedEntityIds([]);
      setHighlightedConnectionIds([]);
    } catch (reason) {
      setDetail(null);
      setGraph(null);
      setError(reason instanceof Error ? reason.message : "Document could not be loaded");
    } finally {
      setLoadingDocument(false);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = selectedFile;
    if (!file || file.size === 0) return;
    const sourceType = sourceTypeForFilename(file.name);
    if (!sourceType) {
      setError(supportedInputMessage);
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const createdResponse = await fetch(`${apiUrl}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: file.name, sourceType }),
      });
      if (!createdResponse.ok) throw new Error(await errorMessage(createdResponse));
      const created = (await createdResponse.json()) as Document;
      const uploadBody = new FormData();
      uploadBody.set("file", file);
      const uploadResponse = await fetch(`${apiUrl}/documents/${created.id}/upload`, {
        method: "POST",
        body: uploadBody,
      });
      if (!uploadResponse.ok) throw new Error(await errorMessage(uploadResponse));
      const uploaded = (await uploadResponse.json()) as DocumentDetail;
      const graphResponse = await fetch(`${apiUrl}/documents/${created.id}/graph`);
      if (!graphResponse.ok) throw new Error(await errorMessage(graphResponse));
      setDetail(uploaded);
      setGraph((await graphResponse.json()) as EngineeringGraph);
      setSelectedEntityId(null);
      setSelectedConnectionId(null);
      setHighlightedEntityIds([]);
      setHighlightedConnectionIds([]);
      window.history.replaceState(null, "", `?documentId=${encodeURIComponent(created.id)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function returnToUpload() {
    setDetail(null);
    setGraph(null);
    setSelectedEntityId(null);
    setSelectedConnectionId(null);
    setHighlightedEntityIds([]);
    setHighlightedConnectionIds([]);
    setError(null);
    window.history.replaceState(null, "", window.location.pathname);
  }

  function entitySaved(saved: EngineeringEntity) {
    setGraph((current) => current ? {
      ...current,
      entities: current.entities.map((entity) => entity.id === saved.id ? saved : entity),
    } : current);
  }

  function connectionCreated(created: EngineeringConnection) {
    setGraph((current) => current ? { ...current, connections: [...current.connections, created] } : current);
    setSelectedEntityId(null);
    setSelectedConnectionId(created.id);
  }

  function connectionSaved(saved: EngineeringConnection) {
    setGraph((current) => current ? { ...current, connections: current.connections.map((item) => item.id === saved.id ? saved : item) } : current);
  }

  function connectionDeleted(id: string) {
    setGraph((current) => current ? { ...current, connections: current.connections.filter((item) => item.id !== id) } : current);
    setSelectedConnectionId(null);
  }

  function selectEntity(id: string | null) { setSelectedEntityId(id); if (id) setSelectedConnectionId(null); }
  function selectConnection(id: string | null) { setSelectedConnectionId(id); if (id) setSelectedEntityId(null); }
  function clearSelection() { setSelectedEntityId(null); setSelectedConnectionId(null); }

  const selectedEntity = graph?.entities.find((entity) => entity.id === selectedEntityId) ?? null;
  const selectedConnection = graph?.connections.find((connection) => connection.id === selectedConnectionId) ?? null;

  return (
    <main>
      <h1>P&amp;ID Digitizer</h1>
      <p>Upload a PNG, JPG/JPEG, or single-page PDF.</p>
      {!detail && !benchmark && <form onSubmit={upload}>
        <label htmlFor="diagram">Engineering diagram</label>
        <input
          id="diagram"
          name="file"
          type="file"
          accept="image/png,image/jpeg,application/pdf"
          onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
          required
        />
        <button type="submit" disabled={uploading}>{uploading ? "Uploading…" : "Upload"}</button>
      </form>}
      {loadingDocument && <p aria-live="polite">Loading document…</p>}
      <p className="error" role="alert">{error}</p>
      {error && new URLSearchParams(typeof window === "undefined" ? "" : window.location.search).has("documentId") && (
        <button type="button" onClick={returnToUpload}>Return to upload</button>
      )}
      {detail?.page && graph && (
        <section aria-label="Uploaded document">
          <h2>{detail.document.name}</h2>
          <div className="document-workspace">
            <DiagramViewer
              page={detail.page}
              imageUrl={`${apiUrl}${detail.page.imageUri}`}
              documentName={detail.document.name}
              graph={graph}
              selectedEntityId={selectedEntityId}
              selectedConnectionId={selectedConnectionId}
              highlightedEntityIds={highlightedEntityIds}
              highlightedConnectionIds={highlightedConnectionIds}
              onSelectEntity={selectEntity}
              onSelectConnection={selectConnection}
              onClearSelection={clearSelection}
            />
            <div className="inspectors">
              <GraphChat
                apiUrl={apiUrl}
                documentId={graph.documentId}
                onHighlight={(entityIds, connectionIds) => {
                  setHighlightedEntityIds([...entityIds]);
                  setHighlightedConnectionIds([...connectionIds]);
                }}
              />
              <DexpiValidation
                apiUrl={apiUrl}
                documentId={graph.documentId}
                onSelectEntity={selectEntity}
                onSelectConnection={selectConnection}
              />
              <EntityInspector entity={selectedEntity} apiUrl={apiUrl} onSaved={entitySaved} />
              <ConnectionInspector
                apiUrl={apiUrl} documentId={graph.documentId} entities={graph.entities}
                connections={graph.connections} connection={selectedConnection}
                onSelect={selectConnection} onCreated={connectionCreated}
                onSaved={connectionSaved} onDeleted={connectionDeleted}
              />
            </div>
          </div>
        </section>
      )}
      {benchmark && <section aria-label="Hydrolysis benchmark page">
        <h2>{benchmark.page.sourceFilename}</h2>
        <div className="document-workspace benchmark-mode">
          <DiagramViewer
            page={{ id: benchmark.page.pageId, documentId: benchmark.page.documentId, pageNumber: 1,
              imageUri: "/api/benchmark/hydrolysis/image", widthPx: benchmark.page.widthPx, heightPx: benchmark.page.heightPx }}
            imageUrl="/api/benchmark/hydrolysis/image" documentName={benchmark.page.sourceFilename}
            graph={benchmark.graph} selectedEntityId={null} selectedConnectionId={null}
            onSelectEntity={() => undefined} onSelectConnection={() => undefined} onClearSelection={() => undefined}
          />
          <BenchmarkSummary fixture={benchmark.page} graph={benchmark.graph} />
        </div>
      </section>}
    </main>
  );
}

async function errorMessage(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null;
  return body?.detail ?? `Upload failed (${response.status})`;
}
