from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisResult:
    no: int
    codeBlock: str
    tableName: str
    conditionType: str
    conditionText: str
