# SQL Analyze Desktop App

Windows에서 SQL 문장을 분석해 소스 테이블과 WHERE/JOIN 조건문을 별도 탭으로 보여주고 Excel 파일로 저장하는 데스크톱 프로그램입니다.

## 실행 방법

개발 환경에서 실행:

```powershell
python -m sql_analyze_app.main
```

빌드된 EXE 실행:

```text
dist\SQL조건분석기.exe
```

사용자는 `dist` 폴더 안의 `SQL조건분석기.exe` 파일을 더블클릭하면 됩니다.

## 필요한 라이브러리

- PySide6
- sqlglot
- openpyxl
- PyInstaller

설치:

```powershell
pip install -r requirements.txt
```

## EXE 빌드 방법

PyInstaller 빌드 명령어:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name "SQL조건분석기" sql_analyze_app/main.py
```

빌드 후 생성되는 EXE 위치:

```text
dist\SQL조건분석기.exe
```

## 파일 역할

- `sql_analyze_app/main.py`: 프로그램 진입점
- `sql_analyze_app/controllers/main_window.py`: GUI 요청 처리
- `sql_analyze_app/services/sql_analysis_service.py`: SQL 분석 호출 및 결과 정리
- `sql_analyze_app/services/excel_export_service.py`: Excel 저장 처리
- `sql_analyze_app/repositories/file_repository.py`: SQL 파일 읽기
- `sql_analyze_app/parsers/sql_parser.py`: sqlglot 기반 SQL 파싱 및 조건 추출
- `sql_analyze_app/models/analysis_result.py`: 분석 결과 데이터 모델
- `tests/test_sql_analysis.py`: SQL 분석 테스트

## 결과 컬럼

소스 테이블 탭:

- No
- Table Name

조건문 탭:

- No
- Code Block
- Condition Type
- Condition Text

Excel 파일의 `SQL_ANALYSIS` 시트에는 `SOURCE TABLES`, `CONDITIONS` 두 표가 별도로 생성됩니다.

## 테스트

```powershell
python -m unittest discover -s tests
```
