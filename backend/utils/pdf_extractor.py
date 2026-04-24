"""
PDF text extraction.

Location: backend/utils/pdf_extractor.py
Imported by: backend/lambda_functions/handler.py  (via sys.path → backend/)

Downloads a PDF from S3 and extracts text using PyMuPDF (fitz).
Falls back to pdfminer if fitz is unavailable.
"""
import io
import logging

import boto3

logger = logging.getLogger(__name__)
s3 = boto3.client("s3")


def extract_text_from_s3(bucket: str, key: str) -> str:
    """Download PDF from S3 and return extracted text."""
    logger.info("Downloading s3://%s/%s", bucket, key)
    obj = s3.get_object(Bucket=bucket, Key=key)
    pdf_bytes = obj["Body"].read()
    return extract_text_from_bytes(pdf_bytes)


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text from raw PDF bytes. Tries PyMuPDF first, then pdfminer."""
    try:
        import fitz  # PyMuPDF
        return _extract_with_pymupdf(pdf_bytes)
    except ImportError:
        logger.warning("PyMuPDF not available, trying pdfminer")

    try:
        from pdfminer.high_level import extract_text as pm_extract
        return pm_extract(io.BytesIO(pdf_bytes))
    except ImportError:
        logger.error("Neither PyMuPDF nor pdfminer available")
        raise RuntimeError(
            "No PDF extraction library available. "
            "Install PyMuPDF or pdfminer.six."
        )


def _extract_with_pymupdf(pdf_bytes: bytes) -> str:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n\n".join(pages)
    logger.info("Extracted %d chars from %d pages", len(text), len(pages))
    return text