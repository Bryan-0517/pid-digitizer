"use client";

import React, { useEffect, useState } from "react";

type Health = { status: string; service: string };

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${apiUrl}/health`)
      .then((response) => {
        if (!response.ok) throw new Error("API health check failed");
        return response.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch(() => setError(true));
  }, []);

  return (
    <main>
      <h1>P&amp;ID Digitizer</h1>
      <p>Web: ready</p>
      <p aria-live="polite">
        API: {error ? "unavailable" : health?.status ?? "checking..."}
      </p>
    </main>
  );
}
