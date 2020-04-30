import socket
import logging
import functools
import contextlib

from treelib import Tree
from pypylon import pylon, genicam
from beautifultable import BeautifulTable


@functools.lru_cache(maxsize=1)
def transport_factory(factory=None):
    return pylon.TlFactory.GetInstance() if factory is None else factory


def get_icamera_from_dev_info(dev_info, factory=None):
    factory = transport_factory(factory)
    dev = factory.CreateDevice(dev_info)
    return pylon.InstantCamera(dev)


def get_icamera_from(factory=None, **kwargs):
    di = pylon.DeviceInfo()
    for key, value in kwargs.items():
        if key == 'IpAddress':
            value = socket.gethostbyname(value)
        getattr(di, 'Set'+key)(value)
    return get_icamera_from_dev_info(di, factory)


class Camera:

    def __init__(self, icam):
        dev_info = icam.GetDeviceInfo()
        log = logging.getLogger(dev_info.GetFullName())
        self.__dict__.update(dict(icam=icam, log=log))

    def __str__(self):
        return self.device_info.GetFriendlyName()

    def __repr__(self):
        props = iter_info(self.device_info)
        return '\n'.join(': '.join(prop) for prop in props)

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
        return ['device_info', 'from_host'] + dir(self.icam)

    @property
    def device_info(self):
        return self.icam.GetDeviceInfo()

    @classmethod
    def from_host(cls, ip_or_hostname):
        return cls(get_icamera_from(IpAddress=ip_or_hostname))


@contextlib.contextmanager
def ensure_grab_stop(camera):
    try:
        yield camera
    finally:
        camera.StopGrabbing()


def prepare_acq(camera, nb_frames, exposure, latency, roi=None):
    camera.ExposureTimeAbs = exposure * 1E6
    if latency < 1e-6:
        camera.AcquisitionFrameRateEnable = False
    else:
        camera.AcquisitionFrameRateEnable = True
        period = latency + exposure
        camera.AcquisitionFrameRateAbs = 1 / period
    ww, hh = camera.Width.Value, camera.Height.Value
    if roi is not None:
        x, y, w, h = roi
        if ww > w:
            camera.Width = w
            camera.OffsetX = x
        else:
            camera.OffsetX = x
            camera.Width = w
        if hh > h:
            camera.Height = h
            camera.OffsetY = y
        else:
            camera.OffsetY = y
            camera.Height = h


def iter_acquire(camera, nb_frames, exposure, latency):
    if nb_frames:
        camera.StartGrabbingMax(nb_frames)
    else:
        camera.StartGrabbing()
    period = exposure + latency
    period_ms = int(period * 1000)
    with ensure_grab_stop(camera):
        while camera.IsGrabbing():
            yield camera.RetrieveResult(
                period_ms + 100, pylon.TimeoutHandling_ThrowException)


class Acquisition:

    def __init__(self, camera):
        self.camera = camera

    def prepare(self, nb_frames, exposure, latency, roi=None):
        self.nb_frames = nb_frames
        self.exposure = exposure
        self.latency = latency
        prepare_acq(self.camera, nb_frames, exposure, latency, roi)

    def __iter__(self):
        return iter_acquire(self.camera, self.nb_frames, self.exposure, self.latency)


# Access mode: NotImplemented, NotAvailable, WriteOnly, ReadOnly, ReadWrite
NI, NA, WO, RO, RW = range(5)


def iter_parameter_values(obj, filt=None):
    values = ((name, getattr(obj, name)) for name in dir(obj))
    ivalues = ((name, value) for name, value in values
               if isinstance(value, genicam.IValue))
    return ivalues if filt is None else filter(filt, ivalues)


def get_field(v, field, default=None):
    try:
        f = getattr(v, field, default)
    except genicam.GenericException:
        f = default
    return f


def parameter_display(v):
    if not isinstance(v, dict):
        v = parameter_from_node(v)
    val = v.get('value', '---')
    unit = v.get('unit')
    unit = (' ' + unit) if unit else ''
    m, M = v.get('limits', (None, None))
    i = v.get('step')
    rng = None
    if m is not None and M is not None:
        rng = f'[{m}:{M}]' if i is None else f'[{m}:{M}:{i}]'
    access = 'RO' if v['readonly'] else 'RW'
    r = f"{v['title']}: {val}{unit} ({access}) ({v['type'][0]})"
    if rng:
        r += ' ' + rng
    return r


def node_is_value(v):
    return isinstance(v, (genicam.IInteger, genicam.IEnumeration,
                          genicam.IBoolean, genicam.IString))


def parameter_table(obj, filt=None):
    table = BeautifulTable()
    table.column_headers = 'Name', 'Value', 'Type', 'Access'
    for name, value in iter_parameter_values(obj, filt):
        vd = parameter_from_node(value)
        row = (vd['name'], vd.get('value'), vd['type'],
               'RO' if vd['readonly'] else 'RW')
        table.append_row(row)
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
    genicam.IInteger: 'int',
    genicam.IBoolean: 'bool',
    genicam.IFloat: 'float',
    genicam.IEnumeration: 'list',
    genicam.IString: 'str',
    genicam.ICategory: 'group',
    genicam.ICommand: 'action',
    genicam.IRegister: 'register',
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
        result['tip'] = n.Node.ToolTip
    value = get_field(n, 'Value')
    if value is not None:
        result['value'] = value
    suffix = get_field(n, 'Unit')
    if suffix is not None:
        result['suffix'] = suffix
    m, M = get_field(n, 'Min'), get_field(n, 'Max')
    if m is not None and M is not None:
        result['limits'] = m, M
    step = get_field(n, 'Inc')
    if step is not None:
        result['step'] = step
    if hasattr(n, 'GetEntries'):
        result['values'] = {e.Symbolic: e.Value for e in n.GetEntries()}
    return result


def _parameter_dict(n, filt=None):
    result = parameter_from_node(n)
    if isinstance(n, genicam.ICategory):
        children = (
            _parameter_dict(feature, filt=filt) for feature in n.Features
            if not isinstance(feature, genicam.IRegister)
        )
        children = [child for child in children if child is not None]
        if not children:
            return
        result['children'] = children
    elif filt is not None and not filt(result):
        return
    return result


def parameter_dict(obj, filt=None):
    if hasattr(obj, 'Root'):
        obj = obj.Root
    return _parameter_dict(obj, filt=filt)


def parameter_tree(item, filt=None):
    def _node_item(d, parent=None):
        if d is None:
            return
        children = d.pop('children', ())
        name = d.pop('name')
        this = tree.create_node(name, name, parent, data=d)
        for key, value in d.items():
            text = '{}: {}'.format(key, value)
            if len(text) > 80:
                text = text[:75] + '[...]'
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
    table = BeautifulTable()
    table.column_headers = props
    for obj in objs:
        values = tuple(obj.GetPropertyValue(name)[1] for name in props)
        table.append_row(values)
    return table
