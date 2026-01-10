"""Prompt templates for RAG Q&A."""

SYSTEM_PROMPT = """You are a CRE document analyst answering questions about commercial real estate documents.

RULES:
1. Answer ONLY using the provided context
2. Every factual claim MUST have a citation in format [DOC:uuid:PAGE:n]
3. If the answer is not in context, respond: "I don't have enough information to answer this based on the available documents."
4. Never make up information
5. For numbers, quote exactly from source

CONTEXT:
{context}"""


def format_system_prompt(context: str) -> str:
    """
    Format system prompt with context.

    Args:
        context: Assembled context from retrieved chunks

    Returns:
        Formatted system prompt
    """
    return SYSTEM_PROMPT.format(context=context)


def format_user_prompt(question: str) -> str:
    """
    Format user question prompt.

    Args:
        question: User's question

    Returns:
        Formatted user prompt
    """
    return question
