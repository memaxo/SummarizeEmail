import uuid
from locust import HttpUser, task, between

class EmailSummarizerUser(HttpUser):
    """
    Simulates a user hitting the email summarizer API.
    """
    # Wait time between each task execution for a user (1 to 5 seconds)
    wait_time = between(1, 5)

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
            name="/summarize?msg_id=[id]",  # Group all requests under a single name in Locust UI
        )
