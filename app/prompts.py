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
RAG_PROMPT_TEMPLATE = """You are a highly intelligent assistant for answering questions based on a user's emails.
Your goal is to synthesize information from the provided email context to answer the user's question accurately.

Please follow these rules:
1.  Base your answer *only* on the context provided in the emails. Do not use any outside knowledge.
2.  If the context does not contain the answer, you MUST state that you cannot answer the question with the information you have. Do not try to guess.
3.  Be concise and directly answer the question. Quote relevant snippets from the emails to support your answer where possible.

Question: {question}

Here is the context from the user's emails:
---
{context}
---

Based on the context above, please provide the answer.
Answer:"""

RAG_PROMPT = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

# LCEL-optimized RAG prompts for map-reduce pattern
RAG_MAP_PROMPT_TEMPLATE = """Use the following portion of a long document to see if any of the text is relevant to answer the question.
Return any relevant text verbatim. Quote the exact relevant portions.

Question: {question}

Document excerpt:
---
{context}
---

Relevant text:"""

RAG_MAP_PROMPT = ChatPromptTemplate.from_template(RAG_MAP_PROMPT_TEMPLATE)

RAG_REDUCE_PROMPT_TEMPLATE = """You are synthesizing information from multiple email excerpts to answer a user's question.

Question: {question}

Here are the relevant excerpts from the user's emails:
---
{doc_summaries}
---

Based on these excerpts, provide a final, consolidated answer. Follow these rules:
1. Base your answer only on the provided excerpts
2. If the excerpts don't contain enough information, state that clearly
3. Be concise and directly answer the question
4. Quote relevant snippets where appropriate

Answer:"""

RAG_REDUCE_PROMPT = ChatPromptTemplate.from_template(RAG_REDUCE_PROMPT_TEMPLATE)

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