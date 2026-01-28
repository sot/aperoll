import sys

import PyQt5.QtWidgets as QtW


class TableWidget(QtW.QWidget):
    def __init__(self, rows, columns, column_titles, parent=None):
        super().__init__(parent)

        self._q_table = QtW.QTableWidget(rows, columns, self)
        self._q_table.setHorizontalHeaderLabels(column_titles)

        layout = QtW.QVBoxLayout()
        layout.addWidget(self._q_table)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        layout.setSpacing(0)  # Remove spacing
        self.setLayout(layout)

        self._q_table.horizontalHeader().setStretchLastSection(True)
        self._q_table.horizontalHeader().setSectionResizeMode(QtW.QHeaderView.Stretch)
        self._q_table.verticalHeader().setSectionResizeMode(QtW.QHeaderView.Stretch)

        # Hide the headers (row/column numbers)
        self._q_table.verticalHeader().setVisible(False)
        # self._q_table.horizontalHeader().setVisible(False)

        # Calculate and set the minimum size
        self.setMinimumSize(*self.calculate_minimum_size())

    def calculate_minimum_size(self):
        width = self._q_table.verticalHeader().width()
        height = self._q_table.horizontalHeader().height()

        for col in range(self._q_table.columnCount()):
            width += self._q_table.columnWidth(col)

        for row in range(self._q_table.rowCount()):
            height += self._q_table.rowHeight(row)

        return width, height

    def resizeEvent(self, event):
        self._q_table.resize(self.size())
        super().resizeEvent(event)

    def setHorizontalScrollBarPolicy(self, policy):
        self._q_table.setHorizontalScrollBarPolicy(policy)


if __name__ == "__main__":
    app = QtW.QApplication(sys.argv)

    rows = 10
    columns = 5
    column_titles = ["Column 1", "Column 2", "Column 3", "Column 4", "Column 5"]

    widget = TableWidget(rows, columns, column_titles)
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec_())
