import re
from typing import Iterable

from sql_analyze_app.models.analysis_result import AnalysisResult

try:
    from sqlglot import exp, parse
    from sqlglot.tokens import Tokenizer, TokenType
except ImportError:
    exp = None
    parse = None
    Tokenizer = None
    TokenType = None


CTE_PATTERN = re.compile(r"\bWITH\s+([A-Z_][\w$#]*)\s+AS\s*\(", re.IGNORECASE)
TABLE_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Z_][\w$#]*(?:\.[A-Z_][\w$#]*)?)",
    re.IGNORECASE,
)
JOIN_PATTERN = re.compile(
    r"\b((?:LEFT|RIGHT|FULL|INNER|CROSS)\s+)?JOIN\s+"
    r"([A-Z_][\w$#]*(?:\.[A-Z_][\w$#]*)?)"
    r"(?:\s+(?:AS\s+)?[A-Z_][\w$#]*)?\s+ON\s+",
    re.IGNORECASE,
)


def parseSql(sqlText: str, includeTablesWithoutConditions: bool = False) -> list[AnalysisResult]:
    cleanedSql = _normalizeSql(sqlText)
    if not cleanedSql:
        return []

    cteNames = _extractCteNames(cleanedSql)
    rows = _parseWithSqlglot(cleanedSql, cteNames)
    if not rows:
        rows = _parseWithFallback(cleanedSql, cteNames)

    if includeTablesWithoutConditions:
        rows = _appendTablesWithoutConditions(cleanedSql, cteNames, rows)

    rows.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[4]))
    return [
        AnalysisResult(index + 1, row[1], row[2], row[3], row[4])
        for index, row in enumerate(rows)
    ]


def parseSourceTables(sqlText: str) -> list[str]:
    cleanedSql = _normalizeSql(sqlText)
    if not cleanedSql:
        return []

    cteNames = _extractCteNames(cleanedSql)
    return list(_allTablesFromText(cleanedSql, cteNames))


def _parseWithSqlglot(sqlText: str, cteNames: set[str]) -> list[tuple[int, str, str, str, str]]:
    if parse is None or exp is None:
        return []

    rows: list[tuple[int, str, str, str, str]] = []
    try:
        statements = parse(sqlText)
    except Exception:
        return []

    selectBlocks = _selectBlocks(sqlText, statements)
    for statement in statements:
        cteSourceMap = _cteSourceMap(statement, cteNames)
        for selectExpression in statement.find_all(exp.Select):
            blockStart, blockLabel = selectBlocks.get(id(selectExpression), (len(sqlText), "CODE BLOCK ?"))
            aliasSourceMap = _aliasSourceMap(selectExpression, cteNames, cteSourceMap)
            rows.extend(_extractJoinRows(selectExpression, cteNames, blockStart, blockLabel))
            rows.extend(_extractWhereRows(selectExpression, aliasSourceMap, blockStart, blockLabel))

    return rows


def _extractJoinRows(
    selectExpression,
    cteNames: set[str],
    blockStart: int,
    blockLabel: str,
) -> list[tuple[int, str, str, str, str]]:
    rows: list[tuple[int, str, str, str, str]] = []
    for joinIndex, joinExpression in enumerate(selectExpression.args.get("joins") or []):
        onExpression = joinExpression.args.get("on")
        if onExpression is None:
            continue

        tableName = _directPhysicalJoinTableName(joinExpression.this, cteNames)
        onText = _expressionSql(onExpression)
        rows.append((blockStart * 1000 + 100 + joinIndex, blockLabel, tableName, "JOIN", onText))

    return rows


def _extractWhereRows(
    selectExpression,
    aliasSourceMap: dict[str, list[str]],
    blockStart: int,
    blockLabel: str,
) -> list[tuple[int, str, str, str, str]]:
    whereExpression = selectExpression.args.get("where")
    if whereExpression is None:
        return []

    tableNames = _whereTableNames(whereExpression, aliasSourceMap)
    tableName = tableNames[0] if tableNames else ""
    conditionExpression = whereExpression.this if hasattr(whereExpression, "this") else whereExpression
    conditionText = _expressionSql(conditionExpression)
    return [(blockStart * 1000 + 500, blockLabel, tableName, "WHERE", conditionText)]


def _selectBlocks(sqlText: str, statements) -> dict[int, tuple[int, str]]:
    selectExpressions = []
    for statement in statements:
        selectExpressions.extend(statement.find_all(exp.Select))

    positionsByDepth = _selectPositionsByDepth(sqlText)
    depthIndexes: dict[int, int] = {}
    blockPositions: dict[int, int] = {}
    for selectExpression in selectExpressions:
        depth = _selectDepth(selectExpression)
        index = depthIndexes.get(depth, 0)
        depthIndexes[depth] = index + 1
        positions = positionsByDepth.get(depth) or []
        blockPositions[id(selectExpression)] = positions[index] if index < len(positions) else len(sqlText) + index

    orderedPositions = sorted(set(blockPositions.values()))
    labels = {position: f"CODE BLOCK {index + 1}" for index, position in enumerate(orderedPositions)}
    return {
        expressionId: (position, labels[position])
        for expressionId, position in blockPositions.items()
    }


