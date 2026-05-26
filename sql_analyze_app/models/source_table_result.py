from dataclasses import dataclass


@dataclass(frozen=True)
class SourceTableResult:
    no: int
    tableName: str
