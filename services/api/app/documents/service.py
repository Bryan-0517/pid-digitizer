from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

SUPPORTED_INPUT_MESSAGE = "v0.1 supports only PNG, JPG/JPEG, or single-page PDF files"


class UploadValidationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedPage:
    image: Image.Image
    source_extension: str
    extension: str = "png"


def normalize_upload(content: bytes, declared_source_type: str) -> NormalizedPage:
    if declared_source_type == "image":
        return _normalize_image(content)
    if declared_source_type == "pdf":
        return _normalize_pdf(content)
    raise UploadValidationError(SUPPORTED_INPUT_MESSAGE)


def validate_upload_filename(filename: str | None, declared_source_type: str) -> None:
    suffix = Path(filename or "").suffix.lower()
    source_type = "pdf" if suffix == ".pdf" else "image" if suffix in {".png", ".jpg", ".jpeg"} else None
    if source_type is None or source_type != declared_source_type:
        raise UploadValidationError(SUPPORTED_INPUT_MESSAGE)


def save_page(page: NormalizedPage, storage_dir: Path, document_id: str, page_id: str) -> str:
    relative_path = Path(document_id) / f"{page_id}.{page.extension}"
    destination = storage_dir / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    page.image.save(destination, format="PNG")
    return f"/files/{relative_path.as_posix()}"


def save_source(content: bytes, page: NormalizedPage, storage_dir: Path, document_id: str) -> None:
    destination = storage_dir / document_id / f"source.{page.source_extension}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def _normalize_image(content: bytes) -> NormalizedPage:
    try:
        with Image.open(BytesIO(content)) as candidate:
            detected_format = candidate.format
            candidate.verify()
    except UnidentifiedImageError as exc:
        raise UploadValidationError(
            "Image validation failed: Pillow could not identify the uploaded image data"
        ) from exc
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise UploadValidationError(f"Image validation failed: {exc}") from exc

    if detected_format not in {"PNG", "JPEG", "MPO"}:
        raise UploadValidationError(
            f"Unsupported decoded image format: {detected_format or 'unknown'}; expected PNG or JPEG"
        )

    try:
        with Image.open(BytesIO(content)) as decoded:
            decoded.load()
            normalized = ImageOps.exif_transpose(decoded).convert("RGB")
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise UploadValidationError(f"Image decoding failed: {exc}") from exc

    source_extension = "png" if detected_format == "PNG" else "jpg"
    return NormalizedPage(normalized, source_extension=source_extension)


def _normalize_pdf(content: bytes) -> NormalizedPage:
    try:
        pdf = pdfium.PdfDocument(content)
    except Exception as exc:
        raise UploadValidationError("The uploaded file is not a valid PDF") from exc
    try:
        if len(pdf) != 1:
            raise UploadValidationError("v0.1 supports single-page PDFs only")
        bitmap = pdf[0].render(scale=2)
        return NormalizedPage(bitmap.to_pil().convert("RGB"), source_extension="pdf")
    finally:
        pdf.close()
