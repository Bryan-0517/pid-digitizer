from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.documents.service import UploadValidationError, normalize_upload


def png_bytes(width: int = 12, height: int = 8) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


def jpeg_bytes(width: int = 7, height: int = 9, orientation: int | None = None) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (width, height), "white")
    exif = image.getexif()
    if orientation is not None:
        exif[274] = orientation
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def mpo_jpeg_bytes(width: int = 7, height: int = 9) -> bytes:
    output = BytesIO()
    first = Image.new("RGB", (width, height), "white")
    second = Image.new("RGB", (width, height), "black")
    first.save(output, format="MPO", save_all=True, append_images=[second])
    return output.getvalue()


def pdf_bytes(page_count: int) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids [{' '.join(f'{3 + index * 2} 0 R' for index in range(page_count))}] "
            f"/Count {page_count} >>"
        ).encode(),
    ]
    for index in range(page_count):
        page_number = 3 + index * 2
        content_number = page_number + 1
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 50] "
                    f"/Contents {content_number} 0 R >>"
                ).encode(),
                b"<< /Length 0 >>\nstream\n\nendstream",
            ]
        )
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    result.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        result.extend(f"{offset:010} 00000 n \n".encode())
    result.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(result)


def create_document(client: TestClient, source_type: str = "image") -> dict[str, object]:
    response = client.post(
        "/documents", json={"name": "diagram", "sourceType": source_type}
    )
    assert response.status_code == 201
    return response.json()


def test_png_upload_persists_document_and_page(client: TestClient, tmp_path: Path) -> None:
    created = create_document(client)

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": ("diagram.png", png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    detail = response.json()
    assert detail["document"]["status"] == "ready"
    assert detail["page"]["pageNumber"] == 1
    assert detail["page"]["widthPx"] == 12
    assert detail["page"]["heightPx"] == 8
    assert (tmp_path / created["id"] / "source.png").is_file()
    assert (tmp_path / detail["page"]["imageUri"].removeprefix("/files/")).is_file()

    persisted = client.get(f"/documents/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == detail


@pytest.mark.parametrize("filename", ["diagram.jpg", "IMG_6754.JPG", "diagram.jpeg", "diagram.JPEG"])
def test_jpg_and_jpeg_filenames_are_supported_case_insensitively(
    client: TestClient, filename: str
) -> None:
    created = create_document(client)

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": (filename, jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["page"]["widthPx"] == 7


@pytest.mark.parametrize("filename", ["IMG_6754.JPG", "camera.jpeg"])
def test_camera_jpeg_with_exif_orientation_is_decoded(
    client: TestClient, filename: str
) -> None:
    created = create_document(client)

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": (filename, jpeg_bytes(7, 9, orientation=6), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["page"]["widthPx"] == 9
    assert response.json()["page"]["heightPx"] == 7


def test_camera_mpo_jpeg_container_is_accepted_as_jpeg(client: TestClient) -> None:
    created = create_document(client)

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": ("IMG_6754.JPG", mpo_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["page"]["widthPx"] == 7


@pytest.mark.parametrize("filename", ["diagram.png", "diagram.PNG"])
def test_png_filename_is_supported_case_insensitively(client: TestClient, filename: str) -> None:
    created = create_document(client)

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": (filename, png_bytes(), "image/png")},
    )

    assert response.status_code == 200


def test_single_page_pdf_is_rendered_to_png(client: TestClient) -> None:
    created = create_document(client, "pdf")

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": ("diagram.pdf", pdf_bytes(1), "application/pdf")},
    )

    assert response.status_code == 200
    page = response.json()["page"]
    assert page["imageUri"].endswith(".png")
    assert page["widthPx"] == 200
    assert page["heightPx"] == 100


def test_multi_page_pdf_returns_clear_v01_error(client: TestClient) -> None:
    created = create_document(client, "pdf")

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": ("diagram.pdf", pdf_bytes(2), "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "v0.1 supports single-page PDFs only"}
    assert client.get(f"/documents/{created['id']}").json()["document"]["status"] == "error"


def test_unsupported_content_returns_clear_v01_error(client: TestClient) -> None:
    created = create_document(client)

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": ("diagram.gif", b"GIF89a", "image/gif")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "v0.1 supports only PNG, JPG/JPEG, or single-page PDF files"
    }


def test_supported_extension_does_not_bypass_content_validation(client: TestClient) -> None:
    created = create_document(client)

    response = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": ("fake.JPG", b"not an image", "image/jpeg")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Image validation failed: Pillow could not identify the uploaded image data"
    }


def test_unsupported_declared_source_type_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/documents", json={"name": "diagram", "sourceType": "spreadsheet"}
    )

    assert response.status_code == 422


def test_invalid_pdf_is_rejected() -> None:
    with pytest.raises(UploadValidationError, match="not a valid PDF"):
        normalize_upload(b"not a pdf", "pdf")
