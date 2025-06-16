import logging
from typing import List

import requests
from langchain_community.chat_models import ChatOllama
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain

from .auth import get_graph_token
from .config import settings
from .exceptions import EmailNotFoundError, GraphApiError, SummarizationError
from .graph.email_repository import email_repository
from .graph.models import Email

logger = logging.getLogger(__name__)


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


def fetch_email_content(message_id: str) -> str:
    """
    Fetches the body content of a specific email message using the repository.

    Args:
        message_id: The unique identifier of the Microsoft Outlook message.

    Returns:
        The text content of the email body.
    """
    email = email_repository.get_message(message_id)
    return email.get_full_content()


def run_summarization_chain(content: str) -> str:
    """
    Summarizes the given text using a LangChain map-reduce summarization chain.

    This method is ideal for long documents that don't fit into the model's
    context window. It summarizes chunks of the text independently (`map` step)
    and then combines those summaries into a final summary (`reduce` step).

    Args:
        content: The text content to summarize.

    Returns:
        The generated summary.
    """
    llm = _get_llm()
    # Create a single LangChain Document from the raw email content
    docs = [Document(page_content=content)]

    # Split the document into smaller chunks for the map-reduce strategy
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=200)
    split_docs = text_splitter.split_documents(docs)

    # Use LangChain's built-in summarization chain.
    # The `map_reduce` type is robust for documents of any length.
    chain = load_summarize_chain(llm, chain_type="map_reduce")

    logger.info(f"Running summarization chain with {len(split_docs)} documents...")
    try:
        summary = chain.run(split_docs)
        logger.info("Successfully generated summary.")
        return summary
    except Exception as e:
        logger.error("An error occurred during summarization: %s", e, exc_info=True)
        raise SummarizationError(str(e)) from e


def run_bulk_summarization(emails: List[Email]) -> str:
    """
    Creates a single digest summary from a list of emails.

    Args:
        emails: A list of Email objects to be summarized.

    Returns:
        A single string containing the digest summary.
    """
    if not emails:
        return "No emails to summarize."

    # Combine the content of all emails into a single document,
    # separated by a clear delimiter for the LLM to process.
    full_content = "\n\n---\n\n".join([email.get_full_content() for email in emails])
    
    logger.info(f"Running bulk summarization for {len(emails)} emails.")
    # We can reuse the existing summarization chain for the combined content.
    return run_summarization_chain(full_content) 