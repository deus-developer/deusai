from contextlib import contextmanager
from tempfile import NamedTemporaryFile

from pyexcelerate import Workbook, Style


class ExcelManager:
    def __init__(self):
        self.workbook = Workbook()
        self.sheet = self.workbook.new_sheet('Sheet')

        self._row_idx = 1
        self._column_idx = 1
        self._max_column_idx = 1

    def write_row(self, *values):
        for value in values:
            self.write(value)
        self.next_row()

    def write(self, value):
        try:
            if value is True:
                value = '✅'
            elif value is False:
                value = '❌'
            elif value is None:
                return

            self.sheet.set_cell_value(self.row, self.column, value)
        finally:
            self.column += 1
            if self.column > self._max_column_idx:
                self._max_column_idx = self.column

    def next_row(self):
        self.row += 1
        self.column = 1

    def prev_row(self):
        self.row -= 1

    @property
    def row(self):
        return self._row_idx

    @row.setter
    def row(self, value):
        assert isinstance(value, int) and value > 0, 'Row is not int > 0'
        self._row_idx = value

    @property
    def column(self):
        return self._column_idx

    @column.setter
    def column(self, value):
        assert isinstance(value, int) and value > 0, 'Column is not int > 0'
        self._column_idx = value

    def resize(self):
        style = Style(size=-1)
        for column_idx in range(1, self._max_column_idx + 1):
            self.sheet.set_col_style(column_idx, style)

    @contextmanager
    def save(self, resize: bool = True):
        if resize:
            self.resize()

        with NamedTemporaryFile(suffix='.xlsx') as fh:
            self.workbook.save(fh.name)
            fh.seek(0)
            yield fh
