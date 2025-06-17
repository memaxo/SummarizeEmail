import re
import structlog

logger = structlog.get_logger(__name__)

class EmailCleaningService:
    """
    A service for cleaning email content by removing common artifacts like
    signatures, quoted replies, and forwarded message headers.
    """

    def clean(self, text: str) -> str:
        """
        Cleans the email text.
        
        Args:
            text: The raw email content.

        Returns:
            The cleaned email content.
        """
        # Remove common signature patterns
        text = re.sub(r'(--|__|––|—)\s*\n.*', '', text, flags=re.DOTALL)
        
        # Remove "On [Date], [Name] <[email]> wrote:" reply headers
        text = re.sub(r'On\s.*(wrote|écrit):', '', text)
        
        # Remove forwarded message headers
        text = re.sub(r'---------- Forwarded message ---------', '', text, flags=re.IGNORECASE)
        text = re.sub(r'From:.*', '', text)
        text = re.sub(r'To:.*', '', text)
        text = re.sub(r'Cc:.*', '', text)
        text = re.sub(r'Subject:.*', '', text)
        text = re.sub(r'Date:.*', '', text)
        
        # Remove lines that are just whitespace
        text = "\n".join(line for line in text.splitlines() if line.strip())
        
        return text.strip()

# Singleton instance
email_cleaner = EmailCleaningService() 