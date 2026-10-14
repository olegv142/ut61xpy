"""
Adapters for TI INA226 and INA228 current & voltage monitors
"""

import os
import sys
import time
import logging
import struct
from typing import Any
from collections.abc import Callable

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from device import Device, HIDMixin
import ft260
import cp2112
import termocouple as tc

log = logging.getLogger('DEV')

class I2CAdapter:
    """Base class for I2C adapters"""
    # The following should be defined in subcasses
    DEVICE_VID = None
    DEVICE_PID = None

    def __init__(self, dev):
        """Initialize I2C bus"""
        raise NotImplementedError()

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        """Write data bytes to I2C given target address"""
        raise NotImplementedError()

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        """Read data bytes from I2C given target address"""
        raise NotImplementedError()

class FT260Adapter(I2CAdapter):
    """FTDI FT260 I2C adapter class"""
    DEVICE_VID = ft260.DEVICE_VID
    DEVICE_PID = ft260.DEVICE_PID

    def __init__(self, dev):
        self.dev = dev
        ft260.i2c_init(self.dev)

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        return ft260.i2c_write(self.dev, addr, data)

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        return ft260.i2c_read(self.dev, addr, length)

class CP2112Adapter(I2CAdapter):
    """Silicon Labs CP2112 I2C adapter class"""
    DEVICE_VID = cp2112.DEVICE_VID
    DEVICE_PID = cp2112.DEVICE_PID

    def __init__(self, dev):
        self.dev = dev
        cp2112.i2c_init(self.dev)

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        return cp2112.i2c_write(self.dev, addr, data)

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        return cp2112.i2c_read(self.dev, addr, length)

class INADevice(Device, HIDMixin):
    """Base class for INAxxx current and voltage monitors"""
    SHUNT_RES = .1
    # default i2c adapter
    I2C_ADAPTER_TYPE = FT260Adapter
    DEVICE_VID = I2C_ADAPTER_TYPE.DEVICE_VID
    DEVICE_PID = I2C_ADAPTER_TYPE.DEVICE_PID

    # Channel names for convenience
    CURR_CHAN = 0
    VOLT_CHAN = 1
    NCHANNELS = 2

    def __init__(self, *args):
        super().__init__(*args)
        self.channels = None
        self.adapter = None

    @classmethod
    def set_i2c_adapter(cls, T):
        cls.I2C_ADAPTER_TYPE = T
        cls.DEVICE_VID = T.DEVICE_VID
        cls.DEVICE_PID = T.DEVICE_PID
        return cls

    @classmethod
    def set_model_param(cls, key: str, val: str) -> bool:
        """
        Set model specific parameter.
        Returns True if key / val pair is recognized, False otherwise.
        """
        lkey = key.lower()
        if lkey == 'i2c':
            uval = val.upper()
            if uval == 'FT260':
                cls.set_i2c_adapter(FT260Adapter)
                return True
            if uval == 'CP2112':
                cls.set_i2c_adapter(CP2112Adapter)
                return True
        return super().set_model_param(key, val)

    def init(self, nchannels: int = 1):
        """
        Initialize device setting the number of channels we are going the read.
        Should be called before first query_raw call.
        """
        self.channels = nchannels
        self.adapter = self.I2C_ADAPTER_TYPE(self.dev)

    def get_channels(self, data: Any) -> int:
        """Get the number of channels contained in the raw data"""
        if not data:
            return 0
        return self.channels

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
        return Device.set_param(self, key, val)

    def get_mode(self, data, channel: int = 0) -> str:
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        return ('A', 'V')[channel]

class INA226Device(INADevice):
    """INA226 16bit current and voltage monitor base class"""
    MODEL_NAME = 'INA226'
    I2C_ADDR = 64
    CURR_LSB = 2.5e-6
    VOLT_LSB = 1.25e-3

    def init(self, nchannels: int = 1):
        INADevice.init(self, nchannels)
        # Set 4 msec conversion time and 4 samples averaging
        self.adapter.i2c_write(self.I2C_ADDR, [0, 0x43, 0xB7])

    def query_raw(self, idle_sleep=time.sleep) -> Any|None:
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
        INADevice.init(self, nchannels)
        self.adapter.i2c_write(self.I2C_ADDR, [0, 0, 0 if not self.RANGE else 0x10])
        # Set 4 msec conversion time and 4 samples averaging
        self.adapter.i2c_write(self.I2C_ADDR, [1, 0xFF, 0xF9])

    def set_shunt_voltage_range(self, val: int):
        """Set shunt voltage range (0 = ±163.84mV, 1 = ± 40.96mV)"""
        self.RANGE = val

    def set_shunt_temp_coefficient(self, val: float):
        """Set shunt temperature coefficient (relative to 25°C)"""
        self.TEMPCO = val

    def set_alt_mode(self, val: str):
        """Set alternative channels order"""
        amode = val.lower()
        if amode == 'cv': # default current, voltage mode with temperature in the third channel
            self.CHAN_REMAP = None
            return True
        if amode == 'vt': # voltage, temperature mode with current in the third channel
            self.CHAN_REMAP = (1, 2, 0)
            return True
        if amode == 'tc': # temperature, current mode with voltage in the third channel
            self.CHAN_REMAP = (2, 0, 1)
            return True
        if amode == 'ktv': # K termocouple temperature, voltage mode
            self.CHAN_REMAP = (self.KTC_CHAN, 1)
            return True

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
        return INADevice.set_param(self, key, val)

    def query_raw(self, idle_sleep=time.sleep) -> Any|None:
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
            dev.init(dev.NCHANNELS)
            while dev.is_connected():
                data = dev.query_raw()
                print(data, end = '\t')
                for c in range(dev.NCHANNELS):
                    print(dev.get_value(data, c), dev.get_mode(data, c), end = '\t')
                print()
