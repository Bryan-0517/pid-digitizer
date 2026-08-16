import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { composeArgs } from "./environment";

const imagePath = path.resolve("benchmarks/hydrolysis/images/IMG_6807.JPG");
const editedDisplayName = "T018 persisted edit";

function apiHelper(args: string[]): string {
  return execFileSync("docker", [...composeArgs, "exec", "--no-TTY", "api",
    "python", "/app/e2e_seed.py", ...args], {
    cwd: process.cwd(), encoding: "utf8", stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

test("IMG_6807 persisted edit, deterministic topology chat, and canvas highlight", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Engineering diagram").setInputFiles(imagePath);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByRole("heading", { name: "IMG_6807.JPG" })).toBeVisible();
  await expect(page.getByText(/empty canonical graph/i)).toBeVisible();

  const documentId = new URL(page.url()).searchParams.get("documentId");
  expect(documentId).toBeTruthy();
  const documentResponse = await page.request.get(`http://127.0.0.1:18000/documents/${documentId}`);
  expect(documentResponse.ok()).toBeTruthy();
  const detail = await documentResponse.json() as { document: { id: string; status: string };
    page: { id: string; documentId: string } };
  expect(detail.document).toMatchObject({ id: documentId, status: "ready" });
  expect(detail.page.documentId).toBe(documentId);

  const seeded = JSON.parse(apiHelper(["seed", documentId!, detail.page.id])) as {
    entityIds: string[]; connectionIds: string[];
  };
  expect(seeded.entityIds).toEqual(["t018:e2e-source", "t018:e2e-neighbor"]);
  expect(seeded.connectionIds).toEqual(["t018:e2e-process-connection"]);

  await page.goto(`/?documentId=${encodeURIComponent(documentId!)}`);
  const viewer = page.getByRole("img", { name: "Interactive page 1 of IMG_6807.JPG" });
  await expect(viewer).toBeVisible();

  const box = await viewer.boundingBox();
  expect(box).not.toBeNull();
  // The 4:3 image is fit inside the viewer; click the center of fixture A's normalized bbox.
  const imageWidth = Math.min(box!.width, box!.height * (5712 / 4284));
  const imageHeight = imageWidth / (5712 / 4284);
  await viewer.click({ position: {
    x: (box!.width - imageWidth) / 2 + imageWidth * .22,
    y: (box!.height - imageHeight) / 2 + imageHeight * .34,
  } });
  await expect(page.getByLabel("Selected entity")).toHaveText("t018:e2e-source");
  await expect(page.getByLabel("Tag")).toHaveValue("T018-A");

  await page.getByLabel("Display name").fill(editedDisplayName);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByLabel("Display name")).toHaveValue(editedDisplayName);

  await page.goto(`/?documentId=${encodeURIComponent(documentId!)}`);
  await expect(viewer).toBeVisible();
  const reloadedBox = await viewer.boundingBox();
  expect(reloadedBox).not.toBeNull();
  const reloadedImageWidth = Math.min(reloadedBox!.width, reloadedBox!.height * (5712 / 4284));
  const reloadedImageHeight = reloadedImageWidth / (5712 / 4284);
  await viewer.click({ position: {
    x: (reloadedBox!.width - reloadedImageWidth) / 2 + reloadedImageWidth * .22,
    y: (reloadedBox!.height - reloadedImageHeight) / 2 + reloadedImageHeight * .34,
  } });
  await expect(page.getByLabel("Display name")).toHaveValue(editedDisplayName);
  const persisted = JSON.parse(apiHelper(["assert-edit", documentId!, editedDisplayName]));
  expect(persisted.displayNameRevisionCount).toBe(1);

  await page.getByLabel("Question").fill("What is connected to T018-A?");
  const chatResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith(`/documents/${documentId}/chat`) && response.request().method() === "POST");
  await page.getByRole("button", { name: "Ask graph" }).click();
  const chatResponse = await chatResponsePromise;
  const chat = await chatResponse.json() as { answer: string; supportingEntityIds: string[];
    supportingConnectionIds: string[]; highlight: { entityIds: string[]; connectionIds: string[] } };
  expect(chat.answer).toBe("T018-A has 1 directly connected canonical entities.");
  expect(chat.supportingEntityIds).toEqual(["t018:e2e-neighbor", "t018:e2e-source"]);
  expect(chat.supportingConnectionIds).toEqual(["t018:e2e-process-connection"]);
  expect(chat.highlight).toEqual({ entityIds: chat.supportingEntityIds,
    connectionIds: chat.supportingConnectionIds });

  await expect(page.getByLabel("Highlighted entities")).toHaveText(
    "t018:e2e-neighbor, t018:e2e-source");
  await expect(page.getByLabel("Highlighted connections")).toHaveText("t018:e2e-process-connection");
  await expect(page.getByLabel("Selected entity")).toHaveText("t018:e2e-source");
});
