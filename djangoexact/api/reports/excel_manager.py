"""ExcelFileManager – handles in-memory Excel workbook lifecycle."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from io import BytesIO

import openpyxl as pxl
import xlsxwriter


class ExcelFileManager:
    def __init__(self):
        self.excel_file = BytesIO()
        self._create_initial_excel()

    def _create_initial_excel(self):
        workbook = xlsxwriter.Workbook(self.excel_file, {"in_memory": True})
        workbook.add_worksheet("Results")
        workbook.add_worksheet("Metadata")
        additional_indicators_worksheet = workbook.add_worksheet("Additional Indicators")
        workbook.add_worksheet("Shadow Price of Carbon")
        workbook.add_worksheet("Inventory")
        additional_indicators_worksheet.hide()
        workbook.close()
        self.excel_file.seek(0)

    def get_workbook(self) -> pxl.Workbook:
        return pxl.load_workbook(self.excel_file)

    def save_workbook(self, workbook: pxl.Workbook) -> None:
        self.excel_file = BytesIO()
        workbook.save(self.excel_file)
        self.excel_file.seek(0)

        if os.environ.get("EXACT_SAVE_REPORTS_TO_FILE"):
            reports_dir = os.path.join(tempfile.gettempdir(), "reports")
            os.makedirs(reports_dir, exist_ok=True)
            filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
            filepath = os.path.join(reports_dir, filename)
            with open(filepath, "wb") as f:
                f.write(self.excel_file.getvalue())
            self.saved_report_path = filepath

    def get_excel_bytes(self) -> bytes:
        self.excel_file.seek(0)
        return self.excel_file.getvalue()
