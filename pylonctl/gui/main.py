import logging
import threading

from PyQt5 import Qt, uic
import pyqtgraph
import pkg_resources

from pypylon import genicam
from pylonctl.camera import Acquisition


UI = pkg_resources.resource_filename("pylonctl.gui", "gui.ui")


def acq_loop(camera, source, nb_frames, exposure, latency, roi, binning):
    logging.info("starting acquisition task...")
    logging.info("  start preparing camera...")
    try:
        with Acquisition(camera, nb_frames, exposure, latency, roi, binning) as acq:
            logging.info("  finished preparing camera")
            logging.info("  start acquisition...")
            acq.start()
            for frame in acq:
                source.frame.emit(frame)
            logging.info("  finished acquisition")
    except Exception as error:
        logging.error("Error while acquiring: %r", error)
    finally:
        logging.info("finished acquisition task...")


def load_gui(widget=None, camera=None, source=None):
    if widget is None:
        widget = Qt.QMainWindow()

    def on_update_freq(v):
        exposure = widget.exposure_time.value()
        latency = widget.latency.value()
        period = exposure + latency
        freq = float("inf") if not period else 1 / period
        widget.freq_value.setText("{:.3f} Hz".format(freq))

    def on_reset_roi():
        widget.x_spin.setValue(0)
        widget.y_spin.setValue(0)
        widget.w_spin.setValue(widget.w_spin.maximum())
        widget.h_spin.setValue(widget.h_spin.maximum())

    def on_start():
        nb_frames = widget.nb_frames.value()
        exposure = widget.exposure_time.value()
        latency = widget.latency.value()
        roi = (
            widget.x_spin.value(),
            widget.y_spin.value(),
            widget.w_spin.value(),
            widget.h_spin.value(),
        )
        if widget.h_bin_spin.isEnabled():
            binning = (widget.h_bin_spin.value(), widget.v_bin_spin.value())
        else:
            binning = None
        widget.task = threading.Thread(
            target=acq_loop,
            args=(
                widget.camera,
                widget.source,
                nb_frames,
                exposure,
                latency,
                roi,
                binning,
            ),
        )
        widget.task.daemon = True
        widget.task.start()

    def on_stop():
        camera.StopGrabbing()
        if widget.task:
            widget.task.join()

    widget.on_update_freq = on_update_freq
    widget.on_reset_roi = on_reset_roi
    widget.on_start = on_start
    widget.on_stop = on_stop

    def on_frame(frame):
        try:
            if frame.GrabSucceeded():
                widget.img.setImage(frame.Array)
        except Exception:
            pass

    uic.loadUi(UI, baseinstance=widget)

    widget.source = QFrameSource()
    widget.vb = pyqtgraph.ViewBox()
    widget.canvas.setCentralItem(widget.vb)
    widget.img = pyqtgraph.ImageItem()
    widget.vb.addItem(widget.img)

    widget.source.frame.connect(on_frame)
    widget.camera = camera

    if camera:
        widget.setWindowTitle(
            "{} - {}".format(widget.windowTitle(), camera.device_info.GetFullName())
        )
    widget.nb_frames.setValue(10)
    widget.exposure_time.setValue(0.01)
    widget.latency.setValue(0.1 - widget.exposure_time.value())

    widget.x_spin.setValue(camera.OffsetX.Value)
    widget.y_spin.setValue(camera.OffsetY.Value)
    widget.w_spin.setValue(camera.Width.Value)
    widget.h_spin.setValue(camera.Height.Value)
    try:
        widget.h_bin_spin.setValue(camera.BinningHorizontal.Value)
        widget.v_bin_spin.setValue(camera.BinningVertical.Value)
    except genicam.LogicalErrorException:
        widget.h_bin_spin.setEnabled(False)
        widget.v_bin_spin.setEnabled(False)

    return widget


class QFrameSource(Qt.QObject):

    frame = Qt.pyqtSignal(object)


class GUI(Qt.QMainWindow):
    def __init__(self, camera=None, parent=None):
        super().__init__(parent)
        load_gui(self, camera)


def main(camera):
    app = Qt.QApplication([])
    with camera:
        gui = GUI(camera)
        gui.show()
        app.exec_()
