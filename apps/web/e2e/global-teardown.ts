import { dockerCompose } from "./environment";

export default function globalTeardown(): void {
  dockerCompose(["down", "--volumes", "--remove-orphans"]);
}
