"""
Parser Router - Understanding Plane

Routes documents to optimal parsers based on MIME type and conditions.
Implements fallback logic when primary parser fails.
"""
import logging
from pathlib import Path
from typing import Any, cast

import yaml

from src.exceptions import ParserError

from .config import get_parser_config
from .parsers.base import BaseParser, ParseResult
from .parsers.openpyxl import OpenPyXLParser
from .parsers.pandas import PandasParser
from .parsers.ragflow import RagFlowParser
from .parsers.tika import TikaParser
from .parsers.unstructured import UnstructuredParser

logger = logging.getLogger(__name__)


def load_parser_routes() -> dict[str, Any]:
    """
    Load parser routing configuration from YAML file.

    Returns:
        Dictionary mapping MIME types to parser routes

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / "config" / "parser_routes.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Parser routes config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    routes = config.get("parser_routes", {}) if isinstance(config, dict) else {}
    return cast(dict[str, Any], routes)


def match_mime_type(mime_type: str, routes: dict[str, Any]) -> dict[str, Any] | None:
    """
    Match MIME type to routing configuration.

    Handles exact matches and wildcard patterns (e.g., "image/*").

    Args:
        mime_type: Document MIME type
        routes: Parser routing configuration

    Returns:
        Route configuration for the MIME type, or None if no match
    """
    # Try exact match first
    if mime_type in routes:
        return cast(dict[str, Any], routes[mime_type])

    # Try wildcard match (e.g., "image/*" for "image/png")
    type_prefix = mime_type.split("/")[0]
    wildcard_key = f"{type_prefix}/*"

    if wildcard_key in routes:
        return cast(dict[str, Any], routes[wildcard_key])

    return None


def get_parser(parser_name: str) -> BaseParser:
    """
    Get parser instance by name.

    Args:
        parser_name: Name of parser (ragflow, unstructured, tika, pandas, openpyxl)

    Returns:
        Parser instance

    Raises:
        ValueError: If parser name is unknown
    """
    config = get_parser_config()

    if parser_name == "ragflow":
        return RagFlowParser(api_url=config.ragflow_api_url, api_key=config.ragflow_api_key)
    elif parser_name == "unstructured":
        return UnstructuredParser(api_url=config.unstructured_api_url, api_key=config.unstructured_api_key)
    elif parser_name == "tika":
        return TikaParser(api_url=config.tika_api_url)
    elif parser_name == "pandas":
        return PandasParser()
    elif parser_name == "openpyxl":
        return OpenPyXLParser()
    else:
        raise ValueError(f"Unknown parser: {parser_name}")


async def _detect_document_characteristics(
    content: bytes,
    mime_type: str
) -> dict[str, bool]:
    """
    Detect document characteristics for conditional routing.

    Args:
        content: Raw document bytes
        mime_type: Document MIME type

    Returns:
        Dictionary with detected characteristics (has_tables, scanned, simple_text)
    """
    characteristics = {
        "has_tables": False,
        "scanned": False,
        "simple_text": False,
    }

    # For PDFs, do quick probe to detect characteristics
    if mime_type == "application/pdf":
        try:
            # Quick probe: check if PDF has text layer
            # If no text extractable, likely scanned
            probe_parser = get_parser("tika")
            probe_result = await probe_parser.parse(content, mime_type)

            # Check if text is very short (likely scanned image)
            if len(probe_result.text.strip()) < 100:
                characteristics["scanned"] = True

            # Check if document has tables (simple heuristic: look for tabular patterns)
            if probe_result.tables:
                characteristics["has_tables"] = True
            elif "\t" in probe_result.text or "|" in probe_result.text:
                # Simple heuristic: tabs or pipes suggest tables
                characteristics["has_tables"] = True

            # Check if simple text (mostly plain text, minimal formatting)
            if len(probe_result.text) > 0 and len(probe_result.pages) <= 1:
                # Simple heuristic: single page with text suggests simple document
                characteristics["simple_text"] = True
        except Exception:
            # If probe fails, use defaults
            logger.debug("Failed to probe document characteristics, using defaults")

    # For text files, mark as simple_text
    elif mime_type.startswith("text/"):
        characteristics["simple_text"] = True

    return characteristics


def _select_parser_from_conditions(
    route: dict[str, Any],
    characteristics: dict[str, bool]
) -> str | None:
    """
    Select parser based on document characteristics and route conditions.

    Args:
        route: Route configuration
        characteristics: Detected document characteristics

    Returns:
        Parser name if condition matches, None otherwise
    """
    conditions = route.get("conditions", {})

    # Check conditions in order of specificity
    if characteristics.get("has_tables") and "has_tables" in conditions:
        parser_name = conditions.get("has_tables")
        return cast(str | None, parser_name)

    if characteristics.get("scanned") and "scanned" in conditions:
        parser_name = conditions.get("scanned")
        return cast(str | None, parser_name)

    if characteristics.get("simple_text") and "simple_text" in conditions:
        parser_name = conditions.get("simple_text")
        return cast(str | None, parser_name)

    return None


async def route_document(content: bytes, mime_type: str) -> ParseResult:
    """
    Route document to optimal parser with fallback support.

    Matches the exact router logic from requirements:
    - Gets route by MIME type (with text/* fallback)
    - Checks conditions to select optimal parser
    - Uses route["default"] parser if no conditions match
    - Falls back to route["fallback"] if primary fails

    Args:
        content: Raw document bytes
        mime_type: Document MIME type

    Returns:
        ParseResult with extracted content

    Raises:
        ParserError: If all parsers fail
        ValueError: If no route found for MIME type
    """
    routes = load_parser_routes()
    route = match_mime_type(mime_type, routes)

    if route is None:
        route = routes.get("text/*")
        if route is None:
            raise ValueError(f"No parser route found for MIME type: {mime_type}")

    # Check conditions for optimal parser selection (only if conditions exist)
    parser_name = route.get("default")
    if route.get("conditions"):
        characteristics = await _detect_document_characteristics(content, mime_type)
        conditional_parser = _select_parser_from_conditions(route, characteristics)
        if conditional_parser:
            parser_name = conditional_parser
    if parser_name is None:
        raise ValueError(f"No default parser configured for MIME type: {mime_type}")

    parser = get_parser(parser_name)

    try:
        logger.info(f"Parsing document with {parser_name} (MIME: {mime_type})")
        return await parser.parse(content, mime_type)
    except ParserError as e:
        logger.warning(f"Primary parser {parser_name} failed: {e.message}")
        fallback_name = route.get("fallback")
        if fallback_name:
            logger.info(f"Attempting fallback parser: {fallback_name}")
            fallback = get_parser(fallback_name)
            return await fallback.parse(content, mime_type)
        raise
