"""
Device adapters abstract base classes
"""

from __future__ import annotations

import os
import sys
import time
import logging
from typing import Any
from collections.abc import Callable

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

import bt_engine

log = logging.getLogger('DEV')

hid = None

def import_hid():
    """
    Imports hid module taking into account that it may be called hidapi on some platforms
    """
    global hid
    if hid is not None:
        return
    try:
        import hid as hid
    except ModuleNotFoundError:
        import hidapi as hid

class Device:
    """
    Base class for all device adapters.
    Defines core functionality related to data readout.
    """

    TOUT: float = None # default timeout should be specified in subclasses
    INVALID_VALUE: float = float('nan')

    def __init__(self, *args):
        super().__init__(*args)

    def set_param(self, key: str, val: str|float) -> bool:
        """
        Set device specific parameter.
        Returns True if key / val pair is recognized, False otherwise.
        """
        try:
            if key.lower() == 'tout':
                self.set_tout(float(val))
                return True
        except Exception as e:
            log.debug(e, exc_info=True)
        return False

    def set_tout(self, tout_sec: float):
        """Set data readout timeout in seconds"""
        self.TOUT = tout_sec

    def init(self, nchannels: int = 1):
        """
        Initialize device setting the number of channels we are going to read.
        Should be called before the first query_raw call.
        """

    def query_raw(self, idle_sleep: Callable[[float], None] = time.sleep) -> Any|None:
        """Reads raw data packet from device and returns it. Returns None to indicate failure."""
        raise NotImplementedError()

    def get_channels(self, data: Any) -> int:
        """
        Get the number of channels contained in the raw data. If there are more than 1 channel
        its index should be passed explicitly to get_value and get_mode method. Otherwise
        the channel number may be retrieved by get_channel method.
        """
        return 1 if data else 0

    def get_channel(self, data: Any) -> int:
        """
        The UT61E+ can measure DC and AC voltage alternately in DC voltage dial position.
        This function returns 1 in such mode (25) if the data belongs to the alternative
        measuring channel, so it represents AC voltage. Otherwise it returns 0.
        """
        return 0

    def get_value(self, data: Any, channel: int|None = None) -> float:
        """
        Converts raw data to the floating point value. Here we don't
        care about units since the caller should be aware of them.
        It set mode dial manually after all. So in the mV mode the
        result is expressed in mV rather than volts. The method may
        return INVALID_VALUE = float('nan') to indicate failure to extract
        valid value from the raw data. In particular it returns NaN if DMM
        is overloaded.
        """
        raise NotImplementedError()

    def get_mode(self, data: Any, channel: int|None = None) -> str:
        """Returns measurement mode and units description string"""
        raise NotImplementedError()

class DeviceInstanceMixin:
    """
    This class and its descendants define methods related to creating a device adapter instance,
    specifically, device model information and connection-related functionality.
    Every multimeter adapter should be inherited from this class and Device class or their
    descendants. Having two inheritance chains provides maximum implementation flexibility since
    it allows for implementing different aspects of the device behavior in separate base classes.
    """

    # The following should be redefined in subclasses 
    MODEL_NAME: str = None
    IsBT: bool = None

    def __init__(self, path: str):
        self.path = path

    def __str__(self) -> str:
        raise NotImplementedError()

    def get_model(self) -> str:
        """The implementation may redefine this method to return actual model name"""
        return self.MODEL_NAME

    def is_connected(self) -> bool:
        """
        Returns True if device is connected, False otherwise.
        Subclasses may redefine this method to indicate disconnection.
        """
        return True

    def close(self):
        """Closes device if its still open"""
        raise NotImplementedError()

    def __enter__(self):
        """Context manager protocol support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes device on exiting 'with' block"""
        self.close()

class USBMixin(DeviceInstanceMixin):
    """Methods specific for USB devices"""
    IsBT: bool = False
    # Default VID, PID should be defined in subclasses
    DEVICE_VID: int = None
    DEVICE_PID: int = None

    def __init__(self, dev: Any, path: str):
        """Constructor, called by open_path"""
        DeviceInstanceMixin.__init__(self, path)
        self.dev = dev
        self.disconnected = False

    def is_connected(self) -> bool:
        """Returns True if device is connected, False otherwise"""
        return not self.disconnected

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        self.dev.close()
        self.disconnected = True
        self.dev = None

    @classmethod
    def list_paths(cls, vid: int|None = None, pid: int|None = None) -> list[str]:
        """Returns the list of USB device paths"""
        raise NotImplementedError()

    @classmethod
    def open_path(cls, path: str) -> Any:
        """Opens device given the path"""
        dev = cls._open_path(path)
        if dev is None:
            return None
        return cls(dev, path)

    @classmethod
    def _open_path(cls, path: str) -> Any:
        """Opens device given the path and returns it"""
        raise NotImplementedError()

    @classmethod
    def open(cls, vid: int|None = None, pid: int|None = None) -> Any:
        """Opens device instance given its VID, PID and returns it"""
        if vid is None:
            vid = cls.DEVICE_VID
        if pid is None:
            pid = cls.DEVICE_PID
        paths = cls.list_paths(vid, pid)
        if not paths:
            log.error('%s USB device not found', cls.MODEL_NAME)
            return None
        if len(paths) > 1:
            log.error('%d %s USB devices found', len(paths), cls.MODEL_NAME)
            return None
        return cls.open_path(paths[0])

    def __str__(self) -> str:
        return '[' + self.MODEL_NAME + ' USB]'

class HIDMixin(USBMixin):
    """Methods specific for USB HID devices"""
    @classmethod
    def list_paths(cls, vid: int|None = None, pid: int|None = None) -> list[str]:
        """Returns the list of HID device paths"""
        import_hid()
        if vid is None:
            vid = cls.DEVICE_VID
        if pid is None:
            pid = cls.DEVICE_PID
        return [dev['path'].decode('ascii') for dev in hid.enumerate(vid, pid)]

    @classmethod
    def _open_path(cls, path: str) -> 'hid.device'|None:
        """Opens hid device given the path and returns it"""
        import_hid()
        if isinstance(path, str):
            path = path.encode('ascii')
        dev = hid.device()
        try:
            dev.open_path(path)
        except Exception:
            log.error('failed to open %s USB HID device %s', cls.MODEL_NAME, path)
            return None
        dev.set_nonblocking(True)
        return dev

    def read_last(self, len: int) -> list[int]|None:
        skip = 0
        last_report = None
        while True:
            if report := self.dev.read(len):
                if last_report:
                    skip += 1
                last_report = report
            else:
                if skip:
                    log.debug('skip %d reports', skip)
                return last_report

class CDCMixin(USBMixin):
    """Methods specific for USB CDC devices"""
    # The following properties may be redefined in subclasses
    BAUD_RATE: int = 115200
    WRITE_TIMEOUT: float = .1

    @classmethod
    def list_paths(cls, vid: int|None = None, pid: int|None = None) -> list[str]:
        """Returns the list of CDC device paths"""
        from serial.tools.list_ports import comports
        if vid is None:
            vid = cls.DEVICE_VID
        if pid is None:
            pid = cls.DEVICE_PID
        return [port.device for port in comports() if port.vid == vid and port.pid == pid]

    @classmethod
    def _open_path(cls, path: str) -> 'serial.Serial'|None:
        """Opens CDC device given the path and returns it"""
        import serial
        try:
            return serial.Serial(path, baudrate=cls.BAUD_RATE, timeout=0, write_timeout=cls.WRITE_TIMEOUT)
        except Exception:
            log.error('failed to open %s USB CDC device %s', cls.MODEL_NAME, path)
            return None

class BTMixin(DeviceInstanceMixin):
    """Methods specific for BT devices"""
    IsBT: bool = True
    # Default BT device name should be defined in subclasses
    DEVICE_NAME: str = None

    def __init__(self, dev: Any, addr: str):
        DeviceInstanceMixin.__init__(self, addr)
        self.dev = dev

    def is_connected(self) -> bool:
        """Returns True if device is connected, False otherwise"""
        return self.dev and self.dev.is_connected

    @classmethod
    def list_addrs(cls, name: str|None = None) -> list[str]:
        """Returns the list of BT device addresses"""
        if name is None:
            name = cls.DEVICE_NAME
        return bt_engine.list_addrs(name)

    @classmethod
    def open_addr(cls, addr: str) -> Any:
        """Opens BT device instance given its mac address and returns it"""
        raise NotImplementedError()

    @classmethod
    def open(cls, name: str|None = None) -> Any:
        """Opens BT device instance given its name and returns it"""
        if name is None:
            name = cls.DEVICE_NAME
        addrs = cls.list_addrs(name)
        if not addrs:
            log.error('%s BT device not found', cls.MODEL_NAME)
            return None
        if len(addrs) > 1:
            log.error('%d %s BT devices found', len(addrs), cls.MODEL_NAME)
            return None
        return cls.open_addr(addrs[0])

    def __str__(self) -> str:
        return '[' + self.MODEL_NAME + ' BT]'
