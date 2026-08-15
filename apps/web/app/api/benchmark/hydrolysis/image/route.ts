import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const image = await readFile(
    path.resolve(process.cwd(), "../../benchmarks/hydrolysis/images/IMG_6807.JPG"),
  );
  return new NextResponse(new Uint8Array(image), {
    headers: { "Content-Type": "image/jpeg", "Cache-Control": "public, max-age=3600" },
  });
}
