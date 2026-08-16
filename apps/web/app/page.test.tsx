import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import Home from "./page";
import { sourceTypeForFilename } from "./upload-validation";

vi.mock("../components/diagram-viewer", () => ({
  default: ({ documentName, graph, onSelectEntity }: {
    documentName: string;
    graph: { entities: Array<{ id: string }> };
    onSelectEntity: (id: string) => void;
  }) => (
    <div role="img" aria-label={`Interactive page 1 of ${documentName}`}>
      {graph.entities[0] && <button onClick={() => onSelectEntity(graph.entities[0].id)}>Select fixture entity</button>}
    </div>
  ),
}));

const persistedEntity = {
  id: "entity-1", documentId: "doc-1", pageId: "page-1", kind: "equipment",
  tag: "P-SAVED", displayName: "Persisted pump", properties: {},
  assertion: { mode: "human_added", reviewStatus: "unreviewed" }, provenance: [],
  geometry: { bbox: { x: 0.1, y: 0.1, width: 0.2, height: 0.2 } },
  createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

test.each([
  ["IMG_6754.JPG", "image"],
  ["diagram.jpg", "image"],
  ["diagram.jpeg", "image"],
  ["diagram.JPEG", "image"],
  ["diagram.png", "image"],
  ["diagram.PNG", "image"],
  ["diagram.pdf", "pdf"],
  ["diagram.PDF", "pdf"],
] as const)("classifies supported filename %s", (filename, expected) => {
  expect(sourceTypeForFilename(filename)).toBe(expected);
});

test("rejects an unsupported extension before creating a document", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  render(<Home />);
  const file = new File(["data"], "diagram.gif", { type: "image/gif" });
  const input = screen.getByLabelText("Engineering diagram");
  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.submit(input.closest("form")!);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "PNG, JPG/JPEG, or single-page PDF",
  );
  expect(fetchMock).not.toHaveBeenCalled();
});

test("uploads and displays a normalized document page", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: "doc-1", name: "diagram.png", sourceType: "image", status: "uploaded" }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        document: { id: "doc-1", name: "diagram.png", sourceType: "image", status: "ready" },
        page: { id: "page-1", documentId: "doc-1", pageNumber: 1, imageUri: "/files/page.png", widthPx: 20, heightPx: 10 },
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ schemaVersion: "0.1", documentId: "doc-1", entities: [], connections: [], metadata: {} }),
    });
  vi.stubGlobal("fetch", fetchMock);
  render(<Home />);
  const file = new File(["image"], "diagram.png", { type: "image/png" });
  const input = screen.getByLabelText("Engineering diagram");
  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.submit(input.closest("form")!);

  await waitFor(() => expect(screen.getByRole("img", {
    name: "Interactive page 1 of diagram.png",
  })).toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(window.location.search).toBe("?documentId=doc-1");
});

test("reopens a persisted document and graph from the URL", async () => {
  window.history.replaceState(null, "", "/?documentId=doc-1");
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      document: { id: "doc-1", name: "saved.png", sourceType: "image", status: "ready" },
      page: { id: "page-1", documentId: "doc-1", pageNumber: 1, imageUri: "/files/page.png", widthPx: 20, heightPx: 10 },
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      schemaVersion: "0.1", documentId: "doc-1", entities: [persistedEntity], connections: [], metadata: {},
    }) });
  vi.stubGlobal("fetch", fetchMock);

  render(<Home />);

  await waitFor(() => expect(screen.getByRole("img", {
    name: "Interactive page 1 of saved.png",
  })).toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1/graph");
  fireEvent.click(screen.getByRole("button", { name: "Select fixture entity" }));
  expect(screen.getByLabelText("Tag")).toHaveValue("P-SAVED");
  expect(screen.getByLabelText("Graph chat")).toBeInTheDocument();
  expect(screen.getByLabelText("DEXPI Validation")).toBeInTheDocument();
});

test("opens explicit hydrolysis benchmark mode without upload or mock overlays", async () => {
  window.history.replaceState(null, "", "/?benchmark=hydrolysis&screen=IMG_6807.JPG");
  const graph = { schemaVersion: "0.1", documentId: "benchmark:hydrolysis", entities: [persistedEntity], connections: [], metadata: { sourceKind: "dcs" } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    graph,
    page: {
      pageId: "benchmark:hydrolysis:IMG_6807.JPG", documentId: "benchmark:hydrolysis",
      sourceFilename: "IMG_6807.JPG", widthPx: 5712, heightPx: 4284,
      linkedEntityIds: ["entity-1"], linkedConnectionIds: [], linkedInstrumentIds: [],
      counts: { entities: 1, instruments: 0, connections: 0, multiSourceObjects: 1 },
      geometryCoverage: { status: "missing_verified_geometry", totalObjectsWithVerifiedGeometry: 0 },
      warnings: ["No verified geometry"],
    },
  }) }));
  render(<Home />);
  await waitFor(() => expect(screen.getByRole("img", { name: "Interactive page 1 of IMG_6807.JPG" })).toBeInTheDocument());
  expect(screen.getByText(/Reference mode:/)).toBeInTheDocument();
  expect(screen.getByText(/Verified geometry coverage:/)).toHaveTextContent("0");
  expect(screen.queryByLabelText("Engineering diagram")).not.toBeInTheDocument();
  expect(screen.queryByText(/Mock overlay/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Graph chat")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("DEXPI Validation")).not.toBeInTheDocument();
});

test("shows a clear backend upload error", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "doc-1" }) })
    .mockResolvedValueOnce({ ok: false, status: 422, json: async () => ({ detail: "v0.1 supports single-page PDFs only" }) }));
  render(<Home />);
  const file = new File(["pdf"], "diagram.pdf", { type: "application/pdf" });
  const input = screen.getByLabelText("Engineering diagram");
  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.submit(input.closest("form")!);

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("single-page PDFs only"));
});
