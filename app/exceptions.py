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
    """Raised for general errors interacting with the Microsoft Graph API."""
    def __init__(self, message: str):
        super().__init__(f"Microsoft Graph API error: {message}", status_code=502) # Bad Gateway


class SummarizationError(ServiceError):
    """Raised when the LLM fails to generate a summary."""
    def __init__(self, message: str):
        super().__init__(f"Summarization failed: {message}", status_code=500) 