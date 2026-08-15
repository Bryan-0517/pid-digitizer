import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import Home from "./page";

afterEach(() => vi.restoreAllMocks());

test("displays API health", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ status: "ok", service: "api" }),
  }));
  render(<Home />);
  await waitFor(() => expect(screen.getByText("API: ok")).toBeInTheDocument());
});
