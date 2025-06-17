# This file makes the 'graph' directory a Python package and sets up the email repository singleton.

from ..config import settings

# Conditionally import the correct repository class and instantiate it as a singleton.
# We name it `graph_repo` to avoid a name collision with the `email_repository.py` module.
if settings.USE_MOCK_GRAPH_API:
    from .mock_email_repository import MockEmailRepository
    graph_repo = MockEmailRepository()
else:
    from .email_repository import EmailRepository
    graph_repo = EmailRepository()

# This makes it so `from ..graph import graph_repo` imports the instantiated object.
__all__ = ["graph_repo"] 