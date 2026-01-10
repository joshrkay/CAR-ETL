"""LLM generator for RAG pipeline with citation enforcement."""
import logging
import os
from typing import Optional
from openai import AsyncOpenAI

from .prompts import format_system_prompt, format_user_prompt

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = "gpt-4o-mini"


class Generator:
    """
    LLM generator for answering questions with citations.

    Enforces citation requirements via system prompt.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        """
        Initialize generator.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: LLM model to use
        """
        api_key = api_key or OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, question: str, context: str) -> str:
        """
        Generate answer from question and context.

        Args:
            question: User question
            context: Assembled context with citations

        Returns:
            Generated answer with citations

        Raises:
            Exception: If LLM call fails
        """
        system_prompt = format_system_prompt(context)
        user_prompt = format_user_prompt(question)

        logger.info(
            "Generating answer with LLM",
            extra={
                "model": self.model,
                "question_length": len(question),
                "context_length": len(context),
            },
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,  # Deterministic for consistency
            )

            answer = response.choices[0].message.content

            logger.info(
                "Generated answer",
                extra={
                    "answer_length": len(answer),
                    "tokens_used": response.usage.total_tokens,
                },
            )

            return answer

        except Exception as e:
            logger.error(
                "Failed to generate answer",
                extra={
                    "error": str(e),
                    "model": self.model,
                },
            )
            raise
