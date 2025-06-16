class ServiceError(Exception):
    """Base exception class for service layer errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class EmailNotFoundError(ServiceError):
    """Raised when an email message cannot be found in Microsoft Graph."""
    def __init__(self, message_id: str):
        super().__init__(f"Email with message_id '{message_id}' not found.", status_code=404)


class GraphApiError(ServiceError):
    """Custom exception for errors related to the Microsoft Graph API."""
    def __init__(self, message: str):
        super().__init__(message, status_code=502) # 502 Bad Gateway


class SummarizationError(ServiceError):
    """Custom exception for errors that occur during the summarization process."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class RAGError(ServiceError):
    """Custom exception for errors during RAG chain execution."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500) 