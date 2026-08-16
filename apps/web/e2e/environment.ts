import { execFileSync } from "node:child_process";

export const composeArgs = [
  "compose", "--project-name", "pid-digitizer-t018", "--file", "compose.e2e.yaml",
];

export function dockerCompose(args: string[]): string {
  return execFileSync("docker", [...composeArgs, ...args], {
    cwd: process.cwd(), encoding: "utf8", stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

export async function waitForUrl(url: string): Promise<void> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastError = new Error(`${url} returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw lastError instanceof Error ? lastError : new Error(`${url} did not become ready`);
}
