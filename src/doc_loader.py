"""
doc_loader.py — Architecture document loader.

Purpose:
    Accepts one or more file paths or URLs pointing to architecture /
    compliance documents, extracts their plain-text content, and returns
    the results as ArchitectureDoc objects.
    Supports three input types per source:
        - 'pdf'  : Local PDF file  (parsed via pdfminer.six)
        - 'url'  : HTTPS web page  (scraped via requests + BeautifulSoup)
        - 'text' : Plain .txt / .md file (read directly)

How it fits in the pipeline:
    cli.py  ──calls──>  load_documents()  ──returns──>  List[ArchitectureDoc]
"""

import re
from io import StringIO
from pathlib import Path
from typing import List

import requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams

from src.types import ArchitectureDoc


def _load_pdf(path: str) -> str:
    """Extract plain text from a local PDF file using pdfminer.six."""
    output = StringIO()
    with open(path, "rb") as pdf_file:
        extract_text_to_fp(pdf_file, output, laparams=LAParams(), output_type="text", codec="utf-8")
    return output.getvalue().strip()


def _load_url(url: str) -> str:
    """Fetch a web page and extract its visible text using BeautifulSoup."""
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _load_text(path: str) -> str:
    """Read a plain text or markdown file directly."""
    return Path(path).read_text(encoding="utf-8").strip()


def load_document(source: str) -> ArchitectureDoc:
    """
    Detect the document type and delegate to the correct loader.

    Detection logic:
        1. Starts with 'http://' or 'https://' → URL loader.
        2. Ends with '.pdf'                    → PDF loader.
        3. Anything else                        → plain text loader.

    Args:
        source: File path (PDF, .txt, .md) or HTTPS URL.

    Returns:
        ArchitectureDoc with source, extracted content, and doc_type set.

    Raises:
        ValueError        : If source is empty.
        FileNotFoundError : If a local file path does not exist.
        requests.HTTPError: If a URL returns an error response.
    """
    if not source:
        raise ValueError("Document source cannot be empty.")

    if source.startswith("http://") or source.startswith("https://"):
        content = _load_url(source)
        doc_type = "url"
    elif source.lower().endswith(".pdf"):
        content = _load_pdf(source)
        doc_type = "pdf"
    else:
        content = _load_text(source)
        doc_type = "text"

    return ArchitectureDoc(source=source, content=content, doc_type=doc_type)


def load_documents(sources: List[str]) -> List[ArchitectureDoc]:
    """
    Load one or more compliance / architecture documents.

    Each source is processed independently via :func:`load_document`, so
    any mix of PDFs, URLs, and plain-text files is valid.

    Args:
        sources: Non-empty list of file paths or URLs.

    Returns:
        List of ArchitectureDoc objects in the same order as *sources*.

    Raises:
        ValueError: If *sources* is empty.
        Any exception raised by individual document loaders is propagated
        to the caller so that a single bad source does not silently produce
        an empty document set.
    """
    if not sources:
        raise ValueError("At least one compliance document source must be provided.")
    return [load_document(s) for s in sources]

