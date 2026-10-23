"""
Adapters for TI INA226 and INA228 current & voltage monitors
"""

import os
import sys
import logging
import struct
from typing import Any

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from device import Device
from i2c import FT260Adapter, CP2112Adapter, I2CDevice
import ft260
import cp2112
import termocouple as tc

log = logging.getLogger('DEV')

class INADevice(I2CDevice):
    """Base class for INAxxx current and voltage monitors"""
    SHUNT_RES = .1 # Default shunt resistance
    # Channel names for convenience
    CURR_CHAN = 0
    VOLT_CHAN = 1
    NCHANNELS = 2

    def set_shunt_resistance(self, shunt_res: float):
        """Set shunt resistance in Ohms"""
        self.SHUNT_RES = shunt_res

    def set_param(self, key: str, val: str|float) -> bool:
        """
        Set device specific parameter.
        Returns True if key / val pair is recognized, False otherwise.
        """
        try:
            if key.lower() == 'shunt':
                self.set_shunt_resistance(float(val))
                return True
        except Exception as e:
            log.debug(e, exc_info=True)
            return False
        return super().set_param(key, val)

    def get_mode(self, data, channel: int = 0) -> str:
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        return ('A', 'V')[channel]

class INA226Device(INADevice):
    """INA226 16bit current and voltage monitor base class"""
    MODEL_NAME = 'INA226'
    NCHANNELS = 2
    I2C_ADDR = 64
    CURR_LSB = 2.5e-6
    VOLT_LSB = 1.25e-3

    def init(self, nchannels: int = NCHANNELS):
        """
        Initialize device setting the number of channels we are going to read.
        Should be called before the first query_raw call.
        """
        super().init(nchannels)
        try:
            # Set 4 msec conversion time and 4 samples averaging
            self.adapter.i2c_write(self.I2C_ADDR, [0, 0x43, 0xB7])
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)

    def query_raw(self, idle_sleep=None) -> Any|None:
        """
        Query raw data from device. Here we ignore timeout and idle callback args since
        I2C HID adapter normally responds without long waiting. Therefore calling callback
        here will just slow down readout without any benefits.
        """
        if not self.is_connected():
            return None
        try:
            if not self.adapter.i2c_write(self.I2C_ADDR, [1]): # set target register address
                return None
            if (idata := self.adapter.i2c_read(self.I2C_ADDR, 2)) is None:
                return None
            if self.channels < 2:
                return (bytes(idata),)
            if not self.adapter.i2c_write(self.I2C_ADDR, [2]): # set target register address
                return None
            if (vdata := self.adapter.i2c_read(self.I2C_ADDR, 2)) is None:
                return None
            return (bytes(idata), bytes(vdata))
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)
            return None        

    def get_value(self, data, channel: int = 0) -> float:
        """Converts raw data to the floating point value"""
        if not data:
            return Device.INVALID_VALUE
        val = struct.unpack('>h', data[channel])[0]
        return val * (self.CURR_LSB / self.SHUNT_RES, self.VOLT_LSB)[channel]

class INA228Device(INADevice):
    """INA228 20bit current and voltage monitor base class"""
    MODEL_NAME = 'INA228'
    I2C_ADDR = 64
    CURR0_LSB = 312.5e-9
    CURR1_LSB = 78.125e-9
    VOLT_LSB = 195.3125e-6
    TEMP_LSB = 7.8125e-3
    # Current measuring range (0 = ±163.84mV, 1 = ± 40.96mV)
    RANGE = 0
    # Shunt temperature coefficient (relative to 25°C)
    TEMPCO = 0
    # The number of readout channels (current, voltage and chip temperature)
    NCHANNELS = 3
    # The third channel may be used in scripts for reading chip temperature
    TEMP_CHAN = 2
    # The following channel may be used to read K-termocouple temperature instead of the current
    KTC_CHAN = 3

    CHAN_REMAP = None

    def init(self, nchannels: int = NCHANNELS):
        """
        Initialize device setting the number of channels we are going to read.
        Should be called before the first query_raw call.
        """
        super().init(nchannels)
        try:
            self.adapter.i2c_write(self.I2C_ADDR, [0, 0, 0 if not self.RANGE else 0x10])
            # Set 4 msec conversion time and 4 samples averaging
            self.adapter.i2c_write(self.I2C_ADDR, [1, 0xFF, 0xF9])
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)

    def set_shunt_voltage_range(self, val: int):
        """Set shunt voltage range (0 = ±163.84mV, 1 = ± 40.96mV)"""
        self.RANGE = val

    def set_shunt_temp_coefficient(self, val: float):
        """Set shunt temperature coefficient (relative to 25°C)"""
        self.TEMPCO = val

    def set_alt_mode(self, val: str):
        """Set alternative channels order"""
        amode = val.lower()
        if amode == 'cv': # default current, voltage mode with chip temperature in the third channel
            self.CHAN_REMAP = None
            return True
        if amode == 'vt': # voltage, temperature mode with current in the third channel
            self.CHAN_REMAP = (1, 2, 0)
            return True
        if amode == 'tc': # temperature, current mode with voltage in the third channel
            self.CHAN_REMAP = (2, 0, 1)
            return True
        if amode == 'ktv': # K termocouple temperature, voltage mode with chip temperature in the third channel
            self.CHAN_REMAP = (self.KTC_CHAN, 1, 2)
            return True
        if amode == 'ktt': # K termocouple temperature, chip temperature mode with voltage in the third channel
            self.CHAN_REMAP = (self.KTC_CHAN, 2, 1)
            return True
        return False

    def set_param(self, key: str, val: str|float) -> bool:
        """
        Set device specific parameter.
        Returns True if key / val pair is recognized, False otherwise.
        """
        lkey = key.lower()
        try:
            if lkey == 'range':
                self.set_shunt_voltage_range(int(val))
                return True
            if lkey == 'tempco':
                self.set_shunt_temp_coefficient(float(val))
                return True
            if lkey == 'amode':
                return self.set_alt_mode(val)
        except Exception as e:
            log.debug(e, exc_info=True)
            return False
        return super().set_param(key, val)

    def query_raw(self, idle_sleep=None) -> Any|None:
        """
        Query raw data from device. Here we ignore timeout and idle callback args since
        I2C HID adapter normally responds without long waiting. Therefore calling callback
        here will just slow down readout without any benefits.
        """
        if not self.is_connected():
            return None
        read_channels = self.channels if self.CHAN_REMAP is None and not self.TEMPCO else self.NCHANNELS
        try:
            if not self.adapter.i2c_write(self.I2C_ADDR, [4]): # set VSHUNT target register address
                return None
            if (idata := self.adapter.i2c_read(self.I2C_ADDR, 3)) is None:
                return None
            idata += b'\0' # extend it to 32 bits to simplify conversion
            if read_channels < 2:
                return (bytes(idata),)
            if not self.adapter.i2c_write(self.I2C_ADDR, [5]): # set VBUS target register address
                return None
            if (vdata := self.adapter.i2c_read(self.I2C_ADDR, 3)) is None:
                return None
            vdata += b'\0' # extend it to 32 bits to simplify conversion
            if read_channels < 3:
                return (bytes(idata), bytes(vdata))
            if not self.adapter.i2c_write(self.I2C_ADDR, [6]): # set DIETEMP target register address
                return None
            if (tdata := self.adapter.i2c_read(self.I2C_ADDR, 2)) is None:
                return None
            return (bytes(idata), bytes(vdata), bytes(tdata))
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)
            return None        

    def get_mode(self, data, channel: int = 0) -> str:
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        if self.CHAN_REMAP:
            channel = self.CHAN_REMAP[channel]
        return ('A', 'V', '°C', '°C')[channel]

    def raw_chan_value(self, data, channel: int) -> float:
        """Extract readout channel value from raw data"""
        if channel < 2:
            val = struct.unpack('>i', data[channel])[0]
            return val * ((self.CURR0_LSB if not self.RANGE else self.CURR1_LSB), self.VOLT_LSB)[channel] / (256 * 16)
        else:
            val = struct.unpack('>h', data[channel])[0]
            return val * self.TEMP_LSB

    def get_value(self, data, channel: int = 0) -> float:
        """Converts raw data to the floating point value"""
        if not data:
            return Device.INVALID_VALUE
        if self.CHAN_REMAP:
            channel = self.CHAN_REMAP[channel]
        if channel == self.KTC_CHAN:
            return tc.K_delta_mv2C(self.raw_chan_value(data, self.CURR_CHAN) * 1000, self.raw_chan_value(data, self.TEMP_CHAN))
        val = self.raw_chan_value(data, channel)
        if channel == self.CURR_CHAN:
            val /= self.SHUNT_RES
            if self.TEMPCO:
                temp = self.raw_chan_value(data, self.TEMP_CHAN)
                val += val * (temp - 25) * self.TEMPCO
        return val


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG) 
    devT = INA228Device if '--228' in sys.argv[1:] else INA226Device    
    if dev := devT.set_i2c_adapter(CP2112Adapter if '--2112' in sys.argv[1:] else FT260Adapter).open():
        print(dev)
        with dev:
            dev.init()
            while dev.is_connected():
                data = dev.query_raw()
                print(data, end = '\t')
                for c in range(dev.NCHANNELS):
                    print(dev.get_value(data, c), dev.get_mode(data, c), end = '\t')
                print()
