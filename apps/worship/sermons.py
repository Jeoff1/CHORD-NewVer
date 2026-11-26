"""The sermon PDF a pastor attaches to a theme (Phase 9C).

The file is checked (a real PDF, not too big), and its text is read once,
when it is attached, so the search worker never opens PDFs. A scanned PDF
has no text to read: it is kept for the pastor, and suggestions use the
title, passage and notes only. The text never leaves the installation and
is never logged.
"""

import logging

from django.core.exceptions import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_BYTES = 15 * 1024 * 1024
MAX_PAGES = 200
MAX_CHARACTERS = 200_000

logger = logging.getLogger(__name__)


def check(upload):
    """Refuse a file that isn't a PDF or is too big."""
    if not upload.name.lower().endswith(".pdf"):
        raise ValidationError("Choose a PDF file.")
    if upload.size > MAX_BYTES:
        raise ValidationError("The PDF must be 15 MB or smaller.")
    upload.seek(0)
    header = upload.read(5)
    upload.seek(0)
    if header != b"%PDF-":
        raise ValidationError("This file isn't a PDF.")


def read_text(upload):
    """The text of the PDF's pages ("" when it has none, such as a scanned
    PDF). Raises ``ValidationError`` when the PDF can't be opened at all
    (damaged, or locked with a password)."""
    upload.seek(0)
    try:
        reader = PdfReader(upload)
        if reader.is_encrypted:
            raise ValidationError(
                "This PDF is locked with a password. Save it without one and "
                "attach it again."
            )
        pages = []
        for page in reader.pages[:MAX_PAGES]:
            pages.append(page.extract_text() or "")
    except ValidationError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as error:
        # Only the kind of failure, never the content.
        logger.info("A sermon PDF couldn't be read: %s", type(error).__name__)
        raise ValidationError(
            "This PDF couldn't be read. It may be damaged."
        ) from error
    finally:
        upload.seek(0)
    text = "\n".join(" ".join(page.split()) for page in pages if page.strip())
    return text[:MAX_CHARACTERS]
