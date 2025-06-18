# Custom GPT Setup Guide

This guide explains how to set up your Email Summarizer as an OpenAI Custom GPT with proper OAuth authentication.

## Overview

When deployed as a Custom GPT, your Email Summarizer will:
- Authenticate each user individually via Microsoft OAuth
- Access only the authenticated user's emails
- Handle tokens automatically without requiring TARGET_USER_ID
- Provide a seamless experience through ChatGPT interface

## How It Works

### Authentication Flow

1. **User Initiates**: User asks the Custom GPT to summarize their emails
2. **Permission Request**: OpenAI shows a permission screen to connect to your API
3. **Microsoft Login**: User is redirected to Microsoft login page
4. **Consent**: User grants permission to read their emails
5. **Token Exchange**: Your API receives tokens and stores user context
6. **Seamless Access**: All subsequent requests include the user's token automatically

### Key Differences from Development

| Aspect | Development | Production (Custom GPT) |
|--------|-------------|------------------------|
| User ID | TARGET_USER_ID from .env | Extracted from OAuth token |
| Authentication | Service-to-service | Per-user OAuth flow |
| Token Management | Static credentials | Dynamic per-user tokens |
| Multi-tenancy | Single user | Multiple users supported |

## Setup Steps

### 1. Configure Your API for Production

Your API now uses secure JWT validation for authentication:

```python
# The API validates JWT tokens and extracts user ID securely
# Uses FastAPI dependencies for automatic authentication
from fastapi import Depends
from app.auth.dependencies import get_current_user_id

@app.get("/emails/")
async def search_emails(
    user_id: str = Depends(get_current_user_id),
    # ... other parameters
):
    # user_id is automatically extracted from the validated JWT token
    # No TARGET_USER_ID needed in production
```

### 2. Create the Custom GPT

1. Go to https://chat.openai.com/create
2. Configure your GPT:
   - **Name**: Email Summarizer Pro (or your choice)
   - **Description**: Summarizes your Outlook emails with AI
   - **Instructions**: See sample below

### 3. Configure Actions

1. Click "Create new action"
2. Import your OpenAPI schema from `https://your-api-url/openapi.json`
3. Add the server URL:
   ```json
   {
     "servers": [
       {
         "url": "https://your-api-url"
       }
     ]
   }
   ```

### 4. Set Up OAuth Authentication

1. **Authentication Type**: OAuth
2. **Client ID**: Your Azure AD app's Application (Client) ID
3. **Client Secret**: Your Azure AD app's Client Secret Value (not the ID!)
4. **Authorization URL**: `https://login.microsoftonline.com/common/oauth2/v2.0/authorize`
5. **Token URL**: `https://login.microsoftonline.com/common/oauth2/v2.0/token`
6. **Scope**: `openid profile email offline_access https://graph.microsoft.com/Mail.Read`

### 5. Configure Callback URL

After saving the OAuth configuration:
1. Copy the callback URL shown (format: `https://chat.openai.com/aip/g-XXXXXX/oauth/callback`)
2. Add this to your Azure AD app's Redirect URIs
3. Save and refresh the GPT configuration

### 6. Update Azure AD App

Ensure your Azure AD app has:
- **Supported account types**: "Accounts in any organizational directory and personal Microsoft accounts"
- **Redirect URIs**: The callback URL from step 5
- **API Permissions**: 
  - Microsoft Graph: Mail.Read (Delegated)
  - Microsoft Graph: User.Read (Delegated)
- **Verified Publisher** (recommended for production)

## Sample GPT Instructions

```
You are Email Summarizer Pro, an AI assistant that helps users manage their email inbox by providing intelligent summaries of their Outlook emails.

## Your Capabilities:
1. Search emails by keywords, sender, date range, or other criteria
2. Summarize individual emails or multiple emails at once
3. Include attachment content in summaries when requested
4. Provide concise, actionable insights from email content

## How to Use Your Actions:
- Use the search endpoint to find relevant emails based on user queries
- Use the summary endpoint to generate summaries
- Always ask if the user wants to include attachment content
- Present summaries in a clear, organized format

## Best Practices:
- Start by asking what kind of emails the user wants to summarize
- Offer to search by different criteria (sender, date, subject)
- Highlight action items and important information
- Respect user privacy - only access what's requested

## Authentication:
When a user first interacts with you, they'll need to authenticate with their Microsoft account. This is a one-time process that allows you to access their emails securely.
```

## Testing Your Custom GPT

### Initial Setup Test
1. Ask the GPT to "Summarize my recent emails"
2. Complete the authentication flow when prompted
3. Verify you can see your emails (not TARGET_USER_ID's emails)

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| "Missing access_token" error | Ensure you're using Client Secret Value, not Secret ID |
| Redirect to undefined URL | Check callback URL is correctly added to Azure AD |
| "Public clients can't send secret" | Ensure Azure AD app type is "Web" not "Mobile/Desktop" |
| No emails found | Verify Mail.Read permission is granted and consented |

## Security Considerations

1. **Token Validation**: Always validate tokens in production
2. **Scope Limitation**: Only request necessary permissions
3. **Rate Limiting**: Implement per-user rate limits
4. **Audit Logging**: Log all access for compliance
5. **Token Refresh**: Handle token expiration gracefully

## Monitoring and Analytics

Track usage per user:
```python
# Log user actions for analytics
logger.info("Email summary requested", 
    user_id=user_id,
    message_count=len(messages),
    include_attachments=include_attachments
)
```

## Troubleshooting

### Enable Debug Logging
```python
# In your API, log token details (sanitized)
logger.debug("Token received", 
    has_token=bool(auth_header),
    token_length=len(token) if token else 0,
    user_id=user_id
)
```

### Test Authentication Flow
Use the provided test script:
```bash
python scripts/test-azure-auth.py
```

## Next Steps

1. **Monetization**: Consider usage-based pricing tiers
2. **Features**: Add email composition, calendar integration
3. **Analytics**: Build dashboards for usage insights
4. **Compliance**: Implement data retention policies

## Support

For issues or questions:
1. Check Azure AD logs for authentication errors
2. Review your API logs for token validation issues
3. Test with the Azure AD test script
4. Ensure all permissions are properly configured

Remember: The key difference in production is that each user authenticates individually, and your API must handle multiple users' tokens dynamically rather than using a single TARGET_USER_ID. 