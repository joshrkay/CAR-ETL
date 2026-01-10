from typing import Any, Dict, List, Mapping
from presidio_analyzer import RecognizerResult

class AnonymizerResult:
    text: str

class AnonymizerEngine:
    def anonymize(
        self,
        text: str,
        analyzer_results: List[RecognizerResult],
        operators: Mapping[str, Any] | None = ...,
    ) -> AnonymizerResult: ...
