from typing import List, Optional
from pydantic import BaseModel, Field

class EmailBody(BaseModel):
    """Represents the body of an email."""
    content: str
    content_type: str = Field(alias="contentType")

class Recipient(BaseModel):
    """Represents an email recipient."""
    email_address: dict = Field(alias="emailAddress")

class Email(BaseModel):
    """Represents a single email message from Microsoft Graph."""
    id: str
    subject: str
    body: EmailBody
    from_address: Recipient = Field(alias="from")
    to_recipients: List[Recipient] = Field(alias="toRecipients")
    cc_recipients: Optional[List[Recipient]] = Field(alias="ccRecipients", default=None)
    sent_date_time: str = Field(alias="sentDateTime")
    
    class Config:
        populate_by_name = True
        
    def get_full_content(self) -> str:
        """
        Combines the subject and body for a complete summary context.
        """
        return f"Subject: {self.subject}\n\n{self.body.content}"

class Attachment(BaseModel):
    """Represents a file attachment from Microsoft Graph."""
    id: str
    name: str
    content_type: str = Field(alias="contentType")
    size_in_bytes: int = Field(alias="size")
    is_inline: bool = Field(alias="isInline")
    content_bytes: Optional[str] = Field(alias="contentBytes", default=None)
    content_id: Optional[str] = Field(alias="contentId", default=None) 