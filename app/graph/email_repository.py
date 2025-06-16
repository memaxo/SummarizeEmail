import logging
import requests
import structlog
from typing import Dict, Any, List, Optional
from ..auth import get_graph_token
from ..config import settings
from ..exceptions import EmailNotFoundError, GraphApiError
from .models import Email
from datetime import datetime

logger = structlog.get_logger(__name__)

class EmailRepository:
    """
    Handles all interactions with the Microsoft Graph API for emails.
    """

    def __init__(self):
        self._base_url = f"https://graph.microsoft.com/v1.0/users/{settings.TARGET_USER_ID}"

    def get_message(self, message_id: str) -> Email:
        """
        Fetches a single email message from Microsoft Graph by its ID.

        Args:
            message_id: The unique identifier of the Microsoft Outlook message.

        Returns:
            An Email object representing the fetched email.

        Raises:
            EmailNotFoundError: If the email with the given ID cannot be found.
            GraphApiError: For other errors during the API call.
        """
        endpoint = f"{self._base_url}/messages/{message_id}"
        headers = self._get_auth_headers()
        params = {
            "$select": "id,subject,body,from,toRecipients,ccRecipients,sentDateTime"
        }
        
        logger.info("Fetching email from Graph API", message_id=message_id)
        
        try:
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            
            email_data = response.json()
            return Email(**email_data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise EmailNotFoundError(message_id) from e
            raise GraphApiError(f"Failed to fetch email. Status: {e.response.status_code}, Response: {e.response.text}") from e
        except Exception as e:
            logger.error("An unexpected error occurred while fetching email", exc_info=e)
            raise GraphApiError(str(e)) from e

    def list_messages(
        self,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        from_address: Optional[str] = None,
        subject_contains: Optional[str] = None,
        is_unread: Optional[bool] = None,
        top: int = 25,
    ) -> List[Email]:
        """
        Fetches a list of email messages, with optional filtering.

        Args:
            start_datetime: The start date for the email search.
            end_datetime: The end date for the email search.
            from_address: Filter emails from a specific sender address.
            subject_contains: Filter emails where the subject contains this string.
            is_unread: Filter for read (False) or unread (True) emails.
            top: The maximum number of emails to return.

        Returns:
            A list of Email objects.
        """
        endpoint = f"{self._base_url}/messages"
        headers = self._get_auth_headers()

        # Build OData filter query
        filters = []
        if start_datetime:
            # Format for Graph API: YYYY-MM-DDTHH:MM:SSZ
            filters.append(f"sentDateTime ge {start_datetime.isoformat()}Z")
        if end_datetime:
            filters.append(f"sentDateTime le {end_datetime.isoformat()}Z")
        if from_address:
            filters.append(f"from/emailAddress/address eq '{from_address}'")
        if subject_contains:
            filters.append(f"contains(subject, '{subject_contains}')")
        if is_unread is not None:
            filters.append(f"isRead eq {'false' if is_unread else 'true'}")

        params = {
            "$select": "id,subject,body,from,toRecipients,ccRecipients,sentDateTime",
            "$top": str(top),
            "$orderby": "sentDateTime desc",
        }
        if filters:
            params["$filter"] = " and ".join(filters)

        logger.info("Fetching email list from Graph API", filter=params.get("$filter"))

        try:
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            emails_data = data.get("value", [])
            return [Email(**email_data) for email_data in emails_data]
        except requests.exceptions.HTTPError as e:
            raise GraphApiError(f"Failed to fetch email list. Status: {e.response.status_code}, Response: {e.response.text}") from e
        except Exception as e:
            logger.error("An unexpected error occurred while fetching email list", exc_info=e)
            raise GraphApiError(str(e)) from e

    def _get_auth_headers(self) -> Dict[str, Any]:
        """
        Constructs the authorization headers required for Graph API calls.
        """
        try:
            token = get_graph_token()
            return {
                "Authorization": f"Bearer {token}",
                "Prefer": 'outlook.body-content-type="text"',
            }
        except GraphApiError as e:
            # Re-raise to be handled by the calling method
            raise e

# Create a single, reusable instance of the repository
email_repository = EmailRepository() 