import math
import socket
import logging
import functools
import contextlib

from treelib import Tree
from pypylon import pylon, genicam
from pypylon.genicam import WO, RO, RW
from beautifultable import BeautifulTable


@functools.lru_cache(maxsize=1)
def transport_factory(factory=None):
    return pylon.TlFactory.GetInstance() if factory is None else factory


def get_device_from_info(dev_info, factory=None):
    factory = transport_factory(factory)
    return factory.CreateFirstDevice(dev_info)


def get_icamera_from_dev_info(dev_info, factory=None):
    dev = get_device_from_info(dev_info, factory)
    return pylon.InstantCamera(dev)


def get_device_from(factory=None, **kwargs):
    di = pylon.DeviceInfo()
    for key, value in kwargs.items():
        if key == "IpAddress":
            value = socket.gethostbyname(value)
        getattr(di, "Set" + key)(value)
    return get_device_from_info(di, factory)


def get_icamera_from(factory=None, **kwargs):
    dev = get_device_from(factory=factory, **kwargs)
    return pylon.InstantCamera(dev)


class Camera:
    def __init__(self, icam):
        dev_info = icam.GetDeviceInfo()
        log = logging.getLogger(dev_info.GetFullName())
        self.__dict__.update(dict(icam=icam, log=log))

    def __str__(self):
        return self.device_info.GetFriendlyName()

    def __repr__(self):
        props = iter_info(self.device_info)
        return "\n".join(": ".join(prop) for prop in props)

    def __getattr__(self, name):
        return getattr(self.icam, name)

    def __setattr__(self, name, value):
        return setattr(self.icam, name, value)

    def __enter__(self):
        self.icam.Open()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.icam.Close()

    def __dir__(self):
        members = {i for i in dir(self.icam) if not i.startswith("_")}
        members.update(dir(type(self)))
        return sorted(members)

    @property
    def device_info(self):
        return self.icam.GetDeviceInfo()

    @classmethod
    def from_host(cls, ip_or_hostname):
        return cls(get_icamera_from(IpAddress=ip_or_hostname))

    @classmethod
    def from_model(cls, name):
        return cls(get_icamera_from(ModelName=name))

    @classmethod
    def from_user_name(cls, user_name):
        return cls(get_icamera_from(UserDefinedName=user_name))

    @classmethod
    def from_serial_number(cls, serial_number):
        return cls(get_icamera_from(SerialNumber=serial_number))

    def register_configuration(
        self,
        config,
        mode=pylon.RegistrationMode_ReplaceAll,
        clean_up=pylon.Cleanup_Delete,
    ):
        self.icam.RegisterConfiguration(config, mode, clean_up)

    def register_image_event_handler(
        self,
        handler,
        mode=pylon.RegistrationMode_ReplaceAll,
        clean_up=pylon.Cleanup_Delete,
    ):
        self.icam.RegisterImageEventHandler(handler, mode, clean_up)


@contextlib.contextmanager
def ensure_grab_stop(camera):
    try:
        yield camera
    finally:
        camera.StopGrabbing()


def prepare_acq(camera, exposure, latency, roi=None, binning=(1, 1), pixel_format="Mono8"):
    try:
        camera.ExposureTime = exposure * 1e6
    except genicam.LogicalErrorException:
        try:
            # ace Classic/U/L GigE Cameras
            camera.ExposureTimeAbs = exposure * 1e6
        except genicam.LogicalErrorException:
            # For older cameras (scout, pilot) exposure time with:
            camera.ExposureTimeBaseAbs = 100.0
            raw = math.ceil(exposure / 50.0)
            camera.ExposureTimeRaw = int(raw)
            camera.ExposureTimeBaseAbs = (exposure / raw) * 1e6
    if latency < 1e-6:
        camera.AcquisitionFrameRateEnable = False
    else:
        camera.AcquisitionFrameRateEnable = True
        period = latency + exposure
        camera.AcquisitionFrameRateAbs = 1 / period
    # first reset binning, offset and size
    try:
        camera.BinningHorizontal = 1
        camera.BinningVertical = 1
    except genicam.LogicalErrorException:
        pass
    camera.OffsetX = 0
    camera.OffsetY = 0
    camera.Width = camera.WidthMax.Value
    camera.Height = camera.HeightMax.Value
    camera.PixelFormat = pixel_format
    if roi is None:
        roi = 0, 0, camera.WidthMax.Value, camera.HeightMax.Value
    x, y, w, h = roi
    camera.Width = w
    camera.Height = h
    camera.OffsetX = x
    camera.OffsetY = y
    ww, hh = camera.Width.Value, camera.Height.Value
    bh, bv = binning
    if (bh, bv) != (1, 1):
        camera.BinningHorizontal = bh
        camera.BinningVertical = bv


TRIGGER_SOURCE_MAP = {"internal": "Off", "line1": "Line1", "software": "Software"}


def set_trigger(camera, source="Internal", activation="RisingEdge"):
    """Source: Internal, Software, Line1"""
    source = TRIGGER_SOURCE_MAP[source.lower()]
    selectors = camera.TriggerSelector.Symbolics
    for selector in selectors:
        camera.TriggerSelector = selector
        camera.TriggerMode = "Off"
    if source != "Off":
        selector = "FrameStart" if "FrameStart" in selectors else selectors[0]
        camera.TriggerSelector = selector
        camera.TriggerMode = "On"
        camera.TriggerSource = source
        if source != "Software":
            camera.TriggerActivation = activation
    camera.AcquisitionMode = "Continuous"


class Acquisition:
    def __init__(
        self,
        camera,
        nb_frames,
        exposure,
        latency,
        roi=None,
        binning=(1, 1),
        pixel_format="Mono8",
        trigger="internal",
    ):
        self.camera = camera
        self.trigger = trigger
        self.nb_frames = nb_frames
        self.exposure = exposure
        self.latency = latency
        self.period = exposure + latency
        self.roi = roi
        self.binning = binning
        self.pixel_format = pixel_format
        self.prepared = False
        if nb_frames:
            self.start = functools.partial(camera.StartGrabbingMax, nb_frames)
        else:
            self.start = camera.StartGrabbing

    def prepare(self):
        if self.prepared:
            return
        prepare_acq(
            self.camera, self.exposure, self.latency, self.roi,
            self.binning, self.pixel_format
        )
        self.prepared = True

    def __iter__(self):
        return self

    def __next__(self):
        camera = self.camera
        if not camera.IsGrabbing():
            raise StopIteration()
        wait_ms = int((self.period + 1) * 1000)
        if self.trigger == "software":
            camera.WaitForFrameTriggerReady(100, pylon.TimeoutHandling_ThrowException)
            camera.ExecuteSoftwareTrigger()
        return camera.RetrieveResult(wait_ms, pylon.TimeoutHandling_ThrowException)

    def __enter__(self):
        self.prepare()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass


class Configuration(pylon.ConfigurationEventHandler):

    packet_size = 1500
    inter_packet_delay = 0
    frame_transmission_delay = 0
    output_queue_size = 5
    trigger_source = "internal"

    def OnOpened(self, camera):
        try:
            self.apply_config(camera)
        except Exception:
            name = camera.GetDeviceInfo().GetUserDefinedName()
            log = logging.getLogger(name)
            log.exception("OnOpened error")

    def apply_config(self, camera):
        name = camera.GetDeviceInfo().GetUserDefinedName()
        log = logging.getLogger(name)
        log.debug("OnOpened: Preparing network parameters")
        if camera.IsGigE():
            camera.GevSCPSPacketSize = self.packet_size
            camera.GevSCPD = self.inter_packet_delay
            camera.GevSCFTD = self.frame_transmission_delay
        # reproduce default continuous configuration
        writable = camera.TriggerSelector.GetAccessMode() in {WO, RW}
        if writable:
            set_trigger(camera, self.trigger_source)

        camera.OutputQueueSize = self.output_queue_size
        log.debug("OnOpened: Finished configuration")


class ImageLogger(pylon.ImageEventHandler):

    def OnImageSkipped(self, camera, nb_skipped):
        name = camera.GetDeviceInfo().GetUserDefinedName()
        log = logging.getLogger(name)
        log.error("Skipped %d images", nb_skipped)

    def OnImageGrabbed(self, camera, result):
        name = camera.GetDeviceInfo().GetUserDefinedName()
        log = logging.getLogger(name)
        if result.GrabSucceeded():
            data = result.Array
            log.info("Grabbed %s %s", data.shape, data.dtype)
        else:
            error = result.GetErrorDescription()
            log.error("Error grabbing: %s", error)


def iter_parameter_values(obj, filt=None):
    values = ((name, getattr(obj, name)) for name in dir(obj))
    ivalues = (
        (name, value) for name, value in values if isinstance(value, genicam.IValue)
    )
    return ivalues if filt is None else filter(filt, ivalues)


def get_field(v, field, default=None):
    try:
        f = getattr(v, field, default)
    except genicam.GenericException:
        f = default
    return f


def parameter_encode(param, value):
    if isinstance(param, genicam.IInteger):
        f = int
    elif isinstance(param, genicam.IFloat):
        f = float
    elif isinstance(param, genicam.IString):
        f = str
    elif isinstance(param, genicam.IBoolean):
        f = lambda v: v not in {'false', 'False', 0, None}
    # TODO: enumeration
    return f(value)


def parameter_display(v):
    if not isinstance(v, dict):
        v = parameter_from_node(v)
    val = v.get("value", "---")
    unit = v.get("unit")
    unit = (" " + unit) if unit else ""
    m, M = v.get("limits", (None, None))
    i = v.get("step")
    rng = None
    if m is not None and M is not None:
        rng = f"[{m}:{M}]" if i is None else f"[{m}:{M}:{i}]"
    access = "RO" if v["readonly"] else "RW"
    r = f"{v['title']}: {val}{unit} ({access}) ({v['type'][0]})"
    if rng:
        r += " " + rng
    return r


