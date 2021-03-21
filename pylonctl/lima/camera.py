# -*- coding: utf-8 -*-
#
# This file is part of the sls project
#
# Copyright (c) 2019 ALBA Synchrotron
# Distributed under the GPL license. See LICENSE for more info.

import os
import math
import time
import logging
import threading

import numpy

from Lima.Core import (
    HwInterface, HwDetInfoCtrlObj, HwSyncCtrlObj, HwBufferCtrlObj, HwCap,
    HwFrameInfoType, SoftBufferCtrlObj, Size, Point, FrameDim, Roi,
    Bpp8, Bpp10, Bpp12, Bpp16,
    IntTrig, IntTrigMult, ExtTrigMult, ExtGate,
    Timestamp, AcqReady, AcqRunning, CtControl, CtSaving)

from pypylon import pylon
from pypylon.genicam import NI, NA, WO, RO, RW

from ..camera import Camera


Status = HwInterface.StatusType


PIXEL_FORMAT_LIMA_TO_PYLON = {
    Bpp8: pylon.PixelType_Mono8,
    Bpp12: pylon.PixelType_Mono12,
    Bpp16: pylon.PixelType_Mono16,
}


PIXEL_FORMAT_PYLON_TO_LIMA = {
    pylon.PixelType_Mono8: Bpp8,
    pylon.PixelType_BayerRG8: Bpp8,
    pylon.PixelType_BayerBG8: Bpp8,
    pylon.PixelType_RGB8packed: Bpp8,
    pylon.PixelType_BGR8packed: Bpp8,
    pylon.PixelType_RGBA8packed: Bpp8,
    pylon.PixelType_BGRA8packed: Bpp8,
    pylon.PixelType_YUV411packed: Bpp8,
    pylon.PixelType_YUV422packed: Bpp8,
    pylon.PixelType_YUV444packed: Bpp8,

    pylon.PixelType_Mono10: Bpp10,
    pylon.PixelType_BayerRG10: Bpp10,
    pylon.PixelType_BayerBG10: Bpp10,

    pylon.PixelType_Mono12: Bpp12,
    pylon.PixelType_BayerRG12: Bpp12,
    pylon.PixelType_BayerBG12: Bpp12,

    pylon.PixelType_Mono16: Bpp16,
    pylon.PixelType_BayerRG16: Bpp16,
    pylon.PixelType_BayerBG16: Bpp16,
}


class Sync(HwSyncCtrlObj):

    trig_mode = IntTrig
    latency_time = 0
    exp_time = 1
    latency_time = 0
    nb_frames = 1

    def __init__(self, detector):
        self.detector = detector
        super().__init__()

    def checkTrigMode(self, trig_mode):
        # TODO check with camera type (some cameras don't have HW Trigger)
        return trig_mode in (IntTrig, IntTrigMult, ExtTrigMult, ExtGate)

    def setTrigMode(self, trig_mode):
        if not self.checkTrigMode(trig_mode):
            raise ValueError('Unsupported trigger mode')
        selector = 'FrameStart'
        if selector not in self.detector.TriggerSelector.Symbolics:
            selector = 'AcquisitionStart'
        self.detector.TriggerSelector = selector
        if trig_mode is InTrig:
            self.detector.TriggerMode = "Off"
            self.detector.ExposureMode = "Timed"
        elif trig_mode is InTrigMult:
            self.detector.TriggerMode = "On"
            self.detector.TriggerSource = "Software"
            self.detector.ExposureMode = "Timed"
            #self.detector.AcquisitionFrameCount = 1
        elif trig_mode is ExtTrigMult:
            self.detector.TriggerMode = "On"
            self.detector.TriggerSource = "Line1"
            self.detector.AcquisitionFrameEnable = True
            self.detector.ExposureMode = "Timed"
        elif trig_mode is ExtGate:
            self.detector.TriggerMode = "On"
            self.detector.TriggerSource = "Line1"
            self.detector.AcquisitionFrameEnable = False
            self.detector.ExposureMode = "TriggerWidth"
        self.trig_mode = trig_mode

    def getTrigMode(self):
        return self.trig_mode

    def setExpTime(self, exp_time):
        if self.trig_mode = ExtGate:
            if self.detector.ExposureTimeAbs.GetAccessMode() in {WO, RW}:
                # More recent model like ACE and AVIATOR support direct
                # programming of the exposure using the exposure time absolute.
                camera.ExposureTimeAbs = 1E6 * exp_time
            else:
                # If scout or pilot, exposure time has to be adjusted using
                # the exposure time base + the exposure time raw.
                self.detector.ExposureTimeBaseAbs = 100
                self.detector.ExposureTimeRaw = math.ceil(exp_time / 50)
                raw = self.detector.ExposureTimeRaw.Value
                self.detector.ExposureTimeBaseAbs = 1E6 * exp_time / raw
        self.exp_time = exp_time
        if self.latency_time < 1e-6:
            self.detector.AcquisitionFrameRateEnable = False
        else:
            period = self.exp_time + self.latency_time
            self.detector.AcquisitionFrameRateEnable = True
            camera.AcquisitionFrameRateAbs.SetValue(1 / period)

    def getExpTime(self):
        return 1E-6 * self.detector.ExposureTimeAbs.Value

    def setLatTime(self, lat_time):
        self.latency_time = lat_time

    def getLatTime(self):
        return self.latency_time

    def setNbHwFrames(self, nb_frames):
        self.nb_frames = nb_frames

    def getNbHwFrames(self):
        return self.nb_frames

    def getValidRanges(self):
        min_t, max_t = self.getExpTimeRange()
        min_l, max_l = self.getLatTimeRange()
        return self.ValidRangesType(min_t, max_t, min_l, max_l)

    def getExpTimeRange(self):
        time_abs = self.detector.ExposureTimeAbs
        if time_abs.GetAccessMode() in {WO, RW}:
            return time_abs.Min * 1E-6, time_abs.Max * 1E-6
        else:
            # Pilot and and Scout do not have TimeAbs capability
            raw = self.detector.ExposureTimeRaw,
            base = self.detector.ExposureTimeBaseAbs
            initial_raw, initial_base = raw.Value, base.Value
            base.Value = base.Max
            max_exp = 1E-6 * base.Value * raw.Max
            base.Value = base.Min
            min_exp = 1E-6 * base.Value * raw.Min
            base.Value = initial_base
            raw.Value = initial_raw
            return min_exp, max_exp

    def getLatTimeRange(self):
        min_rate = self.detector.AcquisitionFrameRateAbs.Min
        max_lat = 1 / min_rate if min > 0 else 0
        return 0, max_lat


