import structlog
from typing import List, Tuple, Dict, Any, Optional, Union

import requests
from langchain_community.chat_models import ChatOllama
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
from fastapi import Request
import hashlib
import jwt
import os
import httpx

from ..auth import get_graph_token
from ..config import settings
from ..exceptions import EmailNotFoundError, GraphApiError, SummarizationError, RAGError
from ..graph.email_repository import EmailRepository
from ..graph.models import Email
from .document_parser import document_parser
from ..prompts import (
    SIMPLE_SUMMARY_PROMPT, 
    STRUCTURED_SUMMARY_PROMPT,
    MAP_PROMPT,
    REDUCE_PROMPT,
    RAG_PROMPT
)
from app.logger import logger

logger = structlog.get_logger(__name__)


# Pydantic models for structured output
class EmailSummary(BaseModel):
    """Structured email summary output"""
    summary: str = Field(description="A concise summary of the email content")
    key_points: List[str] = Field(description="List of key points from the email")
    action_items: List[str] = Field(description="List of action items mentioned in the email", default_factory=list)
    sentiment: str = Field(description="Overall sentiment: positive, negative, or neutral")


def _get_llm() -> BaseChatModel:
    """
    Factory function to get the appropriate LLM client based on settings.
    This allows for easy swapping between OpenAI, Gemini, and Ollama models.
    """
    provider = settings.LLM_PROVIDER.lower()
    logger.info(f"Initializing LLM for provider: {provider}")

    if provider == "openai":
        return ChatOpenAI(
            temperature=0,
            model_name=settings.OPENAI_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY,
        )
    elif provider == "gemini":
        # Check if we should use Vertex AI (service account) or Google AI (API key)
        if settings.GOOGLE_APPLICATION_CREDENTIALS and settings.GOOGLE_CLOUD_PROJECT:
            # Use Vertex AI with service account
            logger.info("Using Vertex AI with service account authentication")
            
            # Set the environment variable for Google Cloud authentication
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
            
            # Initialize Vertex AI
            import vertexai
            vertexai.init(
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
            
            return ChatVertexAI(
                model_name=settings.GEMINI_MODEL_NAME,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION,
                convert_system_message_to_human=True,
            )
        else:
            # Use Google AI with API key
            logger.info("Using Google AI with API key authentication")
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL_NAME.replace("google/", ""),  # Remove prefix for Google AI
                temperature=0,
                google_api_key=settings.GOOGLE_API_KEY,
                convert_system_message_to_human=True,  # Gemini doesn't support system messages directly
            )
    elif provider == "ollama":
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            temperature=0,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")


async def get_user_id_from_token(request: Request) -> str:
    """Extract the user ID from the OAuth token in the request.
    
    In production with Custom GPT, the user's identity comes from
    the OAuth token, not from environment variables.
    """
    # Get the authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # Fallback to TARGET_USER_ID for local development/testing
        return settings.TARGET_USER_ID
    
    token = auth_header.split(" ")[1]
    
    try:
        # Decode the token to get user info
        # This is a simplified example - in production you'd validate the token
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Microsoft tokens typically have 'oid' (object ID) or 'sub' (subject)
        user_id = decoded.get('oid') or decoded.get('sub') or decoded.get('preferred_username')
        
        if not user_id:
            logger.warning("No user ID found in token, falling back to TARGET_USER_ID")
            return settings.TARGET_USER_ID
            
        return user_id
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        # Fallback for development
        return settings.TARGET_USER_ID


async def fetch_email_content(
    msg_id: str,
    request: Request,
    include_attachments: bool = False
) -> str:
    """Fetch email content from the repository, respecting mock mode."""
    try:
        # The email_repository is now a singleton that respects mock mode
        from ..graph import email_repository
        
        email = email_repository.get_message(msg_id)
        content = email.get_full_content()

        if include_attachments:
            logger.info("Fetching attachments for email", message_id=msg_id)
            attachments = email_repository.list_attachments(msg_id)
            
            for attachment_meta in attachments:
                logger.info("Parsing attachment", attachment_id=attachment_meta.id)
                full_attachment = email_repository.get_attachment(msg_id, attachment_meta.id)
                attachment_text = document_parser.parse_content(full_attachment.contentBytes)
                
                if attachment_text:
                    content += f"\n\n--- Attachment: {attachment_meta.name} ---\n{attachment_text}"

        return content
    except Exception as e:
        logger.error(f"Error fetching email content: {e}", exc_info=True)
        # Re-raise as a standard exception type for the route handler
        raise EmailNotFoundError(f"Email not found or could not be processed: {msg_id}") from e


async def summarize_email(content: str, structured: bool = False) -> Union[str, EmailSummary]:
    """
    Generate a summary for email content using the configured LLM.
    
    Args:
        content: The email content to summarize
        structured: If True, returns structured output with key points and action items
        
    Returns:
        The generated summary (string or EmailSummary object)
    """
    llm = _get_llm()
    
    if structured and settings.LLM_PROVIDER in ["openai", "gemini"]:
        # Use structured output for supported providers
        # Create structured output chain
        structured_llm = llm.with_structured_output(EmailSummary)
        chain = STRUCTURED_SUMMARY_PROMPT | structured_llm
        
        try:
            result = chain.invoke({"text": content})
            return result
        except Exception as e:
            logger.warning(f"Structured output failed, falling back to text: {e}")
            # Fall back to regular text output
    
    # Regular text summarization
    chain = SIMPLE_SUMMARY_PROMPT | llm | StrOutputParser()
    response = chain.invoke({"text": content})
    
    return response


