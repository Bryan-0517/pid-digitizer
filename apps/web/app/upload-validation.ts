export const supportedInputMessage =
  "v0.1 supports only PNG, JPG/JPEG, or single-page PDF files";

export function sourceTypeForFilename(filename: string): "image" | "pdf" | null {
  const suffix = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  if ([".png", ".jpg", ".jpeg"].includes(suffix)) return "image";
  if (suffix === ".pdf") return "pdf";
  return null;
}
