import structlog
from typing import List, Tuple

import requests
from langchain_community.chat_models import ChatOllama
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from fastapi import Request
import hashlib
import jwt

from ..auth import get_graph_token
from ..config import settings
from ..exceptions import EmailNotFoundError, GraphApiError, SummarizationError, RAGError
from ..graph.email_repository import EmailRepository
from ..graph.models import Email
from .document_parser import document_parser

logger = structlog.get_logger(__name__)


def _get_llm() -> BaseChatModel:
    """
    Factory function to get the appropriate LLM client based on settings.
    This allows for easy swapping between OpenAI and a self-hosted Ollama model.
    """
    provider = settings.LLM_PROVIDER.lower()
    logger.info(f"Initializing LLM for provider: {provider}")

    if provider == "openai":
        return ChatOpenAI(
            temperature=0,
            model_name=settings.OPENAI_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY,
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
    """Fetch email content from Microsoft Graph API.
    
    In production, uses the user ID from the OAuth token.
    In development, falls back to TARGET_USER_ID.
    """
    # Get user ID from token in production, or from env in development
    user_id = await get_user_id_from_token(request)
    
    try:
        # Create a repository instance for this specific user
        email_repo = EmailRepository(user_id=user_id)
        # Get the email using the dynamic user ID
        email = email_repo.get_message(msg_id)
        
        content = email.get_full_content()

        if include_attachments:
            logger.info("Fetching attachments for email", message_id=msg_id)
            attachments = email_repo.list_attachments(msg_id)
            
            for attachment_meta in attachments:
                logger.info("Parsing attachment", attachment_id=attachment_meta.id)
                # Fetch the full attachment with its content bytes
                full_attachment = email_repo.get_attachment(msg_id, attachment_meta.id)
                
                # Parse the content using our service
                attachment_text = document_parser.parse_content(full_attachment.contentBytes)
                
                if attachment_text:
                    content += f"\n\n--- Attachment: {attachment_meta.name} ---\n{attachment_text}"

        return content
    except Exception as e:
        logger.error(f"Error fetching email content: {e}")
        raise EmailNotFoundError(f"Email not found: {msg_id}") from e


async def summarize_email(content: str) -> str:
    """
    Generate a summary for email content using the configured LLM.
    
    Args:
        content: The email content to summarize
        
    Returns:
        The generated summary
    """
    llm = _get_llm()
    
    # Create a simple summarization prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant that summarizes emails concisely."),
        ("user", "Please summarize the following email:\n\n{text}")
    ])
    
    # Create and run the chain
    chain = prompt | llm
    response = chain.invoke({"text": content})
    
    return response.content


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
    chain = load_summarize_chain(llm, chain_type="map_reduce")

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
    
    # This prompt instructs the LLM to answer the user's question *only* based
    # on the provided context documents. This is a crucial part of RAG.
    template = """
    You are an assistant for question-answering tasks. 
    Use the following pieces of retrieved context to answer the question. 
    If you don't know the answer, just say that you don't know. 
    Use three sentences maximum and keep the answer concise.

    Question: {question} 

    Context: {context} 

    Answer:
    """
    prompt = ChatPromptTemplate.from_template(template)

    # This chain "stuffs" all the documents into the {context} part of the prompt
    # and sends it to the LLM.
    question_answer_chain = create_stuff_documents_chain(llm, prompt)

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