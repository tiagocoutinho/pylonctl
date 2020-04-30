import logging
import threading

from PyQt5 import Qt, uic
import pyqtgraph
import pkg_resources

from pylonctl.camera import Camera, iacquire


UI = pkg_resources.resource_filename('pylonctl.gui', 'gui.ui')


def acq_loop(camera, source, nb_frames, exposure, latency):
    logging.info('starting acquisition task...')
    for frame in iacquire(camera, nb_frames, exposure, latency):
        source.frame.emit(frame)
    logging.info('finished acquisition task...')


def load_gui(widget=None, camera=None, source=None):
    if widget is None:
        widget = Qt.QMainWindow()

    def update_freq(v):
        exposure = widget.exposure_time.value()
        latency = widget.latency.value()
        freq = 1 / (exposure + latency)
        widget.freq_value.setText('{:.3f} Hz'.format(freq))
    widget.update_freq = update_freq

    uic.loadUi(UI, baseinstance=widget)

    widget.source = QFrameSource()
    widget.vb = pyqtgraph.ViewBox()
    widget.canvas.setCentralItem(widget.vb)
    widget.img = pyqtgraph.ImageItem()
    widget.vb.addItem(widget.img)

    def on_start():
        nb_frames = widget.nb_frames.value()
        exposure = widget.exposure_time.value()
        latency = widget.latency.value()
        widget.task = threading.Thread(
            target=acq_loop, args=(widget.camera, widget.source,
                                   nb_frames, exposure, latency))
        widget.task.daemon = True
        widget.task.start()

    def on_stop():
        camera.StopGrabbing()
        if widget.task:
            widget.task.join()
        
    def on_frame(frame):
        try:
            if frame.GrabSucceeded():
                print(frame.Array)
                widget.img.setImage(frame.Array)
        except:
            pass

    widget.start_button.clicked.connect(on_start)
    widget.stop_button.clicked.connect(on_stop)
    widget.source.frame.connect(on_frame)
    widget.camera = camera

    if camera:
        widget.setWindowTitle(
            '{} - {}'.format(
                widget.windowTitle(), camera.device_info.GetFullName()))
    widget.nb_frames.setValue(10)
    widget.exposure_time.setValue(0.1)
    widget.latency.setValue(0.9)
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
