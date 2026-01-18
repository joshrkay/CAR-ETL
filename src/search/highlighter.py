"""
Search Highlighter - Understanding Plane

Generates text snippets with highlighted query terms.
Wraps matching terms in <mark> tags for UI rendering.
"""

import re
from typing import List, Tuple


class SearchHighlighter:
    """
    Service for generating highlighted search snippets.

    Finds query terms in text and wraps them in <mark> tags.
    Returns snippets centered around matches for better UX.
    """

    def __init__(
        self,
        snippet_length: int = 200,
        max_highlights: int = 3,
    ):
        """
        Initialize search highlighter.

        Args:
            snippet_length: Target length of snippet in characters (default 200)
            max_highlights: Maximum number of highlight snippets per result (default 3)
        """
        self.snippet_length = snippet_length
        self.max_highlights = max_highlights

    def highlight(self, content: str, query: str) -> List[str]:
        """
        Generate highlighted snippets from content.

        Finds query terms in content, wraps them in <mark> tags,
        and returns snippets centered around matches.

        Args:
            content: Full text content to search
            query: Search query (words to highlight)

        Returns:
            List of snippet strings with <mark> tags around matches
            Empty list if no matches found
        """
        if not content or not query:
            return []

        # Extract individual query terms (split on whitespace)
        query_terms = self._extract_query_terms(query)
        if not query_terms:
            return []

        # Find all matches in content
        matches = self._find_matches(content, query_terms)
        if not matches:
            return []

        # Generate snippets around matches
        snippets = self._generate_snippets(content, matches)

        # Limit number of snippets
        return snippets[: self.max_highlights]

    def _extract_query_terms(self, query: str) -> List[str]:
        """
        Extract individual query terms from query string.

        Splits on whitespace and removes common stop words.
        Filters out very short terms (< 2 chars).

        Args:
            query: Search query string

        Returns:
            List of normalized query terms
        """
        # Split on whitespace and punctuation
        terms = re.findall(r'\b\w+\b', query.lower())

        # Filter out stop words and very short terms
        stop_words = {'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
                      'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
                      'that', 'the', 'to', 'was', 'will', 'with'}

        return [term for term in terms if term not in stop_words and len(term) >= 2]

    def _find_matches(self, content: str, query_terms: List[str]) -> List[tuple[int, int, str]]:
        """
        Find all matches of query terms in content.

        Uses case-insensitive word boundary matching.

        Args:
            content: Text content to search
            query_terms: List of terms to find

        Returns:
            List of (start_pos, end_pos, matched_term) tuples
        """
        matches = []

        for term in query_terms:
            # Use word boundary regex for whole-word matching
            # Case-insensitive matching
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)

            for match in pattern.finditer(content):
                matches.append((match.start(), match.end(), match.group()))

        # Sort matches by position
        matches.sort(key=lambda x: x[0])

        return matches

    def _generate_snippets(
        self,
        content: str,
        matches: List[tuple[int, int, str]],
    ) -> List[str]:
        """
        Generate snippets centered around matches.

        Merges overlapping snippets and adds ellipsis where content is truncated.

        Args:
            content: Full text content
            matches: List of (start_pos, end_pos, matched_term) tuples

        Returns:
            List of snippet strings with <mark> tags
        """
        if not matches:
            return []

        snippets = []
        used_positions = set()

        for start, end, term in matches:
            # Skip if this match is already covered by a previous snippet
            if start in used_positions:
                continue

            # Calculate snippet boundaries
            snippet_start = max(0, start - self.snippet_length // 2)
            snippet_end = min(len(content), end + self.snippet_length // 2)

            # Adjust to word boundaries for cleaner snippets
            snippet_start = self._find_word_boundary(content, snippet_start, forward=False)
            snippet_end = self._find_word_boundary(content, snippet_end, forward=True)

            # Extract snippet
            snippet = content[snippet_start:snippet_end]

            # Highlight all query term matches within this snippet
            snippet = self._highlight_terms(snippet, matches, snippet_start)

            # Add ellipsis if truncated
            if snippet_start > 0:
                snippet = "..." + snippet
            if snippet_end < len(content):
                snippet = snippet + "..."

            snippets.append(snippet)

            # Mark entire snippet range as used to avoid overlapping snippets
            for pos in range(snippet_start, snippet_end):
                used_positions.add(pos)

        return snippets

    def _find_word_boundary(
        self,
        content: str,
        position: int,
        forward: bool = True,
    ) -> int:
        """
        Find nearest word boundary from position.

        Args:
            content: Text content
            position: Starting position
            forward: If True, search forward; otherwise search backward

        Returns:
            Position of nearest word boundary
        """
        if position <= 0:
            return 0
        if position >= len(content):
            return len(content)

        # Search for word boundary (space, punctuation, or start/end)
        if forward:
            while position < len(content) and content[position].isalnum():
                position += 1
        else:
            while position > 0 and content[position - 1].isalnum():
                position -= 1

        return position

    def _highlight_terms(
        self,
        snippet: str,
        matches: List[tuple[int, int, str]],
        snippet_start: int,
    ) -> str:
        """
        Add <mark> tags around matching terms in snippet.

        Args:
            snippet: Text snippet
            matches: All matches in original content
            snippet_start: Starting position of snippet in original content

        Returns:
            Snippet with <mark> tags around matches
        """
        # Find matches that fall within this snippet
        snippet_end = snippet_start + len(snippet)
        relevant_matches = [
            (start - snippet_start, end - snippet_start, term)
            for start, end, term in matches
            if start >= snippet_start and end <= snippet_end
        ]

        if not relevant_matches:
            return snippet

        # Sort matches by position (descending) to avoid offset issues
        relevant_matches.sort(key=lambda x: x[0], reverse=True)

        # Insert <mark> tags (backward to avoid position shifts)
        result = snippet
        for start, end, term in relevant_matches:
            result = result[:start] + "<mark>" + result[start:end] + "</mark>" + result[end:]

        return result
