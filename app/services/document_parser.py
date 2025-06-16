import base64
import magic
import os
import tempfile
import structlog
from typing import Optional

from langchain_community.document_loaders import UnstructuredFileLoader

logger = structlog.get_logger(__name__)

class DocumentParsingService:
    """
    A service to handle the parsing of various document types from byte content.
    """

    def parse_content(self, content_bytes_base64: str) -> Optional[str]:
        """
        Parses the content of a file from a base64 encoded string.

        Args:
            content_bytes_base64: The base64-encoded byte content of the file.

        Returns:
            The extracted text from the document, or None if parsing fails.
        """
        if not content_bytes_base64:
            return None

        try:
            # 1. Decode the base64 string to get the raw bytes
            file_content = base64.b64decode(content_bytes_base64)
            
            # Create a temporary file to hold the content
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name

            # 2. Use UnstructuredFileLoader to load and extract text
            # Unstructured will automatically infer the file type
            loader = UnstructuredFileLoader(tmp_path)
            docs = loader.load()

            # Clean up the temporary file
            os.unlink(tmp_path)

            # 3. Join the content of the loaded documents
            if docs:
                return "\n".join([doc.page_content for doc in docs])
            
            return None

        except Exception as e:
            logger.error("Failed to parse document content", exc_info=e)
            # Ensure temp file is cleaned up on error if it exists
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None

# Create a single, reusable instance of the service
document_parser = DocumentParsingService() 