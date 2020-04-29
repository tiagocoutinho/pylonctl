import socket
import logging
import functools

from treelib import Tree
from pypylon import pylon, genicam


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
        return self.device_info.GetFullName()

    def __repr__(self):
        props = iter_obj_props(self.device_info)
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


def iacquire(camera, nb_frames, exposure, latency):
    camera.ExposureTimeAbs = exposure * 1E6
    if latency < 1e-6:
        camera.AcquisitionFrameRateEnable = False
    else:
        camera.AcquisitionFrameRateEnable = True
        period = latency + exposure
        camera.AcquisitionFrameRateAbs = 1 / period
    camera.StartGrabbingMax(nb_frames)
    while camera.IsGrabbing():
        yield camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)


# Access mode: NotImplemented, NotAvailable, WriteOnly, ReadOnly, ReadWrite
NI, NA, WO, RO, RW = range(5)


def iter_obj_values(obj, filt=None):
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


def v_dict(value, default=None):
    access = value.GetAccessMode()
    return dict(
        Value=get_field(value, 'Value', default),
        Access=genicam.EAccessModeClass.ToString(access),
        Name=value.Node.Name,
        DisplayName=value.Node.DisplayName,
        Unit=get_field(value, 'Unit', default),
        Min=get_field(value, 'Min', default),
        Max=get_field(value, 'Max', default),
        Inc=get_field(value, 'Inc', default),
        Type=type(value).__name__[1:],
        Description=value.Node.Description,
        ToolTip=value.Node.ToolTip
    )


def v_display(v):
    if not isinstance(v, dict):
        v = v_dict(v)
    val = v['Value']
    if val is None:
        val = '---'
    unit = v['Unit']
    unit = (' ' + unit) if unit else ''
    m, M, i = v['Min'], v['Max'], v['Inc']
    rng = None
    if m is not None and M is not None:
        rng = f'[{m}:{M}]' if i is None else f'[{m}:{M}:{i}]'
    r = f"{v['DisplayName']}: {val}{unit} ({v['Access']}) ({v['Type'][0]})"
    if rng:
        r += ' ' + rng
    return r


def v_is_value(v):
    return isinstance(v, (genicam.IInteger, genicam.IEnumeration,
                          genicam.IBoolean, genicam.IString))


def obj_tree(obj, name=None, filt=None):
    if name is None:
        name = obj.device_info.GetFullName()
    tree = Tree()
    root = tree.create_node(name, name)
    for name, value in iter_obj_values(obj, filt):
        n = tree.create_node(name, name, root)
        vd = v_dict(value)
        for k, v in vd.items():
            if v is not None:
                if k in {'Description', 'ToolTip'} and len(v) > 80:
                    v = v[:75] + "[...]"
                tree.create_node(
                    '{}: {}'.format(k, v), parent=n)
    return tree


def obj_table(obj, max_width=80, filt=None):
    table = BeautifulTable(max_width=max_width)
    table.column_headers = 'Name', 'Value', 'Type', 'Access', 'Display'
    for name, value in iter_obj_values(obj, filt):
        vd = v_dict(value, '---')
        row = (vd['Name'], vd['Value'], vd['Type'][0],
               vd['Access'], vd['DisplayName'])
        table.append_row(row)
    return table


def obj_prop_names(obj, filt=None):
    names = obj.GetPropertyNames()[1]
    if filt:
        names = tuple(filter(filt, names))
    return names


def iter_obj_props(obj, filt=None):
    names = obj_prop_names(obj, filt=filt)
    for name in names:
        yield (name, obj.GetPropertyValue(name)[1])


from beautifultable import BeautifulTable


def prop_list_table(*objs, max_width=80, filt=None):
    """
    Return a BeautifulTable for all the properties of all given objects
    """
    props = set()
    props.update(*(obj_prop_names(obj, filt=filt) for obj in objs))
    table = BeautifulTable(max_width=max_width)
    table.column_headers = props
    for obj in objs:
        values = tuple(obj.GetPropertyValue(name)[1] for name in props)
        table.append_row(values)
    return table
