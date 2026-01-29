import sys

import numpy as np
import PyQt5.QtCore as QtC
import PyQt5.QtWidgets as QtW

from aperoll.utils import logger
from aperoll.widgets.table_widget import TableWidget

FORMATS = {
    "slot": "{:d}",
    "yang": "{:8.2f}",
    "zang": "{:8.2f}",
    "mag": "{:5.2f}",
}

TYPES = {
    "enable": bool,
    "enabled": bool,
    "id": int,
    "fid": bool,
    "mag": float,
    "slot": int,
    "type": "<U3",
    "yang": float,
    "zang": float,
}


class CentroidTable(TableWidget):
    slot_enabled = QtC.pyqtSignal(int, bool)

    def __init__(self, columns=None, titles=None, add_enable=True):
        rows = 8
        columns = (
            ["slot", "yang", "zang", "mag", "enabled"] if columns is None else columns
        )
        titles = list(columns if titles is None else titles)  # this makes a copy
        if add_enable and "enable" not in columns:
            columns.insert(0, "enable")
            titles.insert(0, "Enable")
        super().__init__(
            rows=rows,
            columns=len(columns),
            column_titles=titles,
        )

        self.format = {col: FORMATS.get(col, "{}") for col in columns}

        self._table = np.zeros(rows, dtype=[(col, TYPES[col]) for col in columns])

        # Set the enabled column to be as narrow as possible
        if "enable" in columns:
            idx = columns.index("enable")
            self._q_table.horizontalHeader().setSectionResizeMode(
                idx, QtW.QHeaderView.ResizeToContents
            )

            for row in range(rows):
                checkbox = QtW.QCheckBox()
                self._q_table.setCellWidget(row, idx, checkbox)
                checkbox.setStyleSheet("margin-left: auto; margin-right: auto;")
                checkbox.stateChanged.connect(
                    lambda state, row=row: self.enable_slot(
                        row, state == QtC.Qt.Checked
                    )
                )

        # set all cell items to empty strings now to make sure the items are initialized
        for row in range(rows):
            for col in range(len(columns)):
                colname = self._table.dtype.names[col]
                if colname == "enable":
                    continue
                self._q_table.setItem(row, col, QtW.QTableWidgetItem(""))

        self._reset_table()

    def set_read_only(self, read_only):
        for row in range(len(self._table)):
            for col in range(len(self._table.dtype.names)):
                item = self._q_table.item(row, col)
                if item is not None:
                    if read_only:
                        item.setFlags(item.flags() ^ QtC.Qt.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() | QtC.Qt.ItemIsEditable)

    def reset(self):
        self._reset_table()
        self._display_table()

    def _reset_table(self):
        self._table[:] = 0
        self._table["slot"] = np.arange(8)

    def set_centroids(self, centroids):
        self._reset_table()
        if not np.all(centroids["slot"] == self._table["slot"]):
            logger.debug(f"Got centroids that do not match: slot={centroids['slot']}")
            return
        if "enable" in self._table.dtype.names:
            self._table["enable"] = centroids["enabled"]
        for col in set(self._table.dtype.names).intersection(centroids.dtype.names):
            self._table[col] = centroids[col]
        self._display_table()

    def get_centroids(self):
        view = self._table.view()
        view.flags.writeable = False
        return view

    def enable_slot(self, slot, enable):
        if self._table["enable"][slot] == enable:
            # nothing to do
            return
        self._table["enable"][slot] = enable
        col = list(self._table.dtype.names).index("enable")
        checkbox = self._q_table.cellWidget(slot, col)
        checkbox.setChecked(enable)
        self.slot_enabled.emit(slot, enable)

    def _display_table(self):
        for row in range(len(self._table)):
            for col in range(len(self._table.dtype)):
                colname = self._table.dtype.names[col]
                item = self._table[row][col]
                if colname == "enable":
                    checkbox = self._q_table.cellWidget(row, col)
                    checkbox.setChecked(bool(item))
                else:
                    self._q_table.item(row, col).setText(
                        self.format[colname].format(item)
                    )


if __name__ == "__main__":
    app = QtW.QApplication(sys.argv)

    centroids = np.array(
        [
            (0, True, -764.98, -1876.88, 7.06),
            (1, True, 2146.43, 31.10, 7.19),
            (2, True, -1819.00, 26.60, 7.19),
            (3, False, 843.05, -1395.72, 7.88),
            (4, False, -673.33, 755.15, 9.06),
            (5, False, -686.73, 2047.40, 9.38),
            (6, False, -682.90, -688.48, 10.31),
            (7, False, -390.85, 1030.92, 9.31),
        ],
        dtype=[
            ("IMGNUM", int),
            ("IMGFID", bool),
            ("YAGS", float),
            ("ZAGS", float),
            ("AOACMAG", float),
        ],
    )

    widget = CentroidTable()
    widget.resize(800, 600)
    widget.set_centroids(centroids)
    widget.show()

    sys.exit(app.exec_())
