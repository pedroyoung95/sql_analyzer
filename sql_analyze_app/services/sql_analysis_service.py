from sql_analyze_app.models.analysis_result import AnalysisResult
from sql_analyze_app.models.source_table_result import SourceTableResult
from sql_analyze_app.parsers.sql_parser import parseSourceTables, parseSql
from sql_analyze_app.repositories.file_repository import readSqlFile


def loadSqlFile(filePath: str) -> str:
    return readSqlFile(filePath)


def analyzeSql(sqlText: str, includeTablesWithoutConditions: bool = False) -> list[AnalysisResult]:
    if not sqlText or not sqlText.strip():
        raise ValueError("SQL을 입력하거나 파일을 업로드해주세요.")

    results = parseSql(sqlText, includeTablesWithoutConditions)
    if not results:
        raise ValueError("분석 가능한 테이블 또는 조건문을 찾지 못했습니다.")

    return results


def analyzeSourceTables(sqlText: str) -> list[SourceTableResult]:
    if not sqlText or not sqlText.strip():
        raise ValueError("SQL을 입력하거나 파일을 업로드해주세요.")

    tableNames = parseSourceTables(sqlText)
    return [
        SourceTableResult(index + 1, tableName)
        for index, tableName in enumerate(tableNames)
    ]
