import math
import logging
import pathlib
import functools
import threading
import contextlib

from PyQt5 import Qt, uic
import pkg_resources
import pyqtgraph

from pylonctl.camera import Camera, Configuration, Acquisition
from .camera_form import CameraForm


UI = pkg_resources.resource_filename("pylonctl.gui", "gui.ui")


def iter_acq(acq):
    logging.info("starting acquisition task...")
    logging.info("  start preparing camera...")
    try:
        with acq:
            logging.info("  finished preparing camera")
            logging.info("  start acquisition...")
            acq.start()
            yield from acq
            logging.info("  finished acquisition")
    except Exception as error:
        logging.error("Error while acquiring: %r", error)
    finally:
        logging.info("finished acquisition task...")


def iter_frames(acq):
    for frame in iter_acq(acq):
        try:
            if frame.GrabSucceeded():
                yield frame.Array
        except Exception as error:
            logging.error("frame error %r", error)
        finally:
            frame.Release()


class QCamera(Qt.QObject):

    newFrame = Qt.pyqtSignal(object)
    newProfileX = Qt.pyqtSignal(object)
    newProfileY = Qt.pyqtSignal(object)

    def __init__(self, camera, form):
        super().__init__()
        self.camera = camera
        self.form = form
        form.start_button.clicked.connect(self.on_start)
        form.stop_button.clicked.connect(self.on_stop)
        self.task = None

    def _acq_loop(self, acq, prepared_event, start_trigger):
        acq.prepare()
        prepared_event.set()
        start_trigger.wait()
        for frame in iter_frames(acq):
            self.newFrame.emit(frame)
            self.newProfileX.emit(frame.sum(0))
            self.newProfileY.emit(frame.sum(1))

    def prepare(self, data):
        logging.info("on start")
        nb_frames = data["nb_frames"]
        exposure = data["exposure_time"]
        latency = data["latency"]
        roi = data["roi"]
        binning = data["binning"]
        if binning is None:
            binning = (1, 1)
        acq = Acquisition(self.camera, nb_frames, exposure, latency, roi, binning)
        prepared_event = threading.Event()
        start_trigger = threading.Event()
        self.task = threading.Thread(
            target=self._acq_loop,
            args=(acq, prepared_event, start_trigger)
        )
        self.task.daemon = True
        self.task.prepared_event = prepared_event
        self.task.start_trigger = start_trigger
        self.task.start()
        return self.task

    def on_start(self):
        data = self.form.get_data()
        task = self.prepare(data)
        task.prepared_event.wait()
        task.start_trigger.set()

    def on_stop(self):
        self.camera.StopGrabbing()
        if self.task:
            self.task.join()
            self.task = None


def load_config(filename):
    path = pathlib.Path(filename)
    if not path.exists():
        raise ValueError('configuration file does not exist')
    ext = path.suffix
    if ext.endswith('toml'):
        from toml import load
    elif ext.endswith('yml') or ext.endswith('.yaml'):
        import yaml
        def load(fobj):
            return yaml.load(fobj, Loader=yaml.Loader)
    elif ext.endswith('json'):
        from json import load
    elif ext.endswith('py'):
        # python only supports a single detector definition
        def load(fobj):
            r = {}
            exec(fobj.read(), None, r)
            return [r]
    else:
        raise NotImplementedError
    with path.open() as fobj:
        return load(fobj)


def create_view(config):
    view = pyqtgraph.GraphicsLayoutWidget()
    view.source_items = {}
    for panel in config["layout"]:
        row, col = panel["location"]
        #vb = view.addPlot(row=row, col=col)
        plot = view.addPlot(row=row, col=col)
        for source in panel["sources"]:
            item = None
            if source.endswith("/image"):
                item = pyqtgraph.ImageItem()
            elif source.endswith("/profile-y"):
                item = pyqtgraph.PlotCurveItem()
            elif source.endswith("/profile-x"):
                item = pyqtgraph.PlotCurveItem()
            else:
                logging.warning("unknown source: %r", source)
            if item is not None:
                plot.addItem(item)
                view.source_items[item] = source
    return config["name"], view


def create_camera(config):
    if "user_name" in config:
        camera = Camera.from_user_name(config["user_name"])
        name = config.get("name", config["user_name"])
    elif "serial_number" in config:
        camera = Camera.from_serial_number(config["serial_number"])
        name = config.get("name", config["serial_number"])
    elif "host" in config:
        camera = Camera.from_host(config["host"])
        name = config.get("name", config["host"])
    else:
        msg = "missing camera ID (user_name, serial_number or host)"
        if "name" in config:
            msg += " for {}".format(config["name"])
        raise ValueError(msg)
    configuration = Configuration()
    if "packet_size" in config:
        configuration.packet_size = config["packet_size"]
    if "inter_packet_delay" in config:
        configuration.inter_packet_delay = config["inter_packet_delay"]
    if "frame_transmission_delay" in config:
        configuration.frame_transmission_delay = config["frame_transmission_delay"]
    if "output_queue_size" in config:
        configuration.output_queue_size = config["output_queue_size"]
    camera.register_configuration(configuration)
    return name, camera


def link_views(views, sources):
    for view in views.values():
        for item, source_name in view.source_items.items():
            name, event = source_name.split("/", 1)
            source = sources[name]
            if event == "image":
                source.newFrame.connect(item.setImage)
            elif event == "profile-x":
                source.newProfileX.connect(item.setData)
            elif event == "profile-y":
                source.newProfileY.connect(item.setData)


def main():
    app = Qt.QApplication([])

    config = load_config("gui.yml")
    cameras = dict(create_camera(conf) for conf in config["cameras"])

    with contextlib.ExitStack() as cam_stack:
        [cam_stack.enter_context(camera) for camera in cameras.values()]
        forms = {name: CameraForm(camera) for name, camera in cameras.items()}
        sources = {name: QCamera(form.camera, form) for name, form in forms.items()}
        views = dict(create_view(view) for view in config["views"])
        link_views(views, sources)

        gui = Qt.QMainWindow()
        uic.loadUi(UI, baseinstance=gui)
        for name, form in forms.items():
            dock =  Qt.QDockWidget(name, gui)
            dock.setWidget(form)
            gui.addDockWidget(Qt.Qt.LeftDockWidgetArea, dock)
        # TODO: support multiple windows (maybe MDIArea)
        gui.setCentralWidget(views["main"])

        #gui = GUI(cameras)
        gui.show()
        app.exec_()


if __name__ == "__main__":
    main()
