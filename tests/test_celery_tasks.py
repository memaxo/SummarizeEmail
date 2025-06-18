"""
Unit tests for Celery tasks.
"""
import pytest
from unittest.mock import MagicMock, patch
from celery import Task

from app.tasks import ingest_emails_task
from app.graph.models import Email, EmailBody


class TestCeleryTasks:
    """Test cases for Celery tasks."""
    
    @patch('app.tasks.SessionLocal')
    @patch('app.tasks.EmailRepository')
    @patch('app.tasks.VectorDBRepository')
    @patch('app.tasks.fetch_email_content')
    @patch('app.tasks.email_cleaner')
    def test_ingest_emails_task_success(self, mock_cleaner, mock_fetch, mock_vector_repo_class, 
                                       mock_email_repo_class, mock_session):
        """Test successful email ingestion task."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        mock_email_repo = MagicMock()
        mock_email_repo_class.return_value = mock_email_repo
        
        mock_vector_repo = MagicMock()
        mock_vector_repo_class.return_value = mock_vector_repo
        
        # Mock emails
        test_emails = [
            Email(
                id="email1",
                subject="Test Email 1",
                body=EmailBody(content="Content 1", contentType="text"),
                from_address={"emailAddress": {"address": "test1@example.com"}},
                toRecipients=[],
                sentDateTime="2024-01-01T10:00:00Z"
            ),
            Email(
                id="email2",
                subject="Test Email 2",
                body=EmailBody(content="Content 2", contentType="text"),
                from_address={"emailAddress": {"address": "test2@example.com"}},
                toRecipients=[],
                sentDateTime="2024-01-01T11:00:00Z"
            )
        ]
        
        mock_email_repo.list_messages.return_value = test_emails
        mock_fetch.side_effect = ["Full content 1", "Full content 2"]
        mock_cleaner.clean.side_effect = ["Cleaned content 1", "Cleaned content 2"]
        
        # Execute task
        result = ingest_emails_task(query="test query", user_id="user123")
        
        # Assert
        assert result["status"] == "Completed"
        assert result["ingested_count"] == 2
        
        # Verify calls
        mock_email_repo.list_messages.assert_called_once_with(search="test query", top=100)
        assert mock_fetch.call_count == 2
        assert mock_cleaner.clean.call_count == 2
        mock_vector_repo.add_emails.assert_called_once()
        
        # Verify enriched emails were created
        enriched_emails = mock_vector_repo.add_emails.call_args[0][0]
        assert len(enriched_emails) == 2
        assert enriched_emails[0].body.content == "Cleaned content 1"
        assert enriched_emails[1].body.content == "Cleaned content 2"
    
    @patch('app.tasks.SessionLocal')
    @patch('app.tasks.EmailRepository')
    def test_ingest_emails_task_no_emails(self, mock_email_repo_class, mock_session):
        """Test ingestion task when no emails are found."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        mock_email_repo = MagicMock()
        mock_email_repo_class.return_value = mock_email_repo
        mock_email_repo.list_messages.return_value = []
        
        # Execute task
        result = ingest_emails_task(query="no results", user_id="user123")
        
        # Assert
        assert result["status"] == "No emails found"
        assert result["ingested_count"] == 0
    
    @patch('app.tasks.SessionLocal')
    @patch('app.tasks.EmailRepository')
    @patch('app.tasks.fetch_email_content')
    @patch('app.tasks.logger')
    def test_ingest_emails_task_partial_failure(self, mock_logger, mock_fetch, 
                                               mock_email_repo_class, mock_session):
        """Test ingestion task when some emails fail to process."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        mock_email_repo = MagicMock()
        mock_email_repo_class.return_value = mock_email_repo
        
        # Mock emails
        test_emails = [
            Email(
                id="email1",
                subject="Test Email 1",
                body=EmailBody(content="Content 1", contentType="text"),
                from_address={"emailAddress": {"address": "test1@example.com"}},
                toRecipients=[],
                sentDateTime="2024-01-01T10:00:00Z"
            ),
            Email(
                id="email2",
                subject="Test Email 2",
                body=EmailBody(content="Content 2", contentType="text"),
                from_address={"emailAddress": {"address": "test2@example.com"}},
                toRecipients=[],
                sentDateTime="2024-01-01T11:00:00Z"
            )
        ]
        
        mock_email_repo.list_messages.return_value = test_emails
        
        # First email succeeds, second fails
        mock_fetch.side_effect = ["Full content 1", Exception("Fetch failed")]
        
        with patch('app.tasks.email_cleaner') as mock_cleaner:
            with patch('app.tasks.VectorDBRepository') as mock_vector_repo_class:
                mock_cleaner.clean.return_value = "Cleaned content 1"
                mock_vector_repo = MagicMock()
                mock_vector_repo_class.return_value = mock_vector_repo
                
                # Execute task
                result = ingest_emails_task(query="test query", user_id="user123")
                
                # Assert - should process the successful email
                assert result["status"] == "Completed"
                assert result["ingested_count"] == 1
                
                # Verify error was logged
                mock_logger.error.assert_called_once()
                assert "email2" in str(mock_logger.error.call_args)
    
    @patch('app.tasks.SessionLocal')
    @patch('app.tasks.EmailRepository')
    def test_ingest_emails_task_database_cleanup(self, mock_email_repo_class, mock_session):
        """Test that database session is properly closed."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        mock_email_repo = MagicMock()
        mock_email_repo_class.return_value = mock_email_repo
        mock_email_repo.list_messages.return_value = []
        
        # Execute task
        ingest_emails_task(query="test", user_id="user123")
        
        # Verify database was closed
        mock_db.close.assert_called_once()
    
    @patch('app.tasks.SessionLocal')
    @patch('app.tasks.EmailRepository')
    def test_ingest_emails_task_exception_cleanup(self, mock_email_repo_class, mock_session):
        """Test that database is closed even when exception occurs."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        mock_email_repo = MagicMock()
        mock_email_repo_class.return_value = mock_email_repo
        mock_email_repo.list_messages.side_effect = Exception("API Error")
        
        # Execute task - should not raise exception
        with pytest.raises(Exception):
            ingest_emails_task(query="test", user_id="user123")
        
        # Verify database was still closed
        mock_db.close.assert_called_once()
    
    def test_ingest_emails_task_is_bound(self):
        """Test that the task is properly bound to Celery."""
        # The task should have Celery task attributes
        assert hasattr(ingest_emails_task, 'delay')
        assert hasattr(ingest_emails_task, 'apply_async')
        assert ingest_emails_task.name == 'app.tasks.ingest_emails_task' 