from typing import Any, List

class RecognizerResult:
    entity_type: str
    start: int
    end: int

class AnalyzerEngine:
    def analyze(self, text: str, language: str, entities: Any | None = ...) -> List[RecognizerResult]: ...
