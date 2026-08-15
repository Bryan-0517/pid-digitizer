import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  if (request.nextUrl.searchParams.get("screen") !== "IMG_6807.JPG") {
    return NextResponse.json({ detail: "Unsupported hydrolysis benchmark screen" }, { status: 404 });
  }
  const root = path.resolve(process.cwd(), "../../benchmarks/hydrolysis");
  const [page, graph] = await Promise.all([
    readFile(path.join(root, "expected/pages/IMG_6807.page.json"), "utf8"),
    readFile(path.join(root, "expected/engineering_graph.json"), "utf8"),
  ]);
  return NextResponse.json({ page: JSON.parse(page), graph: JSON.parse(graph) });
}