class DetInfo(HwDetInfoCtrlObj):

    def __init__(self, detector):
        self.detector = detector
        super().__init__()

    def getMaxImageSize(self):
        return Size(self.detector.WidthMax(), self.detector.HeightMax())

    def getDetectorImageSize(self):
        return Size(self.detector.WidthMax(), self.detector.HeightMax())

    def getDefImageType(self):
        return PIXEL_FORMAT_PYLON_TO_LIMA[self.detector.PixelFormat.IntValue]

    def getCurrImageType(self):
        return PIXEL_FORMAT_PYLON_TO_LIMA[self.detector.PixelFormat.IntValue]

    def setCurrImageType(self, image_type):
        self.detector.PixelFormat = PIXEL_FORMAT_LIMA_TO_PYLON[image_type]

    def getPixelSize(self):
        return (55.0e-6, 55.0e-6)

    def getDetectorType(self):
        return self.detector.device_info.GetVendorName()

    def getDetectorModel(self):
        return self.detector.device_info.GetModelName()

    def registerMaxImageSizeCallback(self, cb):
        pass

    def unregisterMaxImageSizeCallback(self, cb):
        pass


class Interface(HwInterface):

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self.det_info = DetInfo(detector)
        self.sync = Sync(detector)
        self.buff = SoftBufferCtrlObj()
        self.caps = list(map(HwCap, (self.det_info, self.sync, self.buff)))
        self._status = Status.Ready
        self._nb_acquired_frames = 0
        self._acq_thread = None
        self._acq = None

    def getCapList(self):
        return self.caps

    def reset(self, reset_level):
        self.stopAcq()

    def prepareAcq(self):
        nb_frames = self.sync.getNbHwFrames()
        frame_dim = self.buff.getFrameDim()
        frame_infos = [HwFrameInfoType() for i in range(nb_frames)]
        self._acq = self.detector.acquisition(progress_interval=None)
        self._nb_acquired_frames = 0
        self._acq_thread = threading.Thread(
            target=self._acquire, args=(self._acq, frame_dim, frame_infos))

    def startAcq(self):
        self._acq_thread.start()

    def stopAcq(self):
        if self._acq:
            self._acq.stop()
        else:
            self.detector.stop_acquisition()
        if self._acq_thread:
            self._acq_thread.join()

    def getStatus(self):
        s = Status()
        s.set(self._status)
        return s

    def getNbHwAcquiredFrames(self):
        return self._nb_acquired_frames

    def _acquire(self, acq, frame_dim, frame_infos):
        try:
            self._acquisition_loop(acq, frame_dim, frame_infos)
        except BaseException as err:
            print('Error occurred: {!r}'.format(err))
            import traceback
            traceback.print_exc()
        finally:
            self._acq = None

    def _acquisition_loop(self, acq, frame_dim, frame_infos):
        frame_size = frame_dim.getMemSize()
        buffer_mgr = self.buff.getBuffer()

        start_time = time.time()
        buffer_mgr.setStartTimestamp(Timestamp(start_time))
        self._status = Status.Exposure
        for frame_nb, (_, frame) in enumerate(acq):
            self._status = Status.Readout
            buff = buffer_mgr.getFrameBufferPtr(frame_nb)
            # don't know why the sip.voidptr has no size
            buff.setsize(frame_size)
            data = numpy.frombuffer(buff, dtype='<i4')
            data[:] = frame
            frame_info = frame_infos[frame_nb]
            frame_info.acq_frame_nb = frame_nb
            buffer_mgr.newFrameReady(frame_info)
            self._nb_acquired_frames += 1
            self._status = Status.Exposure
        self._status = Status.Ready


def get_ctrl():
    # TODO
    camera = Camera()
    interface = Interface(camera)
    ctrl = CtControl(interface)
    return ctrl