def node_is_value(v):
    return isinstance(
        v, (genicam.IInteger, genicam.IFloat, genicam.IEnumeration, genicam.IBoolean, genicam.IString)
    )


def parameter_table(obj, filt=None):
    table = BeautifulTable()
    table.columns.header = "Name", "Value", "Type", "Access"
    for name, value in iter_parameter_values(obj, filt):
        vd = parameter_from_node(value)
        row = (
            vd["name"],
            vd.get("value"),
            vd["type"],
            "RO" if vd["readonly"] else "RW",
        )
        table.rows.append(row)
    return table


def iter_parameter_display(obj, filt=None):
    if filt is None:

        def f(o):
            return o[1].GetAccessMode() in {RO, RW}

    else:

        def f(o):
            return o[1].GetAccessMode() in {RO, RW} and filt(o)

    for name, value in iter_parameter_values(obj, filt=f):
        if node_is_value(value):
            vd = parameter_from_node(value)
            yield parameter_display(vd)


TypeMap = {
    genicam.IInteger: "int",
    genicam.IBoolean: "bool",
    genicam.IFloat: "float",
    genicam.IEnumeration: "list",
    genicam.IString: "str",
    genicam.ICategory: "group",
    genicam.ICommand: "action",
    genicam.IRegister: "register",
}


def parameter_from_node(n):
    access = n.GetAccessMode()
    result = dict(
        name=n.Node.Name,
        type=TypeMap[type(n)],
        title=n.Node.DisplayName,
        readonly=access == RO,
    )
    if n.Node.ToolTip:
        result["tip"] = n.Node.ToolTip
    value = get_field(n, "Value")
    if value is not None:
        result["value"] = value
    suffix = get_field(n, "Unit")
    if suffix is not None:
        result["suffix"] = suffix
    m, M = get_field(n, "Min"), get_field(n, "Max")
    if m is not None and M is not None:
        result["limits"] = m, M
    step = get_field(n, "Inc")
    if step is not None:
        result["step"] = step
    if hasattr(n, "GetEntries"):
        result["values"] = {e.Symbolic: e.Value for e in n.GetEntries()}
    return result


def _parameter_dict(n, filt=None):
    result = parameter_from_node(n)
    if isinstance(n, genicam.ICategory):
        children = (
            _parameter_dict(feature, filt=filt)
            for feature in n.Features
            if not isinstance(feature, genicam.IRegister)
        )
        children = [child for child in children if child is not None]
        if not children:
            return
        result["children"] = children
    elif filt is not None and not filt(result):
        return
    return result


def parameter_dict(obj, filt=None):
    if hasattr(obj, "Root"):
        obj = obj.Root
    return _parameter_dict(obj, filt=filt)


def parameter_tree(item, filt=None):
    def _node_item(d, parent=None):
        if d is None:
            return
        children = d.pop("children", ())
        name = d.pop("name")
        this = tree.create_node(name, name, parent, data=d)
        for key, value in d.items():
            text = "{}: {}".format(key, value)
            if len(text) > 80:
                text = text[:75] + "[...]"
            tree.create_node(text, parent=this)
        for child in children:
            _node_item(child, parent=this)

    tree = Tree()
    _node_item(parameter_dict(item, filt=filt))
    return tree


# Object property related functions (applicable to DeviceInfo and Transport)


def info_names(obj, filt=None):
    names = obj.GetPropertyNames()[1]
    if filt:
        names = tuple(filter(filt, names))
    return names


def iter_info(obj, filt=None):
    names = info_names(obj, filt=filt)
    for name in names:
        yield (name, obj.GetPropertyValue(name)[1])


def info_table(*objs, filt=None):
    """
    Return a BeautifulTable with info values for the given objects
    """
    props = set()
    props.update(*(info_names(obj, filt=filt) for obj in objs))
    props = sorted(props)
    table = BeautifulTable()
    table.columns.header = props
    for obj in objs:
        values = tuple(obj.GetPropertyValue(name)[1] for name in props)
        table.rows.append(values)
    return table


def camera_table(filt=None):
    dev_info_list = transport_factory().EnumerateDevices()
    garbage = {
        "DeviceFactory", "SubnetAddress",
        "IpConfigOptions", "IpConfigCurrent", "IpAddress", "PortNr",
        "DefaultGateway", "SubnetMask", "InterfaceID", "VendorName",
    }
    if filt is None:
        def filt(x):
            return x
    repl = {
        'DeviceClass': 'Class',
        'ModelName': 'Name',
        'UserDefinedName': 'User name',
        'FriendlyName': 'Friendly name',
        'FullName': 'Full name',
        'SerialNumber': 'Serial Nb.'
    }
    table = info_table(*dev_info_list, filt=lambda c: filt(c) and c not in garbage)
    table.columns.header = [repl.get(name, name) for name in table.columns.header]
    return table
