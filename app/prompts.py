"""
Centralized prompt templates for the Email Summarizer application.

This module contains all the prompts used across the application for various
LLM tasks including summarization, structured analysis, and RAG queries.
"""

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate


# Email Summarization Prompts
SIMPLE_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that summarizes emails concisely."),
    ("user", "Please summarize the following email:\n\n{text}")
])

STRUCTURED_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that analyzes emails and extracts key information."),
    ("user", "Please analyze the following email and provide a structured summary:\n\n{text}")
])

# Map-Reduce Summarization Prompts (for long documents)
MAP_PROMPT_TEMPLATE = """Write a concise summary of the following:
"{text}"
CONCISE SUMMARY:"""

MAP_PROMPT = PromptTemplate(template=MAP_PROMPT_TEMPLATE, input_variables=["text"])

REDUCE_PROMPT_TEMPLATE = """Write a final consolidated summary of the following summaries:
{text}
FINAL SUMMARY:"""

REDUCE_PROMPT = PromptTemplate(template=REDUCE_PROMPT_TEMPLATE, input_variables=["text"])

# RAG (Retrieval-Augmented Generation) Prompts
RAG_PROMPT_TEMPLATE = """You are an assistant for question-answering tasks. 
Use the following pieces of retrieved context to answer the question. 
If you don't know the answer, just say that you don't know. 
Use three sentences maximum and keep the answer concise.

Question: {question} 

Context: {context} 

Answer:"""

RAG_PROMPT = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

# Bulk Summarization Prompt
BULK_SUMMARY_PROMPT_TEMPLATE = """Please provide a comprehensive digest summary of the following emails. 
Identify common themes, important action items, and key decisions across all messages:

{emails}

DIGEST SUMMARY:"""

BULK_SUMMARY_PROMPT = PromptTemplate(
    template=BULK_SUMMARY_PROMPT_TEMPLATE, 
    input_variables=["emails"]
)

# Email Analysis Prompt (for more detailed analysis)
EMAIL_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert email analyst. Analyze emails to extract:
    1. Main topics and themes
    2. Action items with assigned parties
    3. Key decisions made
    4. Important dates and deadlines
    5. Overall sentiment and urgency level"""),
    ("user", "Analyze this email:\n\n{text}")
])

# Custom prompt for specific email types
MEETING_NOTES_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a meeting notes specialist. Extract key information from meeting-related emails."),
    ("user", """From this email about a meeting, extract:
    - Meeting date/time
    - Attendees mentioned
    - Agenda items
    - Decisions made
    - Action items with owners
    - Next steps
    
    Email: {text}""")
])

PROJECT_UPDATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a project management assistant. Analyze project update emails."),
    ("user", """From this project update email, extract:
    - Project status (on track/delayed/at risk)
    - Completed milestones
    - Upcoming milestones
    - Blockers or risks
    - Resource needs
    - Key metrics mentioned
    
    Email: {text}""")
]) 