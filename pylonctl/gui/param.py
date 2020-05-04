from PyQt5 import Qt

from pyqtgraph.parametertree import Parameter, ParameterTree, ParameterItem

from pylonctl.camera import parameter_dict


def strip_limits(data):
    data.pop("limits", None)
    for child in data.get("children", ()):
        strip_limits(child)


def main(camera):
    app = Qt.QApplication([])

    t = ParameterTree()
    t.resize(600, 800)
    t.show()

    def value_changed(param, value):
        try:
            setattr(camera, param.name(), value)
        except Exception as err:
            Qt.QMessageBox.critical(
                None, "Error setting {}".format(param.name()), repr(err)
            )

    def connect(param, slot):
        param.sigValueChanged.connect(slot)
        for child in param.children():
            connect(child, slot)

    with camera:
        t.setWindowTitle(camera.device_info.GetFriendlyName())
        data = parameter_dict(camera)
        # limits are dynamic (ex: max offset-x depends on current value
        # of width).
        strip_limits(data)
        p = Parameter.create(**data)
        t.setParameters(p, showTop=False)
        connect(p, value_changed)
        app.exec_()
