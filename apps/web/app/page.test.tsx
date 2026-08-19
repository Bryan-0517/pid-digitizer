import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import Home from "./page";
import { sourceTypeForFilename } from "./upload-validation";

vi.mock("../components/diagram-viewer", () => ({
  default: ({ documentName, graph, onSelectEntity, onSelectConnection, selectedEntityId,
    selectedConnectionId, highlightedEntityIds = [], proposalCandidates = [] }: {
    documentName: string;
    graph: { entities: Array<{ id: string }>; connections: Array<{ id: string }> };
    onSelectEntity: (id: string) => void;
    onSelectConnection: (id: string) => void;
    selectedEntityId: string | null;
    selectedConnectionId: string | null;
    highlightedEntityIds?: string[];
    proposalCandidates?: Array<{ candidateId: string }>;
  }) => (
    <div role="img" aria-label={`Interactive page 1 of ${documentName}`}>
      {graph.entities[0] && <button onClick={() => onSelectEntity(graph.entities[0].id)}>Select fixture entity</button>}
      {graph.connections[0] && <button onClick={() => onSelectConnection(graph.connections[0].id)}>Select fixture connection</button>}
      <output data-testid="viewer-state">{`${selectedEntityId ?? "none"}|${selectedConnectionId ?? "none"}|${highlightedEntityIds.join(",")}`}</output>
      <output data-testid="viewer-counts">{`${graph.entities.length}|${graph.connections.length}|${proposalCandidates.length}`}</output>
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
const persistedConnection = {
  id: "connection-1", documentId: "doc-1", sourceEntityId: "entity-1", targetEntityId: "entity-1",
  allowSelfLoop: true, kind: "process", direction: "source_to_target", properties: {},
  assertion: { mode: "human_added", reviewStatus: "confirmed" }, provenance: [],
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
  expect(screen.getByText(/empty canonical graph/i)).toBeInTheDocument();
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
  expect(screen.getByRole("tab", { name: "Inspector" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("Select an entity to inspect it.")).toBeInTheDocument();
  expect(screen.getByRole("tabpanel", { name: "Inspector" })).toBeVisible();
  expect(screen.queryByRole("tabpanel", { name: "Query" })).not.toBeInTheDocument();
  expect(screen.queryByRole("tabpanel", { name: "Validate" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Select fixture entity" }));
  expect(screen.getByLabelText("Tag")).toHaveValue("P-SAVED");
});

test("switches one visible sidebar panel at a time and selection opens the relevant tab", async () => {
  window.history.replaceState(null, "", "/?documentId=doc-1");
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      document: { id: "doc-1", name: "saved.png", sourceType: "image", status: "ready" },
      page: { id: "page-1", documentId: "doc-1", pageNumber: 1, imageUri: "/page.png", widthPx: 20, heightPx: 10 },
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      schemaVersion: "0.1", documentId: "doc-1", entities: [persistedEntity],
      connections: [persistedConnection], metadata: {},
    }) }));
  render(<Home />);
  await screen.findByRole("img", { name: "Interactive page 1 of saved.png" });

  fireEvent.click(screen.getByRole("tab", { name: "Query" }));
  expect(within(screen.getByRole("tabpanel", { name: "Query" })).getByLabelText("Graph chat")).toBeVisible();
  expect(screen.queryByRole("tabpanel", { name: "Inspector" })).not.toBeInTheDocument();
  expect(screen.queryByRole("tabpanel", { name: "Validate" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: "Validate" }));
  expect(within(screen.getByRole("tabpanel", { name: "Validate" })).getByLabelText("DEXPI Validation")).toBeVisible();
  expect(screen.queryByRole("tabpanel", { name: "Query" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Select fixture entity" }));
  expect(screen.getByRole("tab", { name: "Inspector" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByLabelText("Tag")).toHaveValue("P-SAVED");

  fireEvent.click(screen.getByRole("button", { name: "Select fixture connection" }));
  expect(screen.getByRole("tab", { name: "Connections" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByLabelText("Medium")).toBeInTheDocument();
  expect(within(screen.getByRole("tabpanel", { name: "Connections" })).queryByLabelText("Tag")).not.toBeInTheDocument();
});

test("Graph Query still highlights its deterministic result from the tabbed panel", async () => {
  window.history.replaceState(null, "", "/?documentId=doc-1");
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      document: { id: "doc-1", name: "saved.png", sourceType: "image", status: "ready" },
      page: { id: "page-1", documentId: "doc-1", pageNumber: 1, imageUri: "/page.png", widthPx: 20, heightPx: 10 },
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      schemaVersion: "0.1", documentId: "doc-1", entities: [persistedEntity], connections: [], metadata: {},
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      answer: "Found P-SAVED.", supportingEntityIds: ["entity-1"], supportingConnectionIds: [],
      highlight: { entityIds: ["entity-1"], connectionIds: [] }, warnings: [],
      outcome: "ok", resolvedIntent: {}, queryResults: [],
    }) });
  vi.stubGlobal("fetch", fetchMock);
  render(<Home />);
  await screen.findByRole("img", { name: "Interactive page 1 of saved.png" });
  fireEvent.click(screen.getByRole("tab", { name: "Query" }));
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Find P-SAVED" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask graph" }));
  expect(await screen.findByText("Found P-SAVED.")).toBeInTheDocument();
  expect(screen.getByTestId("viewer-state")).toHaveTextContent("none|none|entity-1");
});

test("loads proposal-only overlays for the prepared demo without changing canonical counts", async () => {
  window.history.replaceState(null, "", "/?documentId=t019-demo-img6807");
  const proposals = Array.from({ length: 8 }, (_, index) => ({
    candidateId: `proposal-${index}`, kind: "instrument", tag: `AI-${index}`,
    geometry: { bbox: { x: .05 * index, y: .2, width: .02, height: .03 } },
  }));
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      document: { id: "t019-demo-img6807", name: "IMG_6807.JPG", sourceType: "image", status: "ready" },
      page: { id: "page-1", documentId: "t019-demo-img6807", pageNumber: 1, imageUri: "/page.jpg", widthPx: 20, heightPx: 10 },
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      schemaVersion: "0.1", documentId: "t019-demo-img6807",
      entities: [persistedEntity, { ...persistedEntity, id: "entity-2", tag: "TV_0806B" }],
      connections: [persistedConnection], metadata: {},
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      snapshotLabel: "MODEL OUTPUT SNAPSHOT — NOT BENCHMARK TRUTH",
      sourceFilename: "IMG_6807.JPG", candidates: proposals,
    }) });
  vi.stubGlobal("fetch", fetchMock);

  render(<Home />);
  await screen.findByRole("img", { name: "Interactive page 1 of IMG_6807.JPG" });
  await waitFor(() => expect(screen.getByTestId("viewer-counts")).toHaveTextContent("2|1|8"));
  expect(fetchMock).toHaveBeenCalledWith("/api/demo/t019/proposals");
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

test("successful entity PATCH creates one inverse-PATCH undo entry", async () => {
  window.history.replaceState(null, "", "/?documentId=doc-1");
  const saved = { ...persistedEntity, tag: "P-NEW" };
  const restored = { ...persistedEntity, updatedAt: "2026-01-02T00:00:00Z" };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ document: { id: "doc-1", name: "saved.png", sourceType: "image", status: "ready" }, page: { id: "page-1", documentId: "doc-1", pageNumber: 1, imageUri: "/page.png", widthPx: 20, heightPx: 10 } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ schemaVersion: "0.1", documentId: "doc-1", entities: [persistedEntity], connections: [], metadata: {} }) })
    .mockResolvedValueOnce({ ok: true, json: async () => saved })
    .mockResolvedValueOnce({ ok: true, json: async () => restored });
  vi.stubGlobal("fetch", fetchMock);
  render(<Home />);
  await screen.findByRole("img", { name: "Interactive page 1 of saved.png" });
  fireEvent.click(screen.getByRole("button", { name: "Select fixture entity" }));
  fireEvent.change(screen.getByLabelText("Tag"), { target: { value: "P-NEW" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  const undo = await screen.findByRole("button", { name: "Undo last edit to P-SAVED" });
  fireEvent.click(undo);
  await waitFor(() => expect(screen.getByLabelText("Tag")).toHaveValue("P-SAVED"));
  expect(fetchMock).toHaveBeenNthCalledWith(4, "http://localhost:8000/entities/entity-1",
    expect.objectContaining({ method: "PATCH", body: expect.stringContaining('"tag":"P-SAVED"') }));
  expect(screen.getByRole("button", { name: "Undo last edit" })).toBeDisabled();
});

test("keyboard Delete removes only a selected connection and ignores editable controls", async () => {
  window.history.replaceState(null, "", "/?documentId=doc-1");
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ document: { id: "doc-1", name: "saved.png", sourceType: "image", status: "ready" }, page: { id: "page-1", documentId: "doc-1", pageNumber: 1, imageUri: "/page.png", widthPx: 20, heightPx: 10 } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ schemaVersion: "0.1", documentId: "doc-1", entities: [persistedEntity], connections: [persistedConnection], metadata: {} }) })
    .mockResolvedValueOnce({ ok: true, status: 204 });
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<Home />);
  await screen.findByRole("img", { name: "Interactive page 1 of saved.png" });
  fireEvent.keyDown(window, { key: "Delete" });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "Select fixture connection" }));
  fireEvent.keyDown(screen.getByLabelText("Medium"), { key: "Delete" });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  fireEvent.keyDown(window, { key: "Delete" });
  await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(
    "http://localhost:8000/connections/connection-1", { method: "DELETE" }));
  expect(screen.queryByRole("button", { name: "Select fixture connection" })).not.toBeInTheDocument();
});

