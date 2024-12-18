import agasc
import numpy as np
import tables
from astropy import units as u
from astropy.table import Table, vstack
from chandra_aca.transform import (
    radec_to_yagzag,
    yagzag_to_pixels,
)
from cxotime import CxoTime
from PyQt5 import QtCore as QtC
from PyQt5 import QtGui as QtG
from PyQt5 import QtWidgets as QtW
from Quaternion import Quat

from aperoll import utils
from aperoll.star_field_items import Catalog, Star


class StarView(QtW.QGraphicsView):
    include_star = QtC.pyqtSignal(int, str, object)

    def __init__(self, scene=None):
        super().__init__(scene)
        self.setViewport(QtW.QOpenGLWidget())
        # mouseTracking is set so we can show tooltips
        self.setMouseTracking(True)
        # Antialiasing could be disabled if it affects performance
        self.setRenderHint(QtG.QPainter.Antialiasing)

        self._start = None
        self._rotating = False
        self._moving = False

        self._draw_frame = True

    def _get_draw_frame(self):
        return self._draw_frame

    def _set_draw_frame(self, draw):
        if draw != self._draw_frame:
            self._draw_frame = draw
            self.viewport().update()

    draw_frame = property(_get_draw_frame, _set_draw_frame)

    def mouseMoveEvent(self, event):
        pos = event.pos()

        items = [item for item in self.items(event.pos()) if isinstance(item, Star)]
        if items:
            global_pos = event.globalPos()
            # supposedly, the following should cause the tooltip to stay for a long time
            # but it is the same
            # QtW.QToolTip.showText(global_pos, items[0].text(), self, QtC.QRect(), 1000000000)
            QtW.QToolTip.showText(global_pos, items[0].text())

        if self._start is None:
            return

        if pos != self._start:
            if event.modifiers() == QtC.Qt.ShiftModifier:
                self._rotating = True
            else:
                self._moving = True

        if self._moving or self._rotating:
            end_pos = self.mapToScene(pos)
            start_pos = self.mapToScene(self._start)
            if self._moving:
                dx, dy = end_pos.x() - start_pos.x(), end_pos.y() - start_pos.y()
                self.scene().shift_scene(dx, dy)
            elif self._rotating:
                center = self.mapToScene(self.viewport().rect().center())
                x1 = start_pos.x() - center.x()
                y1 = start_pos.y() - center.y()
                x2 = end_pos.x() - center.x()
                y2 = end_pos.y() - center.y()
                r1 = np.sqrt(x1**2 + y1**2)
                r2 = np.sqrt(x2**2 + y2**2)
                angle = np.rad2deg(np.arcsin((x1 * y2 - x2 * y1) / (r1 * r2)))
                self.scene().rotate_scene(angle, center)

            self._start = pos

    def mouseReleaseEvent(self, event):
        if event.button() == QtC.Qt.LeftButton:
            self._start = None

    def mousePressEvent(self, event):
        if event.button() == QtC.Qt.LeftButton:
            self._moving = False
            self._rotating = False
            self._start = event.pos()

    def wheelEvent(self, event):
        scale = 1 + 0.5 * event.angleDelta().y() / 360
        if scale < 0:
            # this has happened when you scroll fast, but I do not know why.
            # It makes no sense anyway.
            return
        self.scale(scale, scale)
        self.set_visibility()
        self.set_item_scale()
        self.viewport().update()

    def drawForeground(self, painter, _rect):
        if not self._draw_frame:
            return

        # I want to use antialising for these lines regardless of what is set for the scene,
        # because they are large and otherwise look hideous. It will be reset at the end.
        anti_aliasing_set = painter.testRenderHint(QtG.QPainter.Antialiasing)
        painter.setRenderHint(QtG.QPainter.Antialiasing, True)

        black_pen = QtG.QPen()
        black_pen.setCosmetic(True)
        black_pen.setWidth(1)
        center = QtC.QPoint(self.viewport().width() // 2, self.viewport().height() // 2)
        center = self.mapToScene(center)

        # The following draws the edges of the CCD
        frame = utils.get_camera_fov_frame()

        row, col = "row", "col"
        painter.setPen(black_pen)
        for i in range(len(frame["edge_1"][row]) - 1):
            painter.drawLine(
                QtC.QPointF(frame["edge_1"][row][i], frame["edge_1"][col][i]),
                QtC.QPointF(frame["edge_1"][row][i + 1], frame["edge_1"][col][i + 1]),
            )
        for i in range(len(frame["edge_2"][row]) - 1):
            painter.drawLine(
                QtC.QPointF(frame["edge_2"][row][i], frame["edge_2"][col][i]),
                QtC.QPointF(frame["edge_2"][row][i + 1], frame["edge_2"][col][i + 1]),
            )

        magenta_pen = QtG.QPen(QtG.QColor("magenta"))
        magenta_pen.setCosmetic(True)
        magenta_pen.setWidth(1)
        painter.setPen(magenta_pen)
        for i in range(len(frame["cross_2"][row]) - 1):
            painter.drawLine(
                QtC.QPointF(frame["cross_2"][row][i], frame["cross_2"][col][i]),
                QtC.QPointF(frame["cross_2"][row][i + 1], frame["cross_2"][col][i + 1]),
            )
        for i in range(len(frame["cross_1"][row]) - 1):
            painter.drawLine(
                QtC.QPointF(frame["cross_1"][row][i], frame["cross_1"][col][i]),
                QtC.QPointF(frame["cross_1"][row][i + 1], frame["cross_1"][col][i + 1]),
            )
        painter.setRenderHint(QtG.QPainter.Antialiasing, anti_aliasing_set)

    def contextMenuEvent(self, event):
        items = [item for item in self.items(event.pos()) if isinstance(item, Star)]
        if not items:
            return
        item = items[0]

        menu = QtW.QMenu()

        incl_action = QtW.QAction("include acq", menu, checkable=True)
        incl_action.setChecked(item.included["acq"] is True)
        menu.addAction(incl_action)

        excl_action = QtW.QAction("exclude acq", menu, checkable=True)
        excl_action.setChecked(item.included["acq"] is False)
        menu.addAction(excl_action)

        incl_action = QtW.QAction("include guide", menu, checkable=True)
        incl_action.setChecked(item.included["guide"] is True)
        menu.addAction(incl_action)

        excl_action = QtW.QAction("exclude guide", menu, checkable=True)
        excl_action.setChecked(item.included["guide"] is False)
        menu.addAction(excl_action)

        result = menu.exec_(event.globalPos())
        if result is not None:
            action, action_type = result.text().split()
            if items:
                if action == "include":
                    item.included[action_type] = True if result.isChecked() else None
                elif action == "exclude":
                    item.included[action_type] = False if result.isChecked() else None
                self.include_star.emit(
                    item.star["AGASC_ID"], action_type, item.included[action_type]
                )
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() == -1 and event.oldSize().height() == -1:
            # this fits the viewport to a circle of radius 7200 arcsec plus some margin
            # (this assumes the scene is in pixels, where the diagonal of the CCD is ~1400 pixels)
            scale = min(event.size().height(), event.size().width()) / 2000
            self.scale(scale, scale)

    def set_visibility(self):
        r_threshold = [2, 4, 6, 8, 10, 11, 15]
        mags = [14, 11, 10.3, 9, 9.5, 8, 7, 3]

        if self.scene()._stars is not None:
            tl = self.mapToScene(self.viewport().rect().topLeft())
            br = self.mapToScene(self.viewport().rect().bottomRight())

            side = max(np.abs(tl.x() - br.x()), np.abs(tl.y() - br.y()))
            radius = 1.5 * (side / 2) * 5 / 3600  # 5 arcsec per pixel, radius in degree

            self.draw_frame = radius < 6

            r = agasc.sphere_dist(
                self.scene().attitude.ra,
                self.scene().attitude.dec,
                self.scene()._stars["RA_PMCORR"],
                self.scene()._stars["DEC_PMCORR"],
            )
            max_mag = mags[np.digitize(radius, r_threshold)]
            hide = (r > radius) | (self.scene()._stars["MAG_ACA"] > max_mag)
            for idx, item in enumerate(self.scene()._stars):
                # note that the coordinate system is (row, -col), which is (-yag, -zag)
                if hide[idx]:
                    item["graphic_item"].hide()
                else:
                    item["graphic_item"].show()

    def set_item_scale(self):
        if self.scene()._stars is not None:
            # when zooming out (scaling < 1), the graphic items should not get too small
            # to control this, we choose a scale below which the item sizes should not decrease
            # so the items are scaled by the inverse to compensate.
            # this breaks the view/scene separation, but it works for us.
            threshold = 0.15
            new_scale = np.sqrt(self.transform().determinant())
            for item in self.scene()._stars["graphic_item"]:
                item.setScale(threshold / new_scale if new_scale < threshold else 1)

    def scale(self, sx, sy):
        # refusing to scale beyond 15 degrees
        tl = self.mapToScene(self.viewport().rect().topLeft())
        br = self.mapToScene(self.viewport().rect().bottomRight())
        width = np.abs(tl.x() - br.x())
        height = np.abs(tl.y() - br.y())
        if (width * 5 / 3600 / sx >= 15) or (height * 5 / 3600 / sy >= 15):
            return

        # scale
        super().scale(sx, sy)

        # now tell the scene the new radius for updating stars
        tl = self.mapToScene(self.viewport().rect().topLeft())
        br = self.mapToScene(self.viewport().rect().bottomRight())

        side = max(np.abs(tl.x() - br.x()), np.abs(tl.y() - br.y())) / 2
        radius = 1.5 * side * 5 / 3600  # 5 arcsec per pixel, radius in degree
        self.scene().update_stars(radius=radius)


class StarField(QtW.QGraphicsScene):
    attitude_changed = QtC.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._attitude = None
        self._time = None
        self._stars = None
        self._catalog = None

        self._healpix_indices = set()
        self._update_radius = 2

    def update_stars(self, radius=None):
        if radius is not None:
            self._update_radius = radius

        if self._attitude is None or self._time is None:
            return

        agasc_file = agasc.paths.default_agasc_file()

        # Table of healpix, idx0, idx1 where idx is the index into main AGASC data table
        healpix_index_map, nside = agasc.healpix.get_healpix_info(agasc_file)
        hp = agasc.healpix.get_healpix(nside)

        # We include stars in healpix pixels intersecting a cone with the given radius
        healpix_indices = set(
            hp.cone_search_lonlat(
                self._attitude.ra * u.deg,
                self._attitude.dec * u.deg,
                radius=self._update_radius * u.deg,
            )
        )
        add_indices = list(set(healpix_indices) - self._healpix_indices)

        # and we only remove them when they fall out of a larger cone
        # (to allow for panning without adding and dro[[ing repeatedly)
        healpix_indices = set(
            hp.cone_search_lonlat(
                self.attitude.ra * u.deg,
                self.attitude.dec * u.deg,
                radius=(self._update_radius * 1.5) * u.deg,
            )
        )
        remove_indices = list(self._healpix_indices - set(healpix_indices))

        # remove stars
        if self._stars is not None:
            for star in self._stars[
                np.in1d(self._stars["healpix_idx"], remove_indices)
            ]:
                self.removeItem(star["graphic_item"])
            self._stars = self._stars[
                ~np.in1d(self._stars["healpix_idx"], remove_indices)
            ]

        # add stars
        if add_indices:
            stars_list = []
            with tables.open_file(agasc_file) as h5:
                for healpix_index in add_indices:
                    idx0, idx1 = healpix_index_map[healpix_index]
                    stars = Table(agasc.read_h5_table(h5, row0=idx0, row1=idx1))
                    stars["healpix_idx"] = healpix_index
                    stars_list.append(stars)

            stars = Table(np.concatenate(stars_list))
            agasc.add_pmcorr_columns(stars, self._time)

            stars["graphic_item"] = [Star(star, highlight=False) for star in stars]
            for item in stars["graphic_item"]:
                # item.setScale(self._scale)
                self.addItem(item)

            if self._stars is None:
                self._stars = stars
            else:
                self._stars = vstack([self._stars, stars])

        # reset current indices
        self._healpix_indices = set(np.unique(self._stars["healpix_idx"]))

        self.set_star_positions()

    def add_test_stars(self):
        # this draws two circles, a blue one at (0, 0) and a red one at the CCD origin,
        # which corresponds to the ACA pointing. This is useful for debugging.
        w = 6
        self.addEllipse(-w / 2, -w / 2, w, w, QtG.QPen(QtG.QColor("blue")))
        self.addEllipse(
            utils.CCD_ORIGIN[0] - w / 2,
            -utils.CCD_ORIGIN[1] - w / 2,
            w,
            w,
            QtG.QPen(QtG.QColor("red")),
        )

    def shift_scene(self, dx, dy):
        """
        Apply an active transformation on the scene, shifting the items the given number of pixels.

        The shift is a linear transformation in pixel coordinates, made on the origin of the CCD
        assuming a constant roll.

        After the shift, an item initially at (0, 0) should be close to (dx, dy). An item initially
        at (x, y) will not be as close to (x + dx, y + dy).
        """
        if self._attitude is None:
            return
        # transformation assuming 5 arcsec per pixel
        dq = Quat(equatorial=[5 * dx / 3600, 5 * dy / 3600, 0])
        # this does roughly the same:
        # yag, zag = pixels_to_yagzag(-dx, dy)
        # dq = Quat(equatorial=[(yag - YZ_ORIGIN[0]) / 3600, (zag - YZ_ORIGIN[1]) / 3600, 0])
        self.set_attitude(self._attitude * dq)

    def rotate_scene(self, angle, around=None):
        """
        Apply an active transformation on the scene, rotating the items around the given point.
        """
        if self._attitude is None:
            return

        dq = Quat(equatorial=[0, 0, -angle])
        self.set_attitude(self._attitude * dq)

    def set_star_positions(self):
        if self._stars is not None and self._attitude is not None:
            # The calculation of row/col is done here so it can be vectorized
            # if done for each item, it is much slower.
            self._stars["yang"], self._stars["zang"] = radec_to_yagzag(
                self._stars["RA_PMCORR"], self._stars["DEC_PMCORR"], self._attitude
            )
            self._stars["row"], self._stars["col"] = yagzag_to_pixels(
                self._stars["yang"], self._stars["zang"], allow_bad=True
            )
            for item in self._stars:
                # note that the coordinate system is (row, -col), which is (-yag, -zag)
                item["graphic_item"].setPos(item["row"], -item["col"])

    def set_time(self, time):
        if time != self._time:
            self._time = time
            self.update_stars()

    def get_time(self):
        return self._time

    time = property(get_time, set_time)

    def set_attitude(self, attitude):
        """
        Set the attitude of the scene, rotating the items to the given attitude.
        """

        if attitude != self._attitude:
            if self._catalog is not None:
                self._catalog.set_pos_for_attitude(attitude)
            self._attitude = attitude
            self.update_stars()
            self.attitude_changed.emit()

    def get_attitude(self):
        return self._attitude

    attitude = property(get_attitude, set_attitude)

    def add_catalog(self, starcat):
        if self._catalog is not None:
            self.removeItem(self._catalog)

        self._catalog = Catalog(starcat)
        self.addItem(self._catalog)


class StarPlot(QtW.QWidget):
    attitude_changed = QtC.pyqtSignal(float, float, float)
    include_star = QtC.pyqtSignal(int, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtW.QVBoxLayout(self)
        self.setLayout(layout)

        self._origin = [6.08840495576943, 4.92618563916467]

        self.scene = StarField(self)
        self.scene.setSceneRect(-100, -100, 200, 200)

        self.view = StarView(self.scene)

        self.layout().addWidget(self.view)

        self.stars = None
        self._time = None
        self._highlight = []
        self._catalog = None

        self.scene.attitude_changed.connect(self._attitude_changed)
        self.scene.attitude_changed.connect(self.view.set_visibility)
        self.scene.attitude_changed.connect(self.view.set_item_scale)
        self.scene.changed.connect(self.view.set_visibility)

        self.view.include_star.connect(self.include_star)

    def _attitude_changed(self):
        if self.scene.attitude is not None:
            self.attitude_changed.emit(
                self.scene.attitude.ra,
                self.scene.attitude.dec,
                self.scene.attitude.roll,
            )

    def set_base_attitude(self, q):
        """
        Sets the base attitude

        The base attitude is the attitude corresponding to the origin of the scene.
        """
        self.scene.set_attitude(q)

    def set_time(self, t):
        self._time = CxoTime(t)
        self.scene.time = self._time

    def highlight(self, agasc_ids):
        self._highlight = agasc_ids

    def set_catalog(self, catalog):
        self.set_time(catalog.date)
        self._catalog = catalog
        self.show_catalog()

    def show_catalog(self):
        if self._catalog is not None:
            self.scene.add_catalog(self._catalog)


def main():
    from aperoll.widgets.parameters import get_default_parameters

    params = get_default_parameters()

    app = QtW.QApplication([])
    w = StarPlot()
    w.set_base_attitude(params["attitude"])
    w.set_time(params["date"])
    w.resize(1500, 1000)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
