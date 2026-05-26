from pathlib import Path


def readSqlFile(filePath: str) -> str:
    path = Path(filePath)
    if not path.exists():
        raise FileNotFoundError("선택한 SQL 파일을 찾을 수 없습니다.")

    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError("unknown", b"", 0, 1, "SQL 파일의 문자 인코딩을 확인해주세요.")