def _selectPositionsByDepth(sqlText: str) -> dict[int, list[int]]:
    if Tokenizer is None or TokenType is None:
        return {0: [match.start() for match in re.finditer(r"\bSELECT\b", sqlText, re.IGNORECASE)]}

    positionsByDepth: dict[int, list[int]] = {}
    depth = 0
    for token in Tokenizer().tokenize(sqlText):
        if token.token_type == TokenType.L_PAREN:
            depth += 1
        elif token.token_type == TokenType.R_PAREN:
            depth = max(depth - 1, 0)
        elif token.token_type == TokenType.SELECT:
            positionsByDepth.setdefault(depth, []).append(token.start)
    return positionsByDepth


def _selectDepth(selectExpression) -> int:
    depth = 0
    parent = getattr(selectExpression, "parent", None)
    while parent is not None:
        if isinstance(parent, exp.Select):
            depth += 1
        parent = getattr(parent, "parent", None)
    return depth


def _cteSourceMap(statement, cteNames: set[str]) -> dict[str, list[str]]:
    sourceMap: dict[str, list[str]] = {}
    for cteExpression in statement.find_all(exp.CTE):
        alias = str(cteExpression.alias or "").upper()
        if not alias:
            continue
        tableNames = _tableNamesInside(cteExpression.this, cteNames)
        if tableNames:
            sourceMap[alias] = tableNames
    return sourceMap


def _aliasSourceMap(
    selectExpression,
    cteNames: set[str],
    cteSourceMap: dict[str, list[str]],
) -> dict[str, list[str]]:
    sourceMap: dict[str, list[str]] = {}

    fromExpression = selectExpression.args.get("from") or selectExpression.args.get("from_")
    if fromExpression is not None:
        _addRelationAlias(sourceMap, getattr(fromExpression, "this", None), cteNames, cteSourceMap)
        for relation in fromExpression.args.get("expressions") or []:
            _addRelationAlias(sourceMap, relation, cteNames, cteSourceMap)

    for joinExpression in selectExpression.args.get("joins") or []:
        _addRelationAlias(sourceMap, joinExpression.this, cteNames, cteSourceMap)

    return sourceMap


def _addRelationAlias(
    sourceMap: dict[str, list[str]],
    relation,
    cteNames: set[str],
    cteSourceMap: dict[str, list[str]],
) -> None:
    if relation is None:
        return

    tableNames = _tableNamesFromRelation(relation, cteNames, cteSourceMap)
    if not tableNames:
        return

    alias = _relationAlias(relation)
    if alias:
        sourceMap[alias.upper()] = tableNames

    if isinstance(relation, exp.Table):
        sourceMap[relation.name.upper()] = tableNames


def _whereTableNames(whereExpression, aliasSourceMap: dict[str, list[str]]) -> list[str]:
    tableNames: list[str] = []
    seen = set()
    for columnExpression in whereExpression.find_all(exp.Column):
        alias = str(columnExpression.table or "").upper()
        if not alias or alias not in aliasSourceMap:
            continue
        for tableName in aliasSourceMap[alias]:
            if tableName.upper() not in seen:
                tableNames.append(tableName)
                seen.add(tableName.upper())
    return tableNames


def _tableNamesFromRelation(
    relation,
    cteNames: set[str],
    cteSourceMap: dict[str, list[str]],
) -> list[str]:
    if relation is None:
        return []

    if isinstance(relation, exp.Table):
        name = relation.name.upper()
        if name in cteNames:
            return cteSourceMap.get(name, [])
        tableName = _tableNameFromExpression(relation, cteNames)
        return [tableName] if tableName else []

    if isinstance(relation, (exp.Subquery, exp.Select)):
        return _tableNamesInside(relation, cteNames)

    tableExpression = relation.find(exp.Table)
    if tableExpression is not None:
        return _tableNamesFromRelation(tableExpression, cteNames, cteSourceMap)

    return []


def _directPhysicalJoinTableName(relation, cteNames: set[str]) -> str:
    if not isinstance(relation, exp.Table):
        return ""

    name = relation.name.upper()
    if name in cteNames:
        return ""

    return _tableNameFromExpression(relation, cteNames)


def _tableNamesInside(expression, cteNames: set[str]) -> list[str]:
    tableNames: list[str] = []
    seen = set()
    for tableExpression in expression.find_all(exp.Table):
        name = tableExpression.name.upper()
        if name in cteNames:
            continue
        tableName = _tableNameFromExpression(tableExpression, cteNames)
        if tableName and tableName.upper() not in seen:
            tableNames.append(tableName)
            seen.add(tableName.upper())
    return tableNames


def _relationAlias(relation) -> str:
    return str(getattr(relation, "alias", "") or "").upper()


