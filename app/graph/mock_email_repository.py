"""
Mock Email Repository for local testing
Returns test data instead of calling Microsoft Graph API
"""

import structlog
from typing import List, Optional
from datetime import datetime, timedelta
from .models import Email, Attachment
from ..exceptions import EmailNotFoundError

logger = structlog.get_logger(__name__)

# Mock email data for testing
MOCK_EMAILS = {
    "msg001": {
        "id": "msg001",
        "subject": "Q4 Budget Review Meeting",
        "body": {
            "content": """Hi team,

I wanted to follow up on our Q4 budget review. Here are the key points we need to discuss:

1. Marketing spend is 15% over budget due to the new campaign
2. Engineering delivered the new features ahead of schedule, saving $50k
3. Sales exceeded targets by 22%, resulting in higher commission payouts
4. We need to reallocate funds for Q1 planning

Please review the attached spreadsheet before our meeting tomorrow at 2 PM.

Best regards,
Sarah""",
            "contentType": "text"
        },
        "from": {"emailAddress": {"address": "sarah@company.com", "name": "Sarah Johnson"}},
        "toRecipients": [{"emailAddress": {"address": "team@company.com"}}],
        "ccRecipients": [],
        "sentDateTime": (datetime.now() - timedelta(hours=2)).isoformat() + "Z"
    },
    "msg002": {
        "id": "msg002",
        "subject": "Security Update Required - Action Needed",
        "body": {
            "content": """Dear IT Team,

URGENT: We've identified a critical security vulnerability in our authentication system. 

Required Actions:
- All users must update their passwords by EOD Friday
- Enable 2FA for all admin accounts immediately  
- Review access logs for any suspicious activity in the past 48 hours
- Update all API keys and rotate secrets

I've scheduled an emergency meeting for 3 PM today. Attendance is mandatory.

This is a high-priority issue that needs immediate attention.

Thanks,
Mike
Security Team Lead""",
            "contentType": "text"
        },
        "from": {"emailAddress": {"address": "mike@company.com", "name": "Mike Chen"}},
        "toRecipients": [{"emailAddress": {"address": "it-team@company.com"}}],
        "ccRecipients": [],
        "sentDateTime": (datetime.now() - timedelta(hours=1)).isoformat() + "Z"
    },
    "msg003": {
        "id": "msg003", 
        "subject": "Welcome to the Team!",
        "body": {
            "content": """Hi Alex,

Welcome to the engineering team! We're excited to have you join us.

Here's what you need to know for your first week:
- Monday: Orientation at 9 AM in the main conference room
- Tuesday: Meet with your mentor (John) at 10 AM
- Wednesday: Team standup at 9:30 AM (daily)
- Thursday: Tech stack overview with the architecture team
- Friday: First sprint planning session

Your equipment should be ready for pickup from IT. Your temporary password is in a separate email.

Looking forward to working with you!

Best,
Lisa
Engineering Manager""",
            "contentType": "text"
        },
        "from": {"emailAddress": {"address": "lisa@company.com", "name": "Lisa Wang"}},
        "toRecipients": [{"emailAddress": {"address": "alex@company.com"}}],
        "ccRecipients": [],
        "sentDateTime": (datetime.now() - timedelta(days=1)).isoformat() + "Z"
    }
}


class MockEmailRepository:
    """Mock implementation of EmailRepository for local testing"""
    
    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id or "testuser@company.com"
        logger.info("Using Mock Email Repository", user_id=self.user_id)
    
    def get_message(self, message_id: str) -> Email:
        """Get a mock email by ID"""
        logger.info("Fetching mock email", message_id=message_id)
        
        if message_id in MOCK_EMAILS:
            return Email(**MOCK_EMAILS[message_id])
        else:
            raise EmailNotFoundError(message_id)
    
    def list_messages(
        self,
        search: Optional[str] = None,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        from_address: Optional[str] = None,
        subject_contains: Optional[str] = None,
        is_unread: Optional[bool] = None,
        top: int = 25,
    ) -> List[Email]:
        """List mock emails with optional filtering"""
        logger.info("Listing mock emails", search=search, top=top)
        
        emails = []
        for email_data in MOCK_EMAILS.values():
            email = Email(**email_data)
            
            # Apply filters
            if subject_contains and subject_contains.lower() not in email.subject.lower():
                continue
            if from_address and email.from_.emailAddress.address != from_address:
                continue
            if search and search.lower() not in (email.subject + " " + email.body.content).lower():
                continue
                
            emails.append(email)
        
        # Sort by sent date (newest first) and limit
        emails.sort(key=lambda e: e.sent_date_time, reverse=True)
        return emails[:top]
    
    def list_attachments(self, message_id: str) -> List[Attachment]:
        """Return empty list - mock emails have no attachments"""
        logger.info("Listing mock attachments", message_id=message_id)
        return []
    
    def get_attachment(self, message_id: str, attachment_id: str) -> Attachment:
        """Mock attachments not implemented"""
        raise EmailNotFoundError(f"Attachment {attachment_id} not found")
    
    def _get_auth_headers(self):
        """Mock - no auth needed"""
        return {} 