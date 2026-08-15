import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import Home from "./page";
import { sourceTypeForFilename } from "./upload-validation";

vi.mock("../components/diagram-viewer", () => ({
  default: ({ documentName }: { documentName: string }) => (
    <div role="img" aria-label={`Interactive page 1 of ${documentName}`} />
  ),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
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
  expect(fetchMock).toHaveBeenCalledTimes(2);
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
