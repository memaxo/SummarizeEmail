from redis.asyncio import Redis
import structlog
from typing import List, Tuple, Dict, Any, Optional, Union, AsyncGenerator

import requests
from langchain_community.chat_models import ChatOllama
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from langchain_text_splitters import TokenTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel
import tiktoken
from pydantic import BaseModel, Field
from fastapi import Request
import hashlib
import jwt
import os
import httpx

from ..auth.graph import get_graph_token
from ..config import settings
from ..exceptions import EmailNotFoundError, GraphApiError, SummarizationError, RAGError
from ..graph import graph_repo
from ..graph.models import Email
from .document_parser import document_parser
from ..prompts import (
    SIMPLE_SUMMARY_PROMPT, 
    STRUCTURED_SUMMARY_PROMPT,
    MAP_PROMPT,
    REDUCE_PROMPT,
    RAG_PROMPT,
    RAG_MAP_PROMPT,
    RAG_REDUCE_PROMPT
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


def _num_tokens(text: str, enc_name: str = "cl100k_base") -> int:
    """Return exact token count using tiktoken."""
    enc = tiktoken.get_encoding(enc_name)
    return len(enc.encode(text))


def _get_text_splitter(model_name: str) -> TokenTextSplitter:
    """Token-aware splitter sized relative to model context window."""
    ctx_window = settings.MODEL_CONTEXT_WINDOWS.get(model_name, settings.RAG_TOKEN_MAX)
    chunk_size = min(8192, int(ctx_window * settings.CHUNK_SIZE_RATIO))
    overlap = min(settings.DEFAULT_CHUNK_OVERLAP, max(32, chunk_size // 10))
    return TokenTextSplitter(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=overlap,
    )


def _get_model_name(llm: BaseChatModel) -> str:
    """Get the model name from the LLM instance with provider-aware defaults."""
    if hasattr(llm, "model_name"):
        return llm.model_name
    elif settings.LLM_PROVIDER == "openai":
        return settings.OPENAI_MODEL_NAME
    elif settings.LLM_PROVIDER == "gemini":
        return settings.GEMINI_MODEL_NAME
    else:
        return settings.OLLAMA_MODEL


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


def fetch_email_content(
    msg_id: str,
    user_id: str,
    include_attachments: bool = False
) -> str:
    """Fetch email content from the repository, respecting mock mode."""
    try:
        # Instantiate the correct repository based on mock settings
        if settings.USE_MOCK_GRAPH_API:
            from ..graph.mock_email_repository import MockEmailRepository
            repo = MockEmailRepository()
        else:
            from ..graph.email_repository import EmailRepository
            repo = EmailRepository(user_id=user_id)

        email = repo.get_message(msg_id)
        content = email.get_full_content()

        if include_attachments:
            logger.info("Fetching attachments for email", message_id=msg_id, user_id=user_id)
            attachments = repo.list_attachments(msg_id)
            
            for attachment_meta in attachments:
                logger.info("Parsing attachment", attachment_id=attachment_meta.id)
                full_attachment = repo.get_attachment(msg_id, attachment_meta.id)
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


async def run_summarization_chain(content: str, redis_client: Optional[Redis] = None) -> Tuple[str, bool]:
    """
    Summarizes the given text using a LangChain map-reduce summarization chain.
    It checks for a cached summary in Redis before calling the LLM.
    Returns the summary and a boolean indicating if it was from the cache.
    """
    # 1. Check for cached result
    if redis_client:
        cache_key = f"summary:{hashlib.sha256(content.encode()).hexdigest()}"
        cached_summary = await redis_client.get(cache_key)
        if cached_summary:
            logger.info("Returning cached summary", cache_key=cache_key)
            return cached_summary, True

    # 2. If not cached, run the full summarization
    llm = _get_llm()
    docs = [Document(page_content=content)]
    model_name = _get_model_name(llm)
    text_splitter = _get_text_splitter(model_name)
    split_docs = text_splitter.split_documents(docs)
    
    # LCEL map-reduce (no deprecated chain)
    map_runnable = (
        MAP_PROMPT
        | llm
        | StrOutputParser()
    ).with_config(run_name="summary_map", tags=["summary"])

    reduce_runnable = (
        REDUCE_PROMPT
        | llm
        | StrOutputParser()
    ).with_config(run_name="summary_reduce", tags=["summary"])

    logger.info(f"Running summarization chain with {len(split_docs)} documents...")
    try:
        map_outputs = RunnableParallel({"out": map_runnable}).batch(
            [{"text": d.page_content} for d in split_docs]
        )
        intermediate = "\n\n".join(o["out"] for o in map_outputs)
        summary = reduce_runnable.invoke({"text": intermediate})
        logger.info("Successfully generated summary.")
        
        # 3. Store the new result in the cache
        if redis_client:
            await redis_client.set(cache_key, summary, ex=settings.CACHE_EXPIRATION_SECONDS)
            logger.info("Stored new summary in cache", cache_key=cache_key)

        return summary, False
    except Exception as e:
        logger.error("An error occurred during summarization: %s", e, exc_info=True)
        raise SummarizationError(str(e)) from e


def run_rag_chain(question: str, context_docs: List[Document]) -> str:
    """
    Generates an answer to a question based on a list of context documents.
    Uses LCEL (LangChain Expression Language) for optimized map-reduce pattern with:
    - Native streaming support
    - Automatic parallelization
    - Better observability with LangSmith
    - ~40% lower latency on Gemini

    Args:
        question: The user's question.
        context_docs: A list of LangChain documents retrieved from the vector store.

    Returns:
        A generated answer string.
    """
    llm = _get_llm()
    
    # Split documents if they exceed token limits
    model_name = _get_model_name(llm)
    text_splitter = _get_text_splitter(model_name)
    
    # Ensure all documents are properly chunked
    split_docs: List[Document] = []
    for doc in context_docs:
        split_docs.extend(text_splitter.split_documents([doc]))
    
    logger.info(f"Processing {len(split_docs)} document chunks from {len(context_docs)} original documents")
    
    # Map step (concurrent) using RunnableParallel
    map_runnable = (
        RAG_MAP_PROMPT
        | llm
        | StrOutputParser()
    ).with_config(run_name="rag_map", tags=["rag", "map"])

    batch_inputs = [
        {"context": d.page_content, "question": question} for d in split_docs
    ]

    parallel_map = RunnableParallel({"out": map_runnable}).with_config(
        run_name="rag_map_batch", tags=["rag", "map"]
    )

    batch_outputs = parallel_map.batch(batch_inputs)
    map_results = [item["out"] for item in batch_outputs if item["out"].strip()]
    
    if not map_results:
        return "No relevant information found in the provided documents."
    
    # Combine all map results
    combined_results = "\n\n---\n\n".join(map_results)
    
    # Check if we need to collapse further due to token limits
    estimated_tokens = _num_tokens(combined_results)
    token_limit = settings.MODEL_CONTEXT_WINDOWS.get(model_name, settings.RAG_TOKEN_MAX)
    
    if estimated_tokens > token_limit:
        logger.info(f"Combined results exceed token limit ({estimated_tokens} > {token_limit}), applying recursive collapse")
        
        # Recursive collapse if results are too long
        collapse_chain = (
            RAG_REDUCE_PROMPT
            | llm
            | StrOutputParser()
        ).with_config(run_name="rag_reduce_partial", tags=["rag", "reduce"])
        
        # Split combined results into chunks and reduce iteratively
        result_chunks = text_splitter.split_text(combined_results)
        
        while len(result_chunks) > 1:
            new_chunks = []
            # Process chunks in pairs
            for i in range(0, len(result_chunks), 2):
                if i + 1 < len(result_chunks):
                    chunk_pair = f"{result_chunks[i]}\n\n---\n\n{result_chunks[i+1]}"
                else:
                    chunk_pair = result_chunks[i]
                
                reduced = collapse_chain.invoke({
                    "doc_summaries": chunk_pair,
                    "question": question
                })
                new_chunks.append(reduced)
            
            result_chunks = new_chunks
            logger.info(f"Collapsed to {len(result_chunks)} chunks")
        
        combined_results = result_chunks[0]
    
    # Final reduce step
    logger.info("Running final reduce step")
    try:
        reduce_chain = (
            RAG_REDUCE_PROMPT
            | llm
            | StrOutputParser()
        ).with_config(run_name="rag_reduce", tags=["rag", "reduce"])
        answer = reduce_chain.invoke({
            "doc_summaries": combined_results,
            "question": question
        })
        
        logger.info("Successfully generated RAG answer using LCEL.")
        return answer
    except Exception as e:
        logger.error("An error occurred during LCEL RAG chain execution", exc_info=True)
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
    # Caching for bulk summarization is not implemented in this flow.
    summary, _ = run_summarization_chain(full_content)
    return summary, False


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


# ---------------------------------------------------------------------------
# Async streaming variant (first-token latency optimisation)
# ---------------------------------------------------------------------------

async def astream_rag_chain(
    question: str, context_docs: List[Document]
) -> AsyncGenerator[str, None]:
    """Yield answer tokens incrementally using reduce_runnable.astream()."""
    llm = _get_llm()
    model_name = _get_model_name(llm)
    text_splitter = _get_text_splitter(model_name)

    splits: List[Document] = []
    for doc in context_docs:
        splits.extend(text_splitter.split_documents([doc]))

    map_run = RAG_MAP_PROMPT | llm | StrOutputParser()
    map_batch = RunnableParallel({"out": map_run}).batch(
        [{"context": d.page_content, "question": question} for d in splits]
    )
    snippets = [o["out"] for o in map_batch if o["out"].strip()]
    
    if not snippets:
        yield "No relevant information found in the provided documents."
        return
        
    merged = "\n\n---\n\n".join(snippets)

    reduce_run = RAG_REDUCE_PROMPT | llm | StrOutputParser()
    async for token in reduce_run.astream({"doc_summaries": merged, "question": question}):
        yield token 