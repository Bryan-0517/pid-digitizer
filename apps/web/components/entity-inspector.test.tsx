import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import type { EngineeringEntity } from "../types/engineering-graph";
import EntityInspector from "./entity-inspector";

const entity: EngineeringEntity = {
  id: "entity-1", documentId: "doc-1", pageId: "page-1", kind: "equipment",
  subtype: "pump", tag: "P-101", displayName: "Feed pump", properties: { service: "water" },
  assertion: { mode: "human_added", reviewStatus: "unreviewed" }, provenance: [],
  geometry: { bbox: { x: 0.1, y: 0.1, width: 0.2, height: 0.2 } },
  createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

test("shows an empty state without a selected entity", () => {
  render(<EntityInspector entity={null} apiUrl="http://localhost:8000" onSaved={vi.fn()} />);
  expect(screen.getByText("Select an entity to inspect it.")).toBeInTheDocument();
});

test("selection populates editable and read-only fields", () => {
  render(<EntityInspector entity={entity} apiUrl="http://localhost:8000" onSaved={vi.fn()} />);
  expect(screen.getByLabelText("Tag")).toHaveValue("P-101");
  expect(screen.getByLabelText("Display name")).toHaveValue("Feed pump");
  expect(screen.getByText("entity-1")).toBeInTheDocument();
});

test("successful save returns the persisted entity", async () => {
  const saved = { ...entity, tag: "P-202", displayName: "Saved pump", assertion: { ...entity.assertion, reviewStatus: "corrected" as const } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => saved }));
  const onSaved = vi.fn();
  render(<EntityInspector entity={entity} apiUrl="http://localhost:8000" onSaved={onSaved} />);
  fireEvent.change(screen.getByLabelText("Tag"), { target: { value: "P-202" } });
  fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Saved pump" } });
  fireEvent.change(screen.getByLabelText("Review status"), { target: { value: "corrected" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved));
});

test("API failure does not commit canonical state and cancel restores values", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false, status: 422, json: async () => ({ detail: "invalid entity" }),
  }));
  const onSaved = vi.fn();
  render(<EntityInspector entity={entity} apiUrl="http://localhost:8000" onSaved={onSaved} />);
  fireEvent.change(screen.getByLabelText("Tag"), { target: { value: "UNSAVED" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("invalid entity"));
  expect(onSaved).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByLabelText("Tag")).toHaveValue("P-101");
});