def _firstFromTable(selectExpression, cteNames: set[str]) -> str:
    fromExpression = selectExpression.args.get("from") or selectExpression.args.get("from_")
    candidates = []
    if fromExpression is not None:
        candidates.append(getattr(fromExpression, "this", None))
        candidates.extend(fromExpression.args.get("expressions") or [])

    for candidate in candidates:
        tableName = _tableNameFromExpression(candidate, cteNames)
        if tableName:
            return tableName

    return ""


def _tableNameFromExpression(expression, cteNames: set[str]) -> str:
    if expression is None:
        return ""

    tableExpression = expression if isinstance(expression, exp.Table) else expression.find(exp.Table)
    if tableExpression is None:
        return ""

    name = tableExpression.name
    if name.upper() in cteNames:
        return ""

    database = tableExpression.args.get("db")
    catalog = tableExpression.args.get("catalog")
    parts = [str(part) for part in (catalog, database, name) if part]
    return ".".join(parts).upper()


def _joinType(joinExpression) -> str:
    side = str(joinExpression.args.get("side") or "").upper()
    kind = str(joinExpression.args.get("kind") or "").upper()
    if side and kind:
        return f"{side} {kind}"
    if side:
        return side
    if kind:
        return kind
    return "INNER"


def _expressionSql(expression) -> str:
    return _squashWhitespace(expression.sql(dialect=""))


def _parseWithFallback(sqlText: str, cteNames: set[str]) -> list[tuple[int, str, str, str, str]]:
    rows: list[tuple[int, str, str, str, str]] = []
    blockLabel = "CODE BLOCK 1"
    for joinIndex, joinMatch in enumerate(JOIN_PATTERN.finditer(sqlText)):
        tableName = _physicalName(joinMatch.group(2))
        if tableName.upper() in cteNames:
            continue

        onStart = joinMatch.end()
        onEnd = _findConditionEnd(sqlText, onStart)
        onText = _squashWhitespace(sqlText[onStart:onEnd])
        rows.append((joinMatch.start() * 1000 + joinIndex, blockLabel, tableName, "JOIN", onText))

    firstTable = _firstTableFromText(sqlText, cteNames)
    whereText = _extractWhereText(sqlText)
    if firstTable and whereText:
        whereStart = _whereStart(sqlText)
        rows.append((whereStart * 1000, blockLabel, firstTable, "WHERE", whereText))

    return rows


def _appendTablesWithoutConditions(
    sqlText: str,
    cteNames: set[str],
    rows: list[tuple[int, str, str, str, str]],
) -> list[tuple[int, str, str, str, str]]:
    existingTables = {row[2].upper() for row in rows if row[2]}
    additionalRows = []
    for index, tableName in enumerate(_allTablesFromText(sqlText, cteNames)):
        if tableName.upper() not in existingTables:
            additionalRows.append((len(sqlText) * 1000 + index, "TABLE ONLY", tableName, "NONE", "조건문 없음"))
    return rows + additionalRows


def _allTablesFromText(sqlText: str, cteNames: set[str]) -> Iterable[str]:
    seen = set()
    for match in TABLE_PATTERN.finditer(sqlText):
        tableName = _physicalName(match.group(1))
        upperName = tableName.upper()
        if upperName not in cteNames and upperName not in seen:
            seen.add(upperName)
            yield tableName


def _firstTableFromText(sqlText: str, cteNames: set[str]) -> str:
    return next(iter(_allTablesFromText(sqlText, cteNames)), "")


def _extractWhereText(sqlText: str) -> str:
    match = re.search(r"\bWHERE\b", sqlText, re.IGNORECASE)
    if not match:
        return ""

    end = _findConditionEnd(sqlText, match.end())
    return _squashWhitespace(sqlText[match.end():end].rstrip(";"))


def _whereStart(sqlText: str) -> int:
    match = re.search(r"\bWHERE\b", sqlText, re.IGNORECASE)
    return match.start() if match else len(sqlText)


def _findConditionEnd(sqlText: str, startIndex: int) -> int:
    keywords = (" WHERE ", " GROUP BY ", " ORDER BY ", " HAVING ", " UNION ", " JOIN ", " LEFT JOIN ", " RIGHT JOIN ", " INNER JOIN ", " FULL JOIN ", " CROSS JOIN ", ";")
    upperText = f" {sqlText.upper()} "
    positions = []
    for keyword in keywords:
        found = upperText.find(keyword, startIndex)
        if found >= 0:
            positions.append(max(found - 1, startIndex))
    return min(positions) if positions else len(sqlText)


def _extractCteNames(sqlText: str) -> set[str]:
    names = set()
    for match in CTE_PATTERN.finditer(sqlText):
        names.add(match.group(1).upper())
    return names


def _normalizeSql(sqlText: str) -> str:
    withoutLineComments = re.sub(r"--.*?$", "", sqlText or "", flags=re.MULTILINE)
    withoutBlockComments = re.sub(r"/\*.*?\*/", "", withoutLineComments, flags=re.DOTALL)
    return withoutBlockComments.strip()


def _physicalName(tableText: str) -> str:
    return tableText.strip().strip('"`[]').upper()


def _squashWhitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
