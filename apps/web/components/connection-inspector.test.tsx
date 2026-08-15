import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import ConnectionInspector, { entityOptionLabel } from "./connection-inspector";
import type { EngineeringConnection, EngineeringEntity } from "../types/engineering-graph";

const entities = [
  entity("e1", { tag: "P-1" }),
  entity("e2", { displayName: "Display valve" }),
  entity("e3", {}),
];
const connection: EngineeringConnection = {
  id: "c1", documentId: "doc-1", sourceEntityId: "e1", targetEntityId: "e2",
  kind: "process", medium: "water", direction: "source_to_target", properties: { line: 1 },
  assertion: { mode: "human_added", reviewStatus: "unreviewed" }, provenance: [],
  createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z",
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

test("populates fields and entity labels use tag, display name, then id", () => {
  renderInspector();
  expect(screen.getByLabelText("Source entity")).toHaveValue("e1");
  expect(screen.getByLabelText("Target entity")).toHaveValue("e2");
  expect(screen.getByLabelText("Medium")).toHaveValue("water");
  expect(entityOptionLabel(entities[0])).toBe("P-1");
  expect(entityOptionLabel(entities[1])).toBe("Display valve");
  expect(entityOptionLabel(entities[2])).toBe("e3");
  expect(screen.getByText(/No diagram geometry; this semantic connection/)).toBeInTheDocument();
});

test("cancel restores persisted values", () => {
  renderInspector();
  fireEvent.change(screen.getByLabelText("Medium"), { target: { value: "steam" } });
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByLabelText("Medium")).toHaveValue("water");
});

test("save commits only after a successful API response", async () => {
  const saved = { ...connection, medium: "steam" };
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => saved });
  vi.stubGlobal("fetch", fetchMock);
  const onSaved = vi.fn();
  renderInspector({ onSaved });
  fireEvent.change(screen.getByLabelText("Medium"), { target: { value: "steam" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved));
  expect(fetchMock).toHaveBeenCalledWith("http://api/connections/c1", expect.objectContaining({ method: "PATCH" }));
});

test("API failure does not commit connection state", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: "invalid target" }) }));
  const onSaved = vi.fn();
  renderInspector({ onSaved });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("invalid target");
  expect(onSaved).not.toHaveBeenCalled();
});

test("creates a geometry-less connection and deletes after confirmation", async () => {
  const created = { ...connection, id: "new-c", geometry: undefined };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => created })
    .mockResolvedValueOnce({ ok: true, status: 204 });
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const onCreated = vi.fn();
  const onDeleted = vi.fn();
  const view = renderInspector({ connection: null, onCreated, onDeleted });
  fireEvent.click(screen.getByRole("button", { name: "Create connection" }));
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(created));
  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://api/documents/doc-1/connections", expect.objectContaining({ method: "POST" }));

  view.rerender(component({ onDeleted }));
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("c1"));
  expect(fetchMock).toHaveBeenNthCalledWith(2, "http://api/connections/c1", { method: "DELETE" });
});

function renderInspector(overrides: Partial<React.ComponentProps<typeof ConnectionInspector>> = {}) {
  return render(component(overrides));
}

function component(overrides: Partial<React.ComponentProps<typeof ConnectionInspector>> = {}) {
  return <ConnectionInspector apiUrl="http://api" documentId="doc-1" entities={entities}
    connections={[connection]} connection={connection} onSelect={vi.fn()} onCreated={vi.fn()}
    onSaved={vi.fn()} onDeleted={vi.fn()} {...overrides} />;
}

function entity(id: string, labels: Partial<EngineeringEntity>): EngineeringEntity {
  return { id, documentId: "doc-1", pageId: "page-1", kind: "equipment", properties: {},
    assertion: { mode: "human_added", reviewStatus: "unreviewed" }, provenance: [],
    createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z", ...labels };
}
