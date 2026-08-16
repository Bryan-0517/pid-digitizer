import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import DexpiValidation from "./dexpi-validation";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const report = {
  boundaryVersion: "internal-v0.1",
  targetDexpiVersion: null,
  conformanceValidated: false,
  status: "blocked",
  graphFields: [],
  counts: {
    supportedObjects: 1, partialObjects: 1, unmappedObjects: 1, blockedObjects: 1,
    supportedFields: 12, unmappedFields: 3, blockedFields: 1,
  },
  preview: { boundaryVersion: "internal-v0.1", targetDexpiVersion: null, conformant: false, objects: [] },
  warnings: ["Version-neutral preflight only; this report is not DEXPI conformance certification."],
  objects: [
    {
      objectType: "entity", canonicalId: "entity-ok", kind: "equipment", label: "P-101",
      disposition: "supported", assertion: { mode: "observed", reviewStatus: "confirmed" },
      fields: [{ path: "tag", disposition: "supported", reasonCode: "supported_internal_v01", message: "Supported", value: "P-101" }],
    },
    {
      objectType: "entity", canonicalId: "entity-partial", kind: "valve", label: "V-201",
      disposition: "partial", assertion: { mode: "human_added", reviewStatus: "corrected" },
      fields: [{ path: "properties.custom", disposition: "unmapped", reasonCode: "unmapped_arbitrary_property", message: "Preserved", value: 1 }],
    },
    {
      objectType: "entity", canonicalId: "entity-text", kind: "text",
      disposition: "unmapped", assertion: { mode: "observed", reviewStatus: "confirmed" },
      fields: [{ path: "kind", disposition: "unmapped", reasonCode: "unmapped_entity_kind", message: "Unsupported kind", value: "text" }],
    },
    {
      objectType: "connection", canonicalId: "edge-blocked", kind: "process",
      disposition: "blocked", assertion: { mode: "inferred", reviewStatus: "unreviewed" },
      fields: [{ path: "assertion.mode", disposition: "blocked", reasonCode: "blocked_inferred_assertion", message: "Inferred", value: "inferred" }],
    },
  ],
} as const;

test("runs validation and renders statuses, counts, unmapped fields, and blocked reasons", async () => {
  const selectEntity = vi.fn();
  const selectConnection = vi.fn();
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => report })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      enabled: true, available: true, pydexpiVersion: "1.2.0", targetDexpiVersion: "1.3",
      artifactLabel: "pyDEXPI 1.2.0 / DEXPI 1.3 compatibility JSON",
    }) });
  vi.stubGlobal("fetch", fetchMock);
  render(<DexpiValidation
    apiUrl="http://api" documentId="doc-1"
    onSelectEntity={selectEntity} onSelectConnection={selectConnection}
  />);

  fireEvent.click(screen.getByRole("button", { name: "Run validation" }));
  await waitFor(() => expect(screen.getByText("blocked", { selector: "dd" })).toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledWith("http://api/documents/doc-1/dexpi/validate", { method: "POST" });
  expect(fetchMock).toHaveBeenCalledWith("http://api/documents/doc-1/dexpi/export/availability");
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByText("Partial / unmapped")).toBeInTheDocument();
  expect(screen.getByText("Blocked")).toBeInTheDocument();

  const partial = screen.getByText(/entity-partial/).closest("details")!;
  fireEvent.click(within(partial).getByText(/entity-partial/));
  expect(within(partial).getByText("properties.custom")).toBeInTheDocument();
  expect(within(partial).getByText("unmapped_arbitrary_property")).toBeInTheDocument();
  const blocked = screen.getByRole("button", { name: "edge-blocked" }).closest("details")!;
  fireEvent.click(within(blocked).getByText(/edge-blocked/));
  expect(within(blocked).getByText("blocked_inferred_assertion")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "entity-ok" }));
  fireEvent.click(screen.getByRole("button", { name: "edge-blocked" }));
  expect(selectEntity).toHaveBeenCalledWith("entity-ok");
  expect(selectConnection).toHaveBeenCalledWith("edge-blocked");
  expect(screen.getByText("Compatibility spike export")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download compatibility JSON" })).toBeDisabled();
});

test("downloads enabled compatibility JSON without changing inspector selection", async () => {
  const readyReport = { ...report, status: "partial", objects: report.objects.slice(0, 3), counts: {
    ...report.counts, blockedObjects: 0, blockedFields: 0,
  } };
  const conversionReport = {
    status: "ready", pydexpiVersion: "1.2.0", targetDexpiVersion: "1.3",
    conformanceValidated: false, artifactLabel: "pyDEXPI 1.2.0 / DEXPI 1.3 compatibility JSON",
    includedObjects: [{ canonicalId: "entity-ok" }], omittedObjects: [{ canonicalId: "entity-text" }],
    omittedFields: [], blockingObjects: [], warnings: ["Compatibility spike only."],
  };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => readyReport })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      enabled: true, available: true, pydexpiVersion: "1.2.0", targetDexpiVersion: "1.3",
      artifactLabel: "pyDEXPI 1.2.0 / DEXPI 1.3 compatibility JSON",
    }) })
    .mockResolvedValueOnce({ ok: true, headers: new Headers({
      "content-disposition": 'attachment; filename="doc-1.dexpi-1.3.pydexpi.json"',
    }), json: async () => ({ conversionReport }) });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  const selectEntity = vi.fn();
  const selectConnection = vi.fn();
  render(<DexpiValidation apiUrl="http://api" documentId="doc-1"
    onSelectEntity={selectEntity} onSelectConnection={selectConnection} />);
  fireEvent.click(screen.getByRole("button", { name: "Run validation" }));
  await screen.findByRole("button", { name: "Download compatibility JSON" });
  fireEvent.click(screen.getByRole("button", { name: "Download compatibility JSON" }));
  await waitFor(() => expect(click).toHaveBeenCalled());
  expect(screen.getByText("Included: 1; omitted/unmapped: 1.")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenLastCalledWith("http://api/documents/doc-1/dexpi/export", { method: "POST" });
  expect(selectEntity).not.toHaveBeenCalled();
  expect(selectConnection).not.toHaveBeenCalled();
  click.mockRestore();
});

test("shows validation errors without selecting or mutating graph state", async () => {
  const selectEntity = vi.fn();
  const selectConnection = vi.fn();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false, status: 500, json: async () => ({ detail: "Preflight unavailable" }),
  }));
  render(<DexpiValidation
    apiUrl="http://api" documentId="doc-1"
    onSelectEntity={selectEntity} onSelectConnection={selectConnection}
  />);
  fireEvent.click(screen.getByRole("button", { name: "Run validation" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Preflight unavailable");
  expect(selectEntity).not.toHaveBeenCalled();
  expect(selectConnection).not.toHaveBeenCalled();
});
