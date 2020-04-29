import socket
import logging
import functools

from pypylon import pylon


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

