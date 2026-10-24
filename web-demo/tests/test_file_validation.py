import pytest

from file_validation import MAX_FILE_BYTES, validate_operational_file
from models import ValidationError


def test_validates_csv_metadata_and_integrity_hash():
    validated = validate_operational_file("agenda padrão.csv", b"data;horario\n", "text/csv; charset=utf-8")
    assert validated.extension == "csv"
    assert validated.mime_type == "text/csv"
    assert validated.display_name == "agenda padrão"
    assert len(validated.sha256) == 64


def test_validates_pdf_signature():
    validated = validate_operational_file("guia.pdf", b"%PDF-1.7\nconteudo", "application/pdf")
    assert validated.extension == "pdf"


@pytest.mark.parametrize(
    ("name", "content", "mime"),
    [
        ("../../segredo.csv", b"a;b", "text/csv"),
        ("agenda.exe", b"MZ", "application/octet-stream"),
        ("guia.pdf", b"nao-e-pdf", "application/pdf"),
        ("agenda.csv", b"\xff", "text/csv"),
        ("agenda.csv", b"a;b", "application/pdf"),
    ],
)
def test_rejects_invalid_names_types_and_content(name, content, mime):
    with pytest.raises(ValidationError):
        validate_operational_file(name, content, mime)


def test_rejects_file_above_application_limit():
    with pytest.raises(ValidationError, match="5 MB"):
        validate_operational_file("agenda.csv", b"x" * (MAX_FILE_BYTES + 1), "text/csv")