test("failed undo preserves current canonical UI state and remains available", async () => {
  window.history.replaceState(null, "", "/?documentId=doc-1");
  const saved = { ...persistedEntity, tag: "P-NEW" };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ document: { id: "doc-1", name: "saved.png", sourceType: "image", status: "ready" }, page: { id: "page-1", documentId: "doc-1", pageNumber: 1, imageUri: "/page.png", widthPx: 20, heightPx: 10 } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ schemaVersion: "0.1", documentId: "doc-1", entities: [persistedEntity], connections: [], metadata: {} }) })
    .mockResolvedValueOnce({ ok: true, json: async () => saved })
    .mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({ detail: "Undo conflict" }) });
  vi.stubGlobal("fetch", fetchMock);
  render(<Home />);
  await screen.findByRole("img", { name: "Interactive page 1 of saved.png" });
  fireEvent.click(screen.getByRole("button", { name: "Select fixture entity" }));
  fireEvent.change(screen.getByLabelText("Tag"), { target: { value: "P-NEW" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  const undo = await screen.findByRole("button", { name: "Undo last edit to P-SAVED" });
  fireEvent.click(undo);
  expect(await screen.findByRole("alert")).toHaveTextContent("Undo conflict");
  expect(screen.getByLabelText("Tag")).toHaveValue("P-NEW");
  expect(screen.getByRole("button", { name: "Undo last edit to P-SAVED" })).toBeEnabled();
});
