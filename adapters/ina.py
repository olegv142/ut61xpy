"""
Adapters for TI INA226 and INA228 current & voltage monitors
"""

import os
import sys
import time
import logging
import struct
from typing import Any

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from device import Device, HIDMixin
import ft260_i2c as ft260

log = logging.getLogger('DEV')

class I2CHIDMixin(HIDMixin):
    """The base class for I2C HID adapters"""
    def __init__(self, dev: Any, path: str):
        Device.__init__(self, path)
        self.dev = dev
        self.channels = None
        self.disconnected = False

    def is_connected(self) -> bool:
        return self.dev and not self.disconnected

    def init(self, nchannels=1):
        """
        Initialize device setting the number of channels we are going the read.
        Should be called before first query_raw call.
        """
        self.channels = nchannels
        self.i2c_init()

    def get_channels(self, data: Any) -> int:
        """Get the number of channels contained in the raw data"""
        if not data:
            return 0
        return self.channels

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        self.dev.close()
        self.dev = None

    def i2c_init(self):
        """Initialize I2C bus"""
        raise NotImplementedError()

    def i2c_write(self, addr: int, data: list[int]):
        """Write data bytes to I2C given target address"""
        raise NotImplementedError()

    def i2c_read(self,
            addr: int, length: int,
            tout: float|None = None,
            idle_sleep: Callable[[float], None] = time.sleep
    ) -> list[int]|None:
        """Read data bytes from I2C given target address"""
        raise NotImplementedError()

class FT260Mixin(I2CHIDMixin):
    """FTDI FT260 I2C adapter base class"""
    DEVICE_VID = ft260.DEVICE_VID
    DEVICE_PID = ft260.DEVICE_PID

    def i2c_init(self):
        ft260.i2c_init(self.dev)

    def i2c_write(self, addr: int, data: list[int]):
        ft260.i2c_write(self.dev, addr, data)

    def i2c_read(self,
            addr: int, length: int,
            tout: float|None = None,
            idle_sleep: Callable[[float], None] = time.sleep
    ) -> list[int]|None:
        return ft260.i2c_read(self.dev, addr, length,
            tout=tout, idle_sleep=idle_sleep)

class INA226Device(Device):
    """INA226 16bit current and voltage monitor base class"""
    I2C_ADDR = 64
    CURR_LSB = 2.5e-6
    VOLT_LSB = 1.25e-3
    SHUNT_RES = .1

    def get_mode(self, data, channel=0):
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        return ('A', 'V')[channel]

    def query_raw(self, tout=None, idle_sleep=time.sleep):
        try:
            self.i2c_write(self.I2C_ADDR, [1]) # set target register address
            idata = self.i2c_read(self.I2C_ADDR, 2, tout = tout, idle_sleep = idle_sleep)
            if idata is None:
                return None
            if self.channels < 2:
                return (bytes(idata),)
            self.i2c_write(self.I2C_ADDR, [2]) # set target register address
            vdata = self.i2c_read(self.I2C_ADDR, 2, tout = tout, idle_sleep = idle_sleep)
            if vdata is None:
                return None
            return (bytes(idata), bytes(vdata))
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)
            return None        

    def get_value(self, data, channel=0):
        """Converts raw data to the floating point value"""
        if not data:
            return Device.INVALID_VALUE
        val = struct.unpack('>h', data[channel])[0]
        return val * (self.CURR_LSB / self.SHUNT_RES, self.VOLT_LSB)[channel]

class INA226FT260Device(FT260Mixin, INA226Device):
    """Adapter class for INA226 16bit current and voltage monitor connected via FT260 USB chip"""
    MODEL_NAME = 'INA226-FT260'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    devT = INA226FT260Device
    if dev := devT.open():
        print(dev)
        with dev:
            dev.init(2)
            while dev.is_connected():
                data = dev.query_raw()
                print(
                    dev.get_value(data, 0), dev.get_mode(data, 0),
                    dev.get_value(data, 1), dev.get_mode(data, 1)
                )
