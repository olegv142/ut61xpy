"""
MCP3421 18 bit ADC adapter
"""

import os
import sys
import logging
import struct
import time
from typing import Any

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from device import Device
from i2c import FT260Adapter, CP2112Adapter, I2CDevice
import ft260
import cp2112

log = logging.getLogger('DEV')

class MCP3421Device(I2CDevice):
    """MCP3421 ADC adapter"""
    MODEL_NAME = 'MCP3421'
    NCHANNELS = 1
    I2C_ADDR = 0x68
    VREF = 2.048
    GAIN = 1
    TOUT = .5
    IDLE_DELAY = .1

    def set_gain(self, gain: int) -> bool:
        """Set PGA gain"""
        if gain in (1, 2, 4, 8):
            self.GAIN = gain
            return True
        return False

    def set_param(self, key: str, val: str|float) -> bool:
        """
        Set device specific parameter.
        Returns True if key / val pair is recognized, False otherwise.
        """
        lkey = key.lower()
        try:
            if lkey == 'gain':
                return self.set_gain(int(val))
        except Exception as e:
            log.debug(e, exc_info=True)
            return False
        return super().set_param(key, val)

    def init(self, nchannels: int = NCHANNELS):
        """
        Initialize device setting the number of channels we are going to read.
        Should be called before the first query_raw call.
        """
        super().init(nchannels)
        gain = {1: 0, 2: 1, 4: 2, 8: 3}.get(self.GAIN, 0)
        rate = 3 << 2 # 3.75 SPS (18 bits)
        mode = 1 << 4 # continuous
        try:
            self.adapter.i2c_write(self.I2C_ADDR, [gain + rate + mode])
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)

    def query_raw(self, idle_sleep=time.sleep) -> Any|None:
        """Query raw data from device"""
        if not self.is_connected():
            return None
        wait = self.TOUT
        try:
            while True:
                idle_sleep(self.IDLE_DELAY)
                if (data := self.adapter.i2c_read(self.I2C_ADDR, 4)) is None:
                    return None
                if not (data[3] & 0x80):
                    return bytes(data[:3]) + b'\0'
                wait -= self.IDLE_DELAY
                if wait <= 0:
                    return None
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)
            return None

    def get_value(self, data, channel: int = 0) -> float:
        """Converts raw data to the floating point value"""
        if not data:
            return Device.INVALID_VALUE
        if channel != 0:
            return Device.INVALID_VALUE
        val = struct.unpack('>i', data)[0]
        return val * self.VREF / ((1 << (17+8)) * self.GAIN)

    def get_mode(self, data, channel: int = 0) -> str:
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        return 'V'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG) 
    if dev := MCP3421Device.set_i2c_adapter(CP2112Adapter if '--2112' in sys.argv[1:] else FT260Adapter).open():
        print(dev)
        assert dev.set_gain(8)
        assert not dev.set_gain(7)
        with dev:
            dev.init()
            while dev.is_connected():
                data = dev.query_raw()
                print(dev.get_value(data), dev.get_mode(data))
