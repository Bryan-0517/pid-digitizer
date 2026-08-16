import { dockerCompose, waitForUrl } from "./environment";

export default async function globalSetup(): Promise<void> {
  // This fixed project name scopes destructive cleanup to disposable T018 resources only.
  dockerCompose(["down", "--volumes", "--remove-orphans"]);
  dockerCompose(["up", "--detach", "--build"]);
  await waitForUrl("http://127.0.0.1:18000/health");
  await waitForUrl("http://127.0.0.1:13000");
}
