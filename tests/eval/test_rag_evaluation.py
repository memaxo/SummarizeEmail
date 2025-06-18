import pytest
from langchain_core.documents import Document

from app.services.email import run_rag_chain

# Golden dataset for RAG evaluation
# This dataset contains question-context-answer triplets.
RAG_GOLDEN_DATASET = [
    {
        "question": "What is the status of the Project Alpha deployment?",
        "context": [
            Document(page_content="Subject: Project Alpha Update\n\nHi team, the deployment for Project Alpha is currently on hold due to a critical bug in the payment module. We are targeting a fix by EOD Friday."),
            Document(page_content="Subject: Re: Project Alpha Update\n\nThanks for the update. Let's sync on Monday to discuss the new timeline."),
        ],
        "expected_answer_keywords": ["on hold", "critical bug", "payment module"],
    },
    {
        "question": "When is the Q3 budget meeting?",
        "context": [
            Document(page_content="Subject: Upcoming Meetings\n\nPlease note that the Q3 budget review has been moved to August 5th at 10 AM in Conference Room B."),
            Document(page_content="Subject: Office Maintenance\n\nThe kitchen will be closed for cleaning on August 5th."),
        ],
        "expected_answer_keywords": ["august 5th"],
    },
    {
        "question": "What is the capital of France?",
        "context": [
            Document(page_content="Subject: Travel Itinerary\n\nYour trip to Italy is confirmed. You will be flying to Rome."),
            Document(page_content="Subject: Lunch Menu\n\nToday's special is spaghetti carbonara."),
        ],
        "expected_answer_keywords": ["cannot answer", "not contain", "no information"],
    }
]

@pytest.mark.parametrize("data", RAG_GOLDEN_DATASET)
def test_rag_chain_evaluation(data):
    """
    Tests the RAG chain against a golden dataset to evaluate its performance.
    """
    # 1. Run the RAG chain with the question and context
    answer = run_rag_chain(question=data["question"], context_docs=data["context"])
    
    # 2. Assert that the generated answer contains at least one of the expected keywords
    # This is a simple form of evaluation. More advanced methods could use
    # semantic similarity or LLM-based evaluation.
    answer_lower = answer.lower()
    keywords_found = [keyword for keyword in data["expected_answer_keywords"] if keyword.lower() in answer_lower]
    
    # For the "cannot answer" case, check for any indication that the question cannot be answered
    if "cannot answer" in data["expected_answer_keywords"]:
        # Accept various phrasings that indicate the question cannot be answered
        negative_indicators = [
            "cannot be answered", "can't answer", "unable to answer", 
            "no information", "not contain", "irrelevant",
            "not available", "is not available", "not found",
            "no relevant", "not in", "doesn't contain"
        ]
        keywords_found = [indicator for indicator in negative_indicators if indicator in answer_lower]
    
    assert len(keywords_found) > 0, f"Answer did not contain any expected keywords. Expected: {data['expected_answer_keywords']}, Answer: {answer}" 