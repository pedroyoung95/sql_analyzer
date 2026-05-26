from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sql_analyze_app.models.analysis_result import AnalysisResult
from sql_analyze_app.models.source_table_result import SourceTableResult
from sql_analyze_app.services.excel_export_service import exportResultsToExcel
from sql_analyze_app.services.sql_analysis_service import analyzeSourceTables, analyzeSql, loadSqlFile


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[AnalysisResult] = []
        self.sourceTables: list[SourceTableResult] = []
        self.setWindowTitle("SQL 조건 분석기")
        self.resize(1120, 760)
        self._buildUi()

    def _buildUi(self) -> None:
        centralWidget = QWidget()
        rootLayout = QVBoxLayout(centralWidget)
        rootLayout.setContentsMargins(16, 16, 16, 16)
        rootLayout.setSpacing(10)

        title = QLabel("SQL 조건 분석기")
        title.setObjectName("titleLabel")
        rootLayout.addWidget(title)

        self.sqlInput = QTextEdit()
        self.sqlInput.setPlaceholderText("SQL 쿼리문을 붙여넣거나 .sql 파일을 업로드하세요.")
        self.sqlInput.setAcceptRichText(False)
        rootLayout.addWidget(self.sqlInput, 3)

        buttonLayout = QHBoxLayout()
        self.uploadButton = QPushButton("SQL 파일 업로드")
        self.analyzeButton = QPushButton("분석 실행")
        self.exportButton = QPushButton("Excel 다운로드")
        self.resetButton = QPushButton("초기화")
        self.includeEmptyCheckBox = QCheckBox("조건문 없는 테이블도 표시")

        buttonLayout.addWidget(self.uploadButton)
        buttonLayout.addWidget(self.analyzeButton)
        buttonLayout.addWidget(self.exportButton)
        buttonLayout.addWidget(self.resetButton)
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(self.includeEmptyCheckBox)
        rootLayout.addLayout(buttonLayout)

        self.resultTabs = QTabWidget()
        self.sourceTableWidget = self._createTable(["No", "Table Name"])
        self.conditionTableWidget = self._createTable(["No", "Code Block", "Condition Type", "Condition Text"])
        self.resultTabs.addTab(self.sourceTableWidget, "소스 테이블")
        self.resultTabs.addTab(self.conditionTableWidget, "조건문")
        rootLayout.addWidget(self.resultTabs, 2)

        self.setCentralWidget(centralWidget)
        self._connectSignals()
        self._applyStyle()

    def _connectSignals(self) -> None:
        self.uploadButton.clicked.connect(self.handleUploadSqlFile)
        self.analyzeButton.clicked.connect(self.handleAnalyzeSql)
        self.exportButton.clicked.connect(self.handleExportExcel)
        self.resetButton.clicked.connect(self.handleReset)

    def handleUploadSqlFile(self) -> None:
        filePath, _ = QFileDialog.getOpenFileName(self, "SQL 파일 선택", "", "SQL Files (*.sql);;All Files (*.*)")
        if not filePath:
            return

        try:
            sqlText = loadSqlFile(filePath)
            self.sqlInput.setPlainText(sqlText)
        except Exception as error:
            self._showError(str(error))

    def handleAnalyzeSql(self) -> None:
        try:
            sqlText = self.sqlInput.toPlainText()
            self.sourceTables = analyzeSourceTables(sqlText)
            self.results = analyzeSql(
                sqlText,
                self.includeEmptyCheckBox.isChecked(),
            )
            self._renderResults()
        except Exception as error:
            self.results = []
            self._renderResults()
            self._showError(str(error))

    def handleExportExcel(self) -> None:
        if not self.results and not self.sourceTables:
            self._showError("저장할 분석 결과가 없습니다. 먼저 분석을 실행해주세요.")
            return

        filePath, _ = QFileDialog.getSaveFileName(self, "Excel 파일 저장", "sql_analysis.xlsx", "Excel Files (*.xlsx)")
        if not filePath:
            return

        try:
            exportResultsToExcel(self.results, filePath, self.sourceTables)
            QMessageBox.information(self, "저장 완료", "Excel 파일 저장이 완료되었습니다.")
        except Exception as error:
            self._showError(str(error))

    def handleReset(self) -> None:
        self.sqlInput.clear()
        self.results = []
        self.sourceTables = []
        self._renderResults()

    def _renderResults(self) -> None:
        self._renderSourceTables()
        self._renderConditions()

    def _renderConditions(self) -> None:
        self.conditionTableWidget.setRowCount(len(self.results))
        for rowIndex, result in enumerate(self.results):
            values = [rowIndex + 1, result.codeBlock, result.conditionType, result.conditionText]
            for columnIndex, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if columnIndex in (0, 1, 2):
                    item.setTextAlignment(Qt.AlignCenter)
                self.conditionTableWidget.setItem(rowIndex, columnIndex, item)
        self.conditionTableWidget.resizeRowsToContents()

    def _renderSourceTables(self) -> None:
        self.sourceTableWidget.setRowCount(len(self.sourceTables))
        for rowIndex, sourceTable in enumerate(self.sourceTables):
            values = [sourceTable.no, sourceTable.tableName]
            for columnIndex, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if columnIndex == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.sourceTableWidget.setItem(rowIndex, columnIndex, item)
        self.sourceTableWidget.resizeRowsToContents()

    def _createTable(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().setVisible(False)
        for columnIndex in range(len(headers) - 1):
            table.horizontalHeader().setSectionResizeMode(columnIndex, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.Stretch)
        return table

    def _showError(self, message: str) -> None:
        QMessageBox.warning(self, "알림", message)

    def _applyStyle(self) -> None:
        QApplication.instance().setStyleSheet(
            """
            QMainWindow {
                background: #f7f8fa;
            }
            QLabel#titleLabel {
                color: #111827;
                font-size: 22px;
                font-weight: 700;
            }
            QTextEdit, QTableWidget {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                color: #111827;
                font-family: Consolas, Malgun Gothic;
                font-size: 12px;
            }
            QTabWidget::pane {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 0 6px 6px 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: #e5e7eb;
                color: #111827;
                min-width: 112px;
                min-height: 32px;
                padding: 6px 16px;
                margin-right: 3px;
                border: 1px solid #cbd5e1;
                border-bottom: 0;
                border-radius: 6px 6px 0 0;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #111827;
                border-top: 4px solid #2563eb;
                padding-top: 3px;
                font-weight: 800;
            }
            QTabBar::tab:!selected {
                background: #f3f4f6;
                color: #374151;
            }
            QTabBar::tab:hover {
                background: #ffffff;
                color: #111827;
            }
            QHeaderView::section {
                background: #1f2937;
                color: #ffffff;
                padding: 7px;
                border: 0;
                font-weight: 700;
            }
            QPushButton {
                background: #2563eb;
                border: 0;
                border-radius: 5px;
                color: #ffffff;
                min-height: 32px;
                padding: 0 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QCheckBox {
                color: #111827;
                spacing: 6px;
            }
            """
        )
