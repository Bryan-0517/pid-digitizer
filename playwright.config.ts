import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./apps/web/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "line",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  globalSetup: "./apps/web/e2e/global-setup.ts",
  globalTeardown: "./apps/web/e2e/global-teardown.ts",
  use: {
    baseURL: "http://127.0.0.1:13000",
    browserName: "chromium",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
});
