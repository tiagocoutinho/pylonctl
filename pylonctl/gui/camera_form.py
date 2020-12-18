from PyQt5 import Qt, uic
import pkg_resources

from pypylon.genicam import LogicalErrorException


UI = pkg_resources.resource_filename("pylonctl.gui", "camera_form.ui")


def get_camera_data(camera):
    frame_time = 1 / camera.AcquisitionFrameRateAbs.Value
    exposure_time = camera.ExposureTimeAbs.Value / 1E6
    try:
        binning = camera.BinningHorizontal.Value, camera.BinningVertical.Value
    except LogicalErrorException:
        binning = None
    return dict(
        camera=camera,
        name=camera.device_info.GetFriendlyName(),
        exposure_time=exposure_time,
        latency=frame_time - exposure_time,
        roi=(
            camera.OffsetX.Value,
            camera.OffsetY.Value,
            camera.Width.Value,
            camera.Height.Value
        ),
        binning=binning
    )


class CameraForm(Qt.QWidget):

    def __init__(self, camera=None, parent=None):
        super().__init__(parent)
        uic.loadUi(UI, baseinstance=self)
        self.set_camera(camera)

    def set_camera(self, camera):
        self.camera = camera
        if camera is not None:
            self.set_data(get_camera_data(camera))

    def set_data(self, data):
        roi = data["roi"]
        self.setWindowTitle(data["name"])
        self.nb_frames.setValue(data.get("nb_frames", 0))
        self.exposure_time.setValue(data["exposure_time"])
        self.latency.setValue(data["latency"])
        self.x_spin.setValue(roi[0])
        self.y_spin.setValue(roi[1])
        self.w_spin.setValue(roi[2])
        self.h_spin.setValue(roi[3])
        binning = data.get("binning")
        has_binning = binning is not None
        if has_binning:
            self.h_bin_spin.setValue(binning[0])
            self.v_bin_spin.setValue(binning[1])
        self.h_bin_spin.setEnabled(has_binning)
        self.v_bin_spin.setEnabled(has_binning)

    def get_data(self):
        if self.h_bin_spin.isEnabled():
            binning = self.h_bin_spin.value(), self.v_bin_spin.value()
        else:
            binning = None
        return dict(
            nb_frames=self.nb_frames.value(),
            exposure_time=self.exposure_time.value(),
            latency=self.latency.value(),
            roi=(
                self.x_spin.value(),
                self.y_spin.value(),
                self.w_spin.value(),
                self.h_spin.value()
            ),
            binning=binning
        )

    def on_update_freq(self, v):
        exposure = self.exposure_time.value()
        latency = self.latency.value()
        period = exposure + latency
        freq = float("inf") if not period else 1 / period
        self.freq_value.setText("{:.3f} Hz".format(freq))

    def on_reset_roi(self):
        self.x_spin.setValue(0)
        self.y_spin.setValue(0)
        self.w_spin.setValue(self.camera.WidthMax.Value)
        self.h_spin.setValue(self.camera.HeightMax.Value)


def main():
    from pylonctl.camera import Camera
    camera = Camera.from_serial_number("0815-0000")
    app = Qt.QApplication([])
    gui = CameraForm()
    with camera:
        gui.set_camera(camera)
        gui.show()
        app.exec_()


if __name__ == "__main__":
    main()
