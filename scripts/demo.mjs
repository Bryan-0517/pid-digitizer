import { execFileSync } from "node:child_process";

const compose = ["compose", "--project-name", "pid-digitizer-demo", "--file", "compose.demo.yaml"];

function runDocker(args, capture = false) {
  return execFileSync("docker", [...compose, ...args], {
    cwd: process.cwd(), encoding: "utf8", stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
  })?.trim();
}

async function waitFor(url) {
  let lastError;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastError = new Error(`${url} returned ${response.status}`);
    } catch (error) { lastError = error; }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw lastError ?? new Error(`${url} did not become ready`);
}

function helper(command) {
  const output = runDocker(["exec", "--no-TTY", "api", "python", "/app/demo-helper/t019_demo.py", command], true);
  process.stdout.write(`${output}\n`);
}

async function checkProposalOverlays() {
  const response = await fetch("http://127.0.0.1:14000/api/demo/t019/proposals");
  if (!response.ok) throw new Error(`proposal overlay check returned ${response.status}`);
  const payload = await response.json();
  const candidates = payload.candidates ?? [];
  if (payload.sourceFilename !== "IMG_6807.JPG" || candidates.length !== 8) {
    throw new Error("proposal overlay payload does not contain the expected eight presentation candidates");
  }
  if (candidates.some((candidate) => ["FI_0828", "FV_0827"].includes(candidate.tag))) {
    throw new Error("proposal overlay payload duplicates a prepared canonical tag");
  }
  const expectedIds = [
    "equipment_boundary:r0c0:cand-1",
    "equipment_boundary:r0c0:cand-6",
    "equipment_boundary:r0c0:cand-7",
    "equipment_boundary:r1c1:bdry-top-header",
    "equipment_boundary:r1c1:bdry-inlet-D",
    "equipment_boundary:r1c1:bdry-inlet-F",
    "equipment_boundary:r1c1:bdry-inlet-G",
    "equipment_boundary:r1c1:bdry-bottom-header",
  ];
  if (JSON.stringify(candidates.map((candidate) => candidate.candidateId)) !== JSON.stringify(expectedIds)) {
    throw new Error("proposal overlay payload differs from the manually verified presentation allowlist");
  }
  process.stdout.write(`${JSON.stringify({ proposalOverlayStatus: "ready", proposalOverlayCount: candidates.length,
    proposalOverlayCandidateIds: expectedIds })}\n`);
}

const command = process.argv[2];
if (command === "start") {
  runDocker(["up", "--detach", "--build"]);
  await waitFor("http://127.0.0.1:19000/health");
  await waitFor("http://127.0.0.1:14000");
  process.stdout.write("Demo services ready. Run npm run demo:setup.\n");
} else if (command === "setup" || command === "reset") {
  await waitFor("http://127.0.0.1:19000/health");
  helper("setup");
  process.stdout.write("Demo URL: http://127.0.0.1:14000/?documentId=t019-demo-img6807\n");
} else if (command === "check") {
  await waitFor("http://127.0.0.1:19000/health");
  await waitFor("http://127.0.0.1:14000");
  helper("check");
  await checkProposalOverlays();
} else if (command === "cleanup") {
  runDocker(["down", "--volumes", "--remove-orphans"]);
} else {
  throw new Error("Usage: node scripts/demo.mjs start|setup|check|reset|cleanup");
}
