# from PyQt5 import QtCore as QtC, QtWidgets as QtW, QtGui as QtG
from tempfile import TemporaryDirectory
from pathlib import Path

from PyQt5 import QtWidgets as QtW
from PyQt5 import QtCore as QtC

import PyQt5.QtWebEngineWidgets as QtWe

from .parameters import Parameters
from .star_plot import StarPlot

from Quaternion import Quat
from astropy import units as u

from cxotime import CxoTime

from proseco import get_aca_catalog
from sparkles.core import run_aca_review


class WebPage(QtWe.QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)

    # trick from https://stackoverflow.com/questions/54920726/how-make-any-link-blank-open-in-same-window-using-qwebengine  # noqa
    def createWindow(self, _type):
        page = WebPage(self)
        page.urlChanged.connect(self.on_url_changed)
        return page

    @QtC.pyqtSlot(QtC.QUrl)
    def on_url_changed(self, url):
        page = self.sender()
        self.setUrl(url)
        page.deleteLater()


class MainWindow(QtW.QWidget):
    def __init__(self, opts={}):
        super().__init__()
        opts = {k: opts[k] for k in opts if opts[k] is not None}

        self.web_page = None

        self._tmp_dir = TemporaryDirectory()
        self._dir = Path(self._tmp_dir.name)

        self.plot = StarPlot()
        self.parameters = Parameters(**opts)

        layout = QtW.QHBoxLayout(self)
        layout.addWidget(self.parameters)
        layout.addWidget(self.plot)

        layout.setStretch(0, 1)
        layout.setStretch(1, 4)
        self.setLayout(layout)

        self.parameters.do_it.connect(self._do_it)
        self.plot.attitude_changed.connect(self.parameters.set_ra_dec)

        # try:
        #     self._do_it()
        # except Exception as e:
        #     print(e)
        #     pass

    def closeEvent(self, event):
        if self.web_page is not None:
            del self.web_page
            self.web_page = None
        event.accept()

    def _do_it(self):
        if self.parameters.values:
            obsid = self.parameters.values['obsid']
            ra, dec = self.parameters.values['ra'], self.parameters.values['dec']
            roll = self.parameters.values['roll']
            time = CxoTime(self.parameters.values['date'])

            # aca_attitude = calc_aca_from_targ(
            #     Quat(equatorial=(float(ra / u.deg), float(dec / u.deg), nominal_roll)),
            #     0,
            #     0
            # )
            aca_attitude = Quat(equatorial=(float(ra / u.deg), float(dec / u.deg), roll))
            print('ra, dec, roll =', (float(ra / u.deg), float(dec / u.deg), roll))
            catalog = get_aca_catalog(
                obsid=obsid,
                att=aca_attitude,
                date=time,
                n_fid=self.parameters.values['n_fid'],
                n_guide=self.parameters.values['n_guide'],
                dither_acq=(8, 8),  # standard dither with ACIS
                dither_guide=(8, 8),  # standard dither with ACIS
                t_ccd_acq=self.parameters.values['t_ccd'],
                t_ccd_guide=self.parameters.values['t_ccd'],
                man_angle=0,  # what is a sensible number to use??
                detector=self.parameters.values['instrument'],
                sim_offset=0,  # docs say this is optional, but it does not seem to be
                focus_offset=0,  # docs say this is optional, but it does not seem to be
            )

            run_aca_review(
                'Exploration',
                acars=[catalog.get_review_table()],
                report_dir=self._dir / 'sparkles',
                report_level='all',
                roll_level='none',
            )
            print(f'sparkles report at {self._dir / "sparkles"}')
            try:
                w = QtW.QMainWindow(self)
                w.resize(1400, 1000)
                web = QtWe.QWebEngineView(w)
                w.setCentralWidget(web)
                self.web_page = WebPage()
                web.setPage(self.web_page)
                url = self._dir / 'sparkles' / 'index.html'
                web.load(QtC.QUrl(f'file://{url}'))
                web.show()
                w.show()
            except Exception as e:
                print(e)

            self.plot.set_catalog(catalog)
