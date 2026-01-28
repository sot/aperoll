import numpy as np
from astropy.table import Table
from chandra_aca.attitude import calc_att
from cxotime import CxoTime
from PyQt5 import QtCore as QtC
from PyQt5 import QtWidgets as QtW
from Quaternion import Quat

from aperoll.utils import log_exception, logger
from aperoll.widgets.attitude_widget import (
    AttitudeWidget,
    QuatRepresentation,
    hstack,
    vstack,
)
from aperoll.widgets.centroid_table import CentroidTable
from aperoll.widgets.line_edit import LineEdit


class CatalogWidget(QtW.QWidget):
    slot_enabled = QtC.pyqtSignal(int, bool)
    track = QtC.pyqtSignal(bool)
    attitude_updated = QtC.pyqtSignal(Quat)

    def __init__(self):
        super().__init__()

        self.date_edit = LineEdit(self)
        self.date_edit.setReadOnly(True)
        self.attitude_widget = AttitudeWidget(
            self,
            columns={
                QuatRepresentation.EQUATORIAL: 0,
                QuatRepresentation.QUATERNION: 0,
                QuatRepresentation.SUN: 0,
            },
        )
        self.attitude_widget.set_read_only(True)
        self.catalog_widget = CentroidTable(
            columns=["slot", "id", "fid", "yang", "zang", "mag", "enabled"]
        )
        self.catalog_widget.set_read_only(True)
        self.catalog_widget.setMinimumWidth(500)
        self.catalog_widget.setHorizontalScrollBarPolicy(QtC.Qt.ScrollBarAlwaysOff)

        self.track_button = QtW.QPushButton("Start tracking")
        self.track_button.setCheckable(True)
        self.track_button.clicked.connect(self._track)

        date_box = QtW.QGroupBox("Date")
        date_box.setLayout(
            vstack(
                self.date_edit,
            )
        )

        self.starcat_source_edit = QtW.QComboBox(self)
        self.starcat_source_edit.addItems(["Kadi", "Proseco", "Find Attitude"])

        self.centroid_table = CentroidTable(add_enable=False)
        self.centroid_table.setHorizontalScrollBarPolicy(QtC.Qt.ScrollBarAlwaysOff)
        self.centroid_table.setMinimumWidth(100)

        source_box = QtW.QGroupBox("Source")
        source_box.setLayout(
            vstack(
                self.starcat_source_edit,
            )
        )

        att_box = QtW.QGroupBox("Attitude")
        att_box.setLayout(
            vstack(
                self.attitude_widget,
            )
        )

        table_box = QtW.QGroupBox("Catalog")
        table_box.setLayout(
            vstack(
                self.catalog_widget,
            )
        )

        centroid_box = QtW.QGroupBox("Centroids")
        centroid_box.setLayout(
            vstack(
                self.centroid_table,
            )
        )

        layout = QtW.QHBoxLayout()
        layout.addStretch()
        layout.addLayout(
            vstack(
                hstack(date_box, source_box),
                att_box,
                table_box,
                centroid_box,
                hstack(self.track_button, stretch=True),
                stretch=True,
            )
        )
        layout.addStretch()
        self.setLayout(layout)
        self.reset()

        self.tracking = False

        self.catalog_widget.slot_enabled.connect(self.slot_enabled)

    def _track(self, checked):
        text = "Stop" if checked else "Start"
        self.track_button.setText(f"{text} tracking")

    def get_tracking(self):
        return self.track_button.isChecked()

    def set_tracking(self, tracking):
        self._track(tracking)
        self.track_button.setChecked(tracking)

    tracking = property(get_tracking, set_tracking)

    def set_attitude(self, attitude):
        self.attitude_widget.set_attitude(attitude)

    def get_attitude(self):
        return self.attitude_widget.get_attitude()

    attitude = property(get_attitude, set_attitude)

    def set_date(self, date):
        date = CxoTime(date).date if date is not None else ""
        if date != self.date_edit.text():
            self.date_edit.setText(date)

    def get_date(self):
        text = self.date_edit.text()
        if text:
            return CxoTime(self.date_edit.text())

    date = property(get_date, set_date)

    def get_starcat_source(self):
        return self.starcat_source_edit.currentText()

    def set_starcat_source(self, source):
        self.starcat_source_edit.setCurrentText(source)

    starcat_source = property(get_starcat_source, set_starcat_source)

    def reset(self):
        self.set_date(None)
        self.attitude = None
        self.catalog_widget.reset()
        # self.centroid_table.reset()

    def set_catalog(self, catalog):
        self.reset()

        try:
            logger.debug("Setting catalog")

            self.date = catalog.date
            self.attitude = catalog.att

            table = Table()
            table["slot"] = np.arange(8)
            # table["id"] = np.ma.masked_all(8, dtype=int)
            # table["yang"] = np.ma.masked_all(8, dtype=float)
            # table["zang"] = np.ma.masked_all(8, dtype=float)
            # table["mag"] = np.ma.masked_all(8, dtype=float)
            # table["enabled"] = np.zeros(8, dtype=bool)
            # table["fid"] = np.ma.masked_all(8, dtype=bool)
            # table["type"] = np.ma.masked_all(8, dtype="<U3")
            table["id"] = 0
            table["yang"] = 0.0
            table["zang"] = 0.0
            table["mag"] = 0.0
            table["enabled"] = False
            table["fid"] = False
            table["type"] = "   "  # 3 characters

            guides = catalog[np.in1d(catalog["type"], ["GUI", "BOT", "FID"])]
            idx = np.searchsorted(np.arange(8), guides["slot"])
            table["slot"][idx] = guides["slot"]
            table["id"][idx] = guides["id"]
            table["yang"][idx] = guides["yang"]
            table["zang"][idx] = guides["zang"]
            table["mag"][idx] = guides["mag"]
            table["type"][idx] = guides["type"]
            table["enabled"][idx] = guides["type"] != "FID"
            table["fid"][idx] = guides["type"] == "FID"

            self.catalog_widget.set_centroids(table)

            centroids = self.centroid_table.get_centroids().copy()
            centroids["enabled"] = self.catalog_widget.get_centroids()["enabled"]
            self.centroid_table.set_centroids(centroids)

        except Exception as exc:
            log_exception("Error setting catalog", exc)

    def enable_slot(self, slot, enable):
        self.catalog_widget.enable_slot(slot, enable)
        centroids = self.centroid_table.get_centroids().copy()
        centroids["enabled"] = self.catalog_widget.get_centroids()["enabled"]
        self.centroid_table.set_centroids(centroids)

    def set_centroids(self, centroids):
        try:
            if np.any(centroids["IMGNUM"] != np.arange(8)):
                logger.warning("Got centroids that do not match")
                return
            fa_centroids = Table(centroids)
            fa_centroids["enabled"] = self.catalog_widget.get_centroids()["enabled"]
            fa_centroids.rename_columns(
                ["IMGNUM", "YAGS", "ZAGS", "AOACMAG"],
                ["slot", "yang", "zang", "mag"],
            )
            self.centroid_table.set_centroids(fa_centroids)
            self.find_attitude()
        except Exception as exc:
            log_exception("Error setting centroids", exc, level="ERROR")

    def find_attitude(self):
        try:
            if not self.tracking or self.attitude is None:
                return

            sel = self.centroid_table.get_centroids()["enabled"]
            attitude = calc_att(
                self.attitude,
                self.catalog_widget.get_centroids()["yang"][sel],
                self.catalog_widget.get_centroids()["zang"][sel],
                self.centroid_table.get_centroids()["yang"][sel],
                self.centroid_table.get_centroids()["zang"][sel],
            )
            self.attitude_updated.emit(attitude)
        except Exception as exc:
            log_exception("Error finding attitude", exc, level="ERROR")
