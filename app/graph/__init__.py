# This file makes the 'graph' directory a Python package and sets up the email repository singleton.

from ..config import settings

# Conditionally import the correct repository class and instantiate it as a singleton.
if settings.USE_MOCK_GRAPH_API:
    from .mock_email_repository import MockEmailRepository
    email_repository = MockEmailRepository()
else:
    from .email_repository import EmailRepository
    email_repository = EmailRepository()

# This makes it so `from ..graph import email_repository` imports the instantiated object.
__all__ = ["email_repository"] 