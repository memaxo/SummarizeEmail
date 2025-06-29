"""
Unit tests for email service functions.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from app.services.email import (
    _get_llm,
    fetch_email_content,
    summarize_email,
    run_summarization_chain,
    run_rag_chain,
    EmailSummary
)
from app.exceptions import EmailNotFoundError, SummarizationError, RAGError


class TestEmailService:
    """Test cases for email service functions."""
    
    @patch('app.services.email.settings')
    def test_get_llm_openai(self, mock_settings):
        """Test LLM factory returns OpenAI client."""
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_MODEL_NAME = "gpt-4"
        mock_settings.OPENAI_API_KEY = "test-key"
        
        with patch('app.services.email.ChatOpenAI') as mock_openai:
            _get_llm()
            mock_openai.assert_called_once_with(
                temperature=0,
                model_name="gpt-4",
                api_key="test-key"
            )
    
    @patch('app.services.email.settings')
    def test_get_llm_gemini_with_vertex(self, mock_settings):
        """Test LLM factory returns Vertex AI client when credentials available."""
        mock_settings.LLM_PROVIDER = "gemini"
        mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/path/to/creds.json"
        mock_settings.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_settings.GOOGLE_CLOUD_LOCATION = "us-central1"
        mock_settings.GEMINI_MODEL_NAME = "gemini-pro"
        
        with patch('app.services.email.ChatVertexAI') as mock_vertex:
            # Mock vertexai import that happens inside _get_llm
            import sys
            mock_vertexai = MagicMock()
            with patch.dict(sys.modules, {'vertexai': mock_vertexai}):
                _get_llm()
                
                mock_vertexai.init.assert_called_once_with(
                    project="test-project",
                    location="us-central1"
                )
                
                mock_vertex.assert_called_once_with(
                    model_name="gemini-pro",
                    project="test-project",
                    location="us-central1",
                    convert_system_message_to_human=True
                )
    
    @patch('app.services.email.settings')
    def test_get_llm_unsupported_provider(self, mock_settings):
        """Test LLM factory raises error for unsupported provider."""
        mock_settings.LLM_PROVIDER = "unsupported"
        
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            _get_llm()
    
    @patch('app.services.email.settings')
    def test_fetch_email_content_basic(self, mock_settings):
        """Test fetching email content without attachments."""
        mock_settings.USE_MOCK_GRAPH_API = True
        
        # Mock the repository import that happens inside fetch_email_content
        import sys
        mock_repo_module = MagicMock()
        mock_repo_class = MagicMock()
        mock_repo = MagicMock()
        
        mock_email = MagicMock()
        mock_email.get_full_content.return_value = "Test email content"
        mock_repo.get_message.return_value = mock_email
        
        mock_repo_class.return_value = mock_repo
        mock_repo_module.MockEmailRepository = mock_repo_class
        
        with patch.dict(sys.modules, {'app.graph.mock_email_repository': mock_repo_module}):
            # Test
            content = fetch_email_content("msg-123", "user-456", include_attachments=False)
            
            # Assert
            assert content == "Test email content"
            mock_repo.get_message.assert_called_once_with("msg-123")
    
    @patch('app.services.email.settings')
    def test_fetch_email_content_with_attachments(self, mock_settings):
        """Test fetching email content with attachments."""
        mock_settings.USE_MOCK_GRAPH_API = False
        
        # Mock the repository import that happens inside fetch_email_content
        import sys
        mock_repo_module = MagicMock()
        mock_repo_class = MagicMock()
        mock_repo = MagicMock()
        
        mock_email = MagicMock()
        mock_email.get_full_content.return_value = "Test email content"
        mock_repo.get_message.return_value = mock_email
        
        # Mock attachment
        mock_attachment_meta = MagicMock()
        mock_attachment_meta.id = "att-1"
        mock_attachment_meta.name = "document.pdf"
        mock_repo.list_attachments.return_value = [mock_attachment_meta]
        
        mock_attachment = MagicMock()
        mock_attachment.contentBytes = b"fake-content"
        mock_repo.get_attachment.return_value = mock_attachment
        
        mock_repo_class.return_value = mock_repo
        mock_repo_module.EmailRepository = mock_repo_class
        
        with patch.dict(sys.modules, {'app.graph.email_repository': mock_repo_module}):
            with patch('app.services.email.document_parser') as mock_parser:
                mock_parser.parse_content.return_value = "Parsed attachment text"
                
                # Test
                content = fetch_email_content("msg-123", "user-456", include_attachments=True)
                
                # Assert
                assert "Test email content" in content
                assert "Attachment: document.pdf" in content
                assert "Parsed attachment text" in content
    
    @pytest.mark.asyncio
    async def test_summarize_email_text_mode(self):
        """Test email summarization in text mode."""
        with patch('app.services.email._get_llm') as mock_get_llm:
            # Setup mock LLM
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            
            # Mock the chain execution
            with patch('app.services.email.SIMPLE_SUMMARY_PROMPT') as mock_prompt:
                with patch('app.services.email.StrOutputParser') as mock_parser:
                    # Create a mock chain that returns the expected string
                    mock_chain = MagicMock()
                    mock_chain.invoke.return_value = "This is a summary"
                    
                    # Set up the chain creation
                    mock_prompt.__or__.return_value.__or__.return_value = mock_chain
                    
                    # Test
                    result = await summarize_email("Test email content", structured=False)
                    
                    # Assert
                    assert result == "This is a summary"
                    mock_chain.invoke.assert_called_once_with({"text": "Test email content"})
    
    @pytest.mark.asyncio
    @patch('app.services.email.settings')
    async def test_summarize_email_structured_mode(self, mock_settings):
        """Test email summarization in structured mode."""
        mock_settings.LLM_PROVIDER = "openai"
        
        with patch('app.services.email._get_llm') as mock_get_llm:
            # Setup mock LLM with structured output
            mock_llm = MagicMock()
            mock_structured_llm = MagicMock()
            
            expected_summary = EmailSummary(
                summary="Test summary",
                key_points=["Point 1", "Point 2"],
                action_items=["Action 1"],
                sentiment="positive"
            )
            
            # Mock the chain
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = expected_summary
            
            # Set up the chain creation
            mock_llm.with_structured_output.return_value = mock_structured_llm
            mock_get_llm.return_value = mock_llm
            
            with patch('app.services.email.STRUCTURED_SUMMARY_PROMPT') as mock_prompt:
                mock_prompt.__or__.return_value = mock_chain
                
                # Test
                result = await summarize_email("Test email content", structured=True)
                
                # Assert
                assert result == expected_summary
                mock_llm.with_structured_output.assert_called_once_with(EmailSummary)
    
    @pytest.mark.asyncio
    async def test_run_summarization_chain_cache_hit(self):
        """Test summarization chain with cache hit."""
        # Setup mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"Cached summary"
        
        # Test
        summary, from_cache = await run_summarization_chain("Test content", mock_redis)
        
        # Assert
        assert summary == b"Cached summary"
        assert from_cache is True
        mock_redis.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_summarization_chain_cache_miss(self):
        """Test summarization chain with cache miss."""
        # Setup mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        
        with patch('app.services.email._get_llm') as mock_get_llm:
            # Setup mocks
            mock_llm = MagicMock()
            mock_llm.model_name = "gpt-4o-mini"
            mock_get_llm.return_value = mock_llm
            
            # Mock text splitter
            with patch('app.services.email._get_text_splitter') as mock_splitter:
                mock_text_splitter = MagicMock()
                mock_text_splitter.split_documents.return_value = [Document(page_content="Test content")]
                mock_splitter.return_value = mock_text_splitter
                
                # Mock RunnableParallel for map stage
                with patch('app.services.email.RunnableParallel') as mock_parallel:
                    mock_parallel_instance = MagicMock()
                    mock_parallel_instance.abatch = AsyncMock(return_value=[{"out": "Mapped content"}])
                    mock_parallel.return_value = mock_parallel_instance
                    
                    # Mock the reduce chain
                    mock_chain = MagicMock()
                    mock_chain.invoke.return_value = "Generated summary"
                    mock_chain.with_config.return_value = mock_chain
                    
                    # Mock prompt and parser
                    mock_prompt = MagicMock()
                    mock_parser = MagicMock()
                    mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))
                    
                    with patch('app.services.email.MAP_PROMPT', mock_prompt):
                        with patch('app.services.email.REDUCE_PROMPT', mock_prompt):
                            with patch('app.services.email.StrOutputParser', return_value=mock_parser):
                                # Test
                                summary, from_cache = await run_summarization_chain("Test content", mock_redis)
                                
                                # Assert
                                assert summary == "Generated summary"
                                assert from_cache is False
                                mock_redis.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_rag_chain_success(self):
        """Test RAG chain execution with LCEL and parallel processing."""
        # Setup
        test_docs = [
            Document(page_content="Doc 1", metadata={"id": "1"}),
            Document(page_content="Doc 2", metadata={"id": "2"})
        ]
        
        with patch('app.services.email._get_llm') as mock_get_llm:
            # Setup mock LLM
            mock_llm = MagicMock()
            mock_llm.model_name = "gemini-2.5-flash"  # Add model_name attribute
            mock_get_llm.return_value = mock_llm
            
            # Mock the text splitter
            with patch('app.services.email._get_text_splitter') as mock_splitter:
                mock_text_splitter = MagicMock()
                mock_text_splitter.split_documents.return_value = test_docs
                mock_splitter.return_value = mock_text_splitter
                
                # Mock RunnableParallel
                with patch('app.services.email.RunnableParallel') as mock_parallel:
                    # Mock the batch method to return proper results
                    mock_parallel_instance = MagicMock()
                    mock_parallel_instance.abatch = AsyncMock(return_value=[
                        {"out": "Relevant text from doc 1"},
                        {"out": "Relevant text from doc 2"}
                    ])
                    mock_parallel_instance.with_config.return_value = mock_parallel_instance
                    mock_parallel.return_value = mock_parallel_instance
                    
                    # Mock the final reduce chain
                    async def mock_ainvoke(inputs):
                        if "doc_summaries" in inputs:
                            return "RAG answer"
                        return ""
                    
                    mock_chain = MagicMock()
                    mock_chain.ainvoke = AsyncMock(side_effect=mock_ainvoke)
                    mock_chain.with_config.return_value = mock_chain
                    
                    # Mock the prompt and parser chain construction
                    mock_prompt = MagicMock()
                    mock_parser = MagicMock()
                    mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))
                    
                    with patch('app.services.email.RAG_MAP_PROMPT', mock_prompt):
                        with patch('app.services.email.RAG_REDUCE_PROMPT', mock_prompt):
                            with patch('app.services.email.StrOutputParser', return_value=mock_parser):
                                # Test
                                result = await run_rag_chain("What is the status?", test_docs)
                                
                                # Assert
                                assert result == "RAG answer"
                                mock_parallel_instance.abatch.assert_called_once()
    
    def test_fetch_email_content_error_handling(self):
        """Test error handling in fetch_email_content."""
        with patch('app.services.email.settings') as mock_settings:
            mock_settings.USE_MOCK_GRAPH_API = True
            
            # Mock the repository import that happens inside fetch_email_content
            import sys
            mock_repo_module = MagicMock()
            mock_repo_class = MagicMock()
            mock_repo = MagicMock()
            
            # Setup mock to raise exception
            mock_repo.get_message.side_effect = Exception("Test error")
            
            mock_repo_class.return_value = mock_repo
            mock_repo_module.MockEmailRepository = mock_repo_class
            
            with patch.dict(sys.modules, {'app.graph.mock_email_repository': mock_repo_module}):
                # Test & Assert
                with pytest.raises(EmailNotFoundError):
                    fetch_email_content("msg-123", "user-456") 