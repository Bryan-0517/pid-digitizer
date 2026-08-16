import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import GraphChat from "./graph-chat";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("submits a deterministic request and renders answer, warnings, and supporting IDs", async () => {
  const onHighlight = vi.fn();
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      outcome: "ok",
      resolvedIntent: { operation: "neighbors", references: ["P-101"], resolvedEntityIds: ["a"] },
      queryResults: [],
      answer: "P-101 has 2 directly connected canonical entities.",
      supportingEntityIds: ["a", "b", "c"],
      supportingConnectionIds: ["edge-1", "edge-2"],
      highlight: { entityIds: ["a", "b", "c"], connectionIds: ["edge-1", "edge-2"] },
      warnings: [{
        code: "uncertain_connection",
        message: "Canonical connection edge-1 is not verified.",
        provenance: [],
      }],
    }),
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<GraphChat apiUrl="http://api" documentId="doc-1" onHighlight={onHighlight} />);

  fireEvent.change(screen.getByLabelText("Question"), {
    target: { value: "What is connected to P-101?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask graph" }));

  await waitFor(() => expect(screen.getByText(/2 directly connected/)).toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledWith("http://api/documents/doc-1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "What is connected to P-101?", verbalize: false }),
  });
  expect(screen.getByLabelText("Graph query warnings")).toHaveTextContent("not verified");
  expect(screen.getByText("a, b, c")).toBeInTheDocument();
  expect(screen.getByText("edge-1, edge-2")).toBeInTheDocument();
  expect(onHighlight).toHaveBeenCalledWith(["a", "b", "c"], ["edge-1", "edge-2"]);
});

test("renders an API error without changing highlights", async () => {
  const onHighlight = vi.fn();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false,
    status: 500,
    json: async () => ({ detail: "Query unavailable" }),
  }));
  render(<GraphChat apiUrl="http://api" documentId="doc-1" onHighlight={onHighlight} />);
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Find P-101" } });
  fireEvent.submit(screen.getByLabelText("Question").closest("form")!);
  expect(await screen.findByRole("alert")).toHaveTextContent("Query unavailable");
  expect(onHighlight).not.toHaveBeenCalled();
});
