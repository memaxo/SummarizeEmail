#!/usr/bin/env python3
"""
Mock Microsoft Graph API Server
Simulates Graph API responses for local testing without Azure credentials
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import FastAPI, Query, HTTPException, Header
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Mock Microsoft Graph API")

# Generate mock emails
def generate_mock_emails(count: int = 10) -> List[Dict[str, Any]]:
    """Generate realistic mock emails"""
    subjects = [
        "Q4 Budget Review Meeting",
        "Security Update Required - Action Needed",
        "Welcome to the Team!",
        "Project Alpha Status Update",
        "Customer Feedback Summary",
        "Weekly Team Sync Notes",
        "New Feature Release Announcement",
        "Urgent: Server Maintenance Tonight",
        "Quarterly Performance Reviews Due",
        "Holiday Schedule Reminder"
    ]
    
    senders = [
        {"address": "sarah@company.com", "name": "Sarah Johnson"},
        {"address": "mike@company.com", "name": "Mike Chen"},
        {"address": "lisa@company.com", "name": "Lisa Wang"},
        {"address": "john@company.com", "name": "John Smith"},
        {"address": "emma@company.com", "name": "Emma Davis"}
    ]
    
    bodies = [
        "Please review the attached budget report and provide feedback by EOW.",
        "Critical security update required. All team members must take action immediately.",
        "Welcome aboard! Looking forward to working with you.",
        "Project is on track. Deliverables will be ready by the deadline.",
        "Customer satisfaction scores have improved by 15% this quarter.",
        "Action items from today's meeting are documented in the wiki.",
        "Excited to announce our new feature launch next week!",
        "Server maintenance scheduled for tonight 10 PM - 2 AM PST.",
        "Please complete your performance reviews by Friday.",
        "Office will be closed for the holidays from Dec 24 - Jan 2."
    ]
    
    emails = []
    for i in range(count):
        email = {
            "id": f"msg{i:03d}",
            "subject": random.choice(subjects),
            "body": {
                "content": random.choice(bodies),
                "contentType": "text"
            },
            "from": {"emailAddress": random.choice(senders)},
            "toRecipients": [{"emailAddress": {"address": "user@company.com"}}],
            "sentDateTime": (datetime.now() - timedelta(hours=random.randint(1, 72))).isoformat() + "Z",
            "isRead": random.choice([True, False]),
            "importance": random.choice(["normal", "high", "low"])
        }
        emails.append(email)
    
    return sorted(emails, key=lambda x: x["sentDateTime"], reverse=True)


# Store mock emails in memory
MOCK_EMAILS = generate_mock_emails(20)


@app.get("/v1.0/me/messages")
async def get_messages(
    top: int = Query(10, alias="$top"),
    skip: int = Query(0, alias="$skip"),
    filter: str = Query(None, alias="$filter"),
    search: str = Query(None, alias="$search"),
    orderby: str = Query("sentDateTime desc", alias="$orderby"),
    select: str = Query(None, alias="$select"),
    authorization: str = Header(None)
):
    """Mock Graph API messages endpoint"""
    
    # Simulate authorization check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Filter emails based on query parameters
    filtered_emails = MOCK_EMAILS.copy()
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        filtered_emails = [
            email for email in filtered_emails
            if search_lower in email["subject"].lower() or
               search_lower in email["body"]["content"].lower()
        ]
    
    # Apply filter
    if filter:
        # Simple filter implementation
        if "from/emailAddress/address eq" in filter:
            filter_email = filter.split("'")[1]
            filtered_emails = [
                email for email in filtered_emails
                if email["from"]["emailAddress"]["address"] == filter_email
            ]
    
    # Apply pagination
    paginated_emails = filtered_emails[skip:skip + top]
    
    # Apply field selection
    if select:
        fields = select.split(",")
        paginated_emails = [
            {field: email.get(field) for field in fields if field in email}
            for email in paginated_emails
        ]
    
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('me')/messages",
        "@odata.count": len(filtered_emails),
        "value": paginated_emails,
        "@odata.nextLink": f"/v1.0/me/messages?$skip={skip + top}" if skip + top < len(filtered_emails) else None
    }


@app.get("/v1.0/me/messages/{message_id}")
async def get_message(
    message_id: str,
    select: str = Query(None, alias="$select"),
    authorization: str = Header(None)
):
    """Mock Graph API single message endpoint"""
    
    # Simulate authorization check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Find the email
    email = next((e for e in MOCK_EMAILS if e["id"] == message_id), None)
    
    if not email:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Apply field selection
    if select:
        fields = select.split(",")
        email = {field: email.get(field) for field in fields if field in email}
    
    return email


@app.get("/v1.0/me")
async def get_user(authorization: str = Header(None)):
    """Mock Graph API user endpoint"""
    
    # Simulate authorization check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return {
        "id": "12345678-1234-1234-1234-123456789012",
        "displayName": "Test User",
        "mail": "testuser@company.com",
        "userPrincipalName": "testuser@company.com"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mock-graph-api"}


if __name__ == "__main__":
    print("Starting Mock Microsoft Graph API Server...")
    print("This simulates Graph API for local testing")
    print("Access at: http://localhost:8001")
    print("Press Ctrl+C to stop")
    
    uvicorn.run(app, host="0.0.0.0", port=8001) 