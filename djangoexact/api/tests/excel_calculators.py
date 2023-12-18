import xlsxwriter as xw

class GrasslandModule:

    def __init__(self):
        self.workbook = xw.Workbook("EX-ACT_V9.4_open.xlsb")
        self.worksheet = self.workbook.worksheets()
        self.worksheet = self.workbook[self.workbook.index("4.Grassland")]