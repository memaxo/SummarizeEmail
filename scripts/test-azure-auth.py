#!/usr/bin/env python3
"""
Test script to verify Azure AD authentication and Microsoft Graph access.
Run this to ensure your Azure AD App Registration is configured correctly.
"""

import os
import sys
import requests
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def test_azure_auth():
    """Test Azure AD authentication and token acquisition."""
    print("=== Azure AD Authentication Test ===\n")
    
    # Check environment variables
    print("1. Checking environment variables...")
    required_vars = ['AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET', 'TARGET_USER_ID']
    missing_vars = []
    
    for var in required_vars:
        value = getattr(settings, var, None)
        if not value or value in ['your_tenant_id_here', 'your_client_id_here', 
                                   'your_client_secret_here', 'target_user_id_here']:
            missing_vars.append(var)
            print(f"   ❌ {var}: Not configured")
        else:
            # Mask the secret for security
            if var == 'AZURE_CLIENT_SECRET':
                print(f"   ✅ {var}: {'*' * 10}{value[-4:]}")
            else:
                print(f"   ✅ {var}: {value}")
    
    if missing_vars:
        print(f"\n❌ Missing configuration: {', '.join(missing_vars)}")
        print("Please update your .env file with the correct values.")
        return False
    
    # Test token acquisition
    print("\n2. Testing token acquisition...")
    token_url = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/token"
    
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': settings.AZURE_CLIENT_ID,
        'client_secret': settings.AZURE_CLIENT_SECRET,
        'scope': 'https://graph.microsoft.com/.default'
    }
    
    try:
        response = requests.post(token_url, data=token_data)
        
        if response.status_code == 200:
            token_info = response.json()
            print("   ✅ Successfully acquired access token")
            print(f"   Token type: {token_info.get('token_type')}")
            print(f"   Expires in: {token_info.get('expires_in')} seconds")
            
            access_token = token_info['access_token']
            
            # Test Graph API access
            print("\n3. Testing Microsoft Graph API access...")
            
            # Test 1: Get user profile
            user_url = f"https://graph.microsoft.com/v1.0/users/{settings.TARGET_USER_ID}"
            headers = {'Authorization': f'Bearer {access_token}'}
            
            user_response = requests.get(user_url, headers=headers)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                print(f"   ✅ Successfully accessed user profile")
                print(f"   User: {user_data.get('displayName', 'N/A')}")
                print(f"   Email: {user_data.get('mail', user_data.get('userPrincipalName', 'N/A'))}")
            else:
                print(f"   ❌ Failed to access user profile: {user_response.status_code}")
                print(f"   Error: {user_response.json().get('error', {}).get('message', 'Unknown error')}")
                return False
            
            # Test 2: List recent emails
            print("\n4. Testing email access...")
            mail_url = f"https://graph.microsoft.com/v1.0/users/{settings.TARGET_USER_ID}/messages"
            params = {
                '$top': 5,
                '$select': 'subject,from,receivedDateTime',
                '$orderby': 'receivedDateTime desc'
            }
            
            mail_response = requests.get(mail_url, headers=headers, params=params)
            
            if mail_response.status_code == 200:
                mail_data = mail_response.json()
                emails = mail_data.get('value', [])
                print(f"   ✅ Successfully accessed emails")
                print(f"   Found {len(emails)} recent emails:")
                
                for email in emails[:3]:  # Show first 3
                    subject = email.get('subject', 'No subject')
                    from_addr = email.get('from', {}).get('emailAddress', {}).get('address', 'Unknown')
                    received = email.get('receivedDateTime', '')
                    print(f"      - {subject[:50]}... (from: {from_addr})")
            else:
                print(f"   ❌ Failed to access emails: {mail_response.status_code}")
                error_msg = mail_response.json().get('error', {}).get('message', 'Unknown error')
                print(f"   Error: {error_msg}")
                
                if 'Application is not authorized' in error_msg:
                    print("\n   💡 Hint: Make sure you've granted admin consent for Mail.Read permission")
                    print("      Go to Azure Portal → App registrations → API permissions → Grant admin consent")
                
                return False
            
            print("\n✅ All tests passed! Your Azure AD configuration is working correctly.")
            return True
            
        else:
            error_data = response.json()
            print(f"   ❌ Failed to acquire token: {response.status_code}")
            print(f"   Error: {error_data.get('error', 'Unknown error')}")
            print(f"   Description: {error_data.get('error_description', 'No description')}")
            
            if error_data.get('error') == 'invalid_client':
                print("\n   💡 Hint: Check your AZURE_CLIENT_ID and AZURE_CLIENT_SECRET")
            elif error_data.get('error') == 'invalid_request':
                print("\n   💡 Hint: Check your AZURE_TENANT_ID")
                
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {str(e)}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {str(e)}")
        return False


if __name__ == "__main__":
    print("Azure AD Configuration Test for Email Summarizer")
    print("=" * 50)
    print()
    
    success = test_azure_auth()
    
    if not success:
        print("\n❌ Tests failed. Please check your configuration and try again.")
        sys.exit(1)
    else:
        print("\n✅ Your Email Summarizer is ready to connect to Microsoft Graph!")
        sys.exit(0) 