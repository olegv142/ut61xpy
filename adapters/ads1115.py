"""
ADS1115 16 bit ADC adapter
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

class ADS1115Device(I2CDevice):
    """ADS1115 ADC adapter"""
    MODEL_NAME = 'ADS1115'
    NCHANNELS  = 2
    I2C_ADDR   = 0x48
    GAIN       = [0, 0]
    MUX        = [0, 7]
    TOUT       = .5
    IDLE_DELAY = .05

    def set_gain(self, gain: int, chan: int = 0) -> bool:
        """
        Set PGA gain. The full scale range is 4.096V / gain except for
        the gain 0 where it equals to 6.144V (so actual gain = 2/3).
        """
        assert 0 <= chan < self.NCHANNELS
        if gain in (0, 1, 2, 4, 8, 16):
            self.GAIN[chan] = gain
            return True
        return False

    def set_mux(self, mux: int, chan: int = 0) -> bool:
        """
        Set input MUX configuration:
          0 : AINP = AIN0 and AINN = AIN1
          1 : AINP = AIN0 and AINN = AIN3
          2 : AINP = AIN1 and AINN = AIN3
          3 : AINP = AIN2 and AINN = AIN3
          4 : AINP = AIN0 and AINN = GND
          5 : AINP = AIN1 and AINN = GND
          6 : AINP = AIN2 and AINN = GND
          7 : AINP = AIN3 and AINN = GND
        """
        assert 0 <= chan < self.NCHANNELS
        if 0 <= mux < 8:
            self.MUX[chan] = mux
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
                return self.set_gain(int(val), 0)
            if lkey == 'again':
                return self.set_gain(int(val), 1)
            if lkey == 'mux':
                return self.set_mux(int(val), 0)
            if lkey == 'amux':
                return self.set_mux(int(val), 1)
        except Exception as e:
            log.debug(e, exc_info=True)
            return False
        return super().set_param(key, val)

    def init(self, nchannels: int = 1):
        """
        Initialize device setting the number of channels we are going to read.
        Should be called before the first query_raw call.
        """
        assert 0 < nchannels <= self.NCHANNELS
        super().init(nchannels)

    def exec_conversion_raw(self, mux: int, gain: int, idle_sleep=time.sleep) -> bytes|None:
        """Executes single conversion given MUX and GAIN. Returns raw bytes result or None on error."""
        if not self.is_connected():
            return None
        gcode = {0: 0, 1: 1, 2: 2, 4: 3, 8: 4, 16: 5}.get(gain, 0)
        wait = self.TOUT
        try:
            self.adapter.i2c_write(self.I2C_ADDR, [1, (1 << 7) + (mux << 4) + (gcode << 1) + 1, 0])
            while True:
                idle_sleep(self.IDLE_DELAY)
                if (status := self.adapter.i2c_read(self.I2C_ADDR, 2)) is None:
                    return None
                if status[0] & (1 << 7):
                    if not self.adapter.i2c_write(self.I2C_ADDR, [0]): # set target register address
                        return None
                    if not (data := self.adapter.i2c_read(self.I2C_ADDR, 2)):
                        return None
                    return bytes(data)
                wait -= self.IDLE_DELAY
                if wait <= 0:
                    return None
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)
            return None

    def exec_conversion(self, mux: int, gain: int, idle_sleep=time.sleep) -> float|None:
        """Executes single conversion given MUX and GAIN. Returns measured voltage or None on error."""
        data = self.exec_conversion_raw(mux, gain, idle_sleep)
        if not data:
            return None
        val = struct.unpack('>h', data)[0]
        FSR = 6.144 if not gain else 4.096 / gain
        return val * FSR / (1 << 15)

    def query_raw(self, idle_sleep=time.sleep) -> Any|None:
        """Query data from device"""
        data = []
        for c in range(self.channels):
            val = self.exec_conversion(self.MUX[c], self.GAIN[c], idle_sleep)
            if val is None:
                return None
            data.append(val)
        return data

    def get_value(self, data, channel: int = 0) -> float:
        """Retrieve floating point value for the given channel"""
        assert 0 <= channel < self.channels
        if not data:
            return Device.INVALID_VALUE
        return data[channel]

    def get_mode(self, data, channel: int = 0) -> str:
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        return 'V'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG) 
    if dev := ADS1115Device.set_i2c_adapter(CP2112Adapter if '--2112' in sys.argv[1:] else FT260Adapter).open():
        print(dev)
        assert dev.set_gain(1)
        assert not dev.set_gain(-1)
        assert dev.set_mux(0)
        assert dev.set_gain(0, 1)
        assert dev.set_mux(7, 1)
        with dev:
            dev.init(2)
            while dev.is_connected():
                data = dev.query_raw()
                print(dev.get_value(data), dev.get_mode(data), dev.get_value(data, 1), dev.get_mode(data, 1))