def run_summarization_chain(request: Request, content: str) -> Tuple[str, bool]:
    """
    Summarizes the given text using a LangChain map-reduce summarization chain.
    It checks for a cached summary in Redis before calling the LLM.
    Returns the summary and a boolean indicating if it was from the cache.
    """
    # 1. Check for cached result
    redis_client = request.app.state.redis
    cache_key = f"summary:{hashlib.sha256(content.encode()).hexdigest()}"
    if redis_client:
        cached_summary = redis_client.get(cache_key)
        if cached_summary:
            logger.info("Returning cached summary", cache_key=cache_key)
            return cached_summary, True

    # 2. If not cached, run the full summarization
    llm = _get_llm()
    docs = [Document(page_content=content)]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=200)
    split_docs = text_splitter.split_documents(docs)
    
    # Use our centralized prompts
    chain = load_summarize_chain(
        llm, 
        chain_type="map_reduce",
        map_prompt=MAP_PROMPT,
        combine_prompt=REDUCE_PROMPT
    )

    logger.info(f"Running summarization chain with {len(split_docs)} documents...")
    try:
        summary = chain.run(split_docs)
        logger.info("Successfully generated summary.")
        
        # 3. Store the new result in the cache
        if redis_client:
            redis_client.set(cache_key, summary, ex=settings.CACHE_EXPIRATION_SECONDS)
            logger.info("Stored new summary in cache", cache_key=cache_key)

        return summary, False
    except Exception as e:
        logger.error("An error occurred during summarization: %s", e, exc_info=True)
        raise SummarizationError(str(e)) from e


def run_rag_chain(question: str, context_docs: List[Document]) -> str:
    """
    Generates an answer to a question based on a list of context documents.

    Args:
        question: The user's question.
        context_docs: A list of LangChain documents retrieved from the vector store.

    Returns:
        A generated answer string.
    """
    llm = _get_llm()
    
    # Use our centralized RAG prompt
    question_answer_chain = create_stuff_documents_chain(llm, RAG_PROMPT)

    logger.info("Running RAG chain", question=question, num_docs=len(context_docs))
    try:
        response = question_answer_chain.invoke({
            "question": question,
            "context": context_docs
        })
        logger.info("Successfully generated RAG answer.")
        return response
    except Exception as e:
        logger.error("An error occurred during RAG chain execution", exc_info=True)
        raise RAGError(str(e)) from e


def run_bulk_summarization(request: Request, emails: List[Email]) -> Tuple[str, bool]:
    """
    Creates a single digest summary from a list of emails.
    """
    if not emails:
        return "No emails to summarize.", False

    # Combine the content of all emails into a single document
    full_content = "\n\n---\n\n".join([email.get_full_content() for email in emails])
    
    logger.info(f"Running bulk summarization for {len(emails)} emails.")
    # We can reuse the existing summarization chain for the combined content.
    return run_summarization_chain(request, full_content)


class EmailService:
    def __init__(self):
        # Check if we're in mock mode
        self.use_mock = os.getenv("USE_MOCK_GRAPH_API", "false").lower() == "true"
        if self.use_mock:
            self.graph_base_url = os.getenv("MOCK_GRAPH_API_URL", "http://localhost:8001")
            logger.info("Using Mock Graph API for testing")
        else:
            self.graph_base_url = "https://graph.microsoft.com"
        
        self.api_version = "v1.0"
        
    async def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        if self.use_mock:
            # Use a test token for mock API
            return {"Authorization": "Bearer test-token"}
        else:
            token = await get_graph_token()
            return {"Authorization": f"Bearer {token}"}
    
    async def search_emails(
        self, 
        query: Optional[str] = None,
        from_address: Optional[str] = None,
        subject: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search emails using Microsoft Graph API or Mock API"""
        try:
            headers = await self._get_headers()
            
            # Build query parameters
            params = {
                "$top": limit,
                "$select": "id,subject,from,sentDateTime,body",
                "$orderby": "sentDateTime desc"
            }
            
            # Add search/filter parameters
            filters = []
            if from_address:
                filters.append(f"from/emailAddress/address eq '{from_address}'")
            
            if filters:
                params["$filter"] = " and ".join(filters)
            
            if query:
                params["$search"] = f'"{query}"'
            
            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.graph_base_url}/{self.api_version}/me/messages",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                return data.get("value", [])
                
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            raise
    
    async def get_email(self, message_id: str) -> Dict[str, Any]:
        """Get a specific email by ID"""
        try:
            headers = await self._get_headers()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.graph_base_url}/{self.api_version}/me/messages/{message_id}",
                    headers=headers,
                    params={"$select": "id,subject,from,sentDateTime,body,toRecipients"}
                )
                response.raise_for_status()
                
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting email {message_id}: {str(e)}")
            raise
    
    async def get_email_content(self, message_id: str) -> str:
        """Get email content for summarization"""
        email = await self.get_email(message_id)
        
        # Extract relevant content
        content_parts = []
        
        # Add subject
        if "subject" in email:
            content_parts.append(f"Subject: {email['subject']}")
        
        # Add from
        if "from" in email and "emailAddress" in email["from"]:
            from_addr = email["from"]["emailAddress"]
            content_parts.append(f"From: {from_addr.get('name', '')} <{from_addr.get('address', '')}>")
        
        # Add body
        if "body" in email and "content" in email["body"]:
            content_parts.append(f"\n{email['body']['content']}")
        
        return "\n".join(content_parts) 