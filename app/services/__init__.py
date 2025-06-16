"""
Initializes the services package, making key functions and classes available
for import from the top-level `app.services` namespace.
"""
from .email import (
    fetch_email_content,
    run_summarization_chain,
    run_bulk_summarization
)
from .document_parser import document_parser

__all__ = [
    "fetch_email_content",
    "run_summarization_chain",
    "run_bulk_summarization",
    "document_parser",
]
