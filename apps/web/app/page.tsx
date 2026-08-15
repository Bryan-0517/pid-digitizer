"use client";

import React, { FormEvent, useState } from "react";
import dynamic from "next/dynamic";
import type { Document, DocumentPage } from "../types/engineering-graph";
import { sourceTypeForFilename, supportedInputMessage } from "./upload-validation";
import { createMockEngineeringGraph } from "../fixtures/mock-engineering-graph";

type DocumentDetail = { document: Document; page?: DocumentPage };

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
      setDetail((await uploadResponse.json()) as DocumentDetail);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <main>
      <h1>P&amp;ID Digitizer</h1>
      <p>Upload a PNG, JPG/JPEG, or single-page PDF.</p>
      <form onSubmit={upload}>
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
      </form>
      <p className="error" role="alert">{error}</p>
      {detail?.page && (
        <section aria-label="Uploaded document">
          <h2>{detail.document.name}</h2>
          <DiagramViewer
            page={detail.page}
            imageUrl={`${apiUrl}${detail.page.imageUri}`}
            documentName={detail.document.name}
            graph={createMockEngineeringGraph(detail.document.id, detail.page.id)}
          />
        </section>
      )}
    </main>
  );
}

async function errorMessage(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null;
  return body?.detail ?? `Upload failed (${response.status})`;
}
