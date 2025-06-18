import uuid
from locust import HttpUser, task, between
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tests.auth.helpers import create_test_token

class EmailSummarizerUser(HttpUser):
    """
    Simulates a user hitting the email summarizer API.
    """
    # Wait time between each task execution for a user (1 to 5 seconds)
    wait_time = between(1, 5)
    
    def on_start(self):
        """
        Called when a simulated user starts. Sets up authentication.
        """
        # Create a test token for this user
        self.user_id = f"test_user_{uuid.uuid4()}"
        self.token = create_test_token(self.user_id)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task
    def summarize_email(self):
        """
        Defines the primary task for the user: summarizing a random email.
        """
        # Generate a random UUID for the message ID to avoid caching
        # and simulate requests for new, unique emails.
        message_id = str(uuid.uuid4())
        
        # The endpoint we are testing
        url = f"/summarize?msg_id={message_id}"
        
        self.client.get(
            url,
            headers=self.headers,
            name="/summarize?msg_id=[id]",  # Group all requests under a single name in Locust UI
        )
