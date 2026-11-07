"""
Bases classes for devices using I2C communication bus
"""

import os
import sys
import logging
from typing import Any

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from device import Device, HIDMixin
import ft260
import cp2112
import ch347t

log = logging.getLogger('DEV')

class I2CAdapter:
    """Base class for I2C adapters"""
    # The following should be defined in subclasses
    DEVICE_VID = None
    DEVICE_PID = None
    DEVICE_IFN = None
    NAME = None

    def __init__(self, dev):
        """Initialize I2C bus"""
        raise NotImplementedError()

    def i2c_probe(self, addr: int) -> bool:
        """Check the device presence at given address"""
        raise NotImplementedError()

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        """Write data bytes to I2C given target address"""
        raise NotImplementedError()

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        """Read data bytes from I2C given target address"""
        raise NotImplementedError()

    def i2c_write_read(self, addr: int, wr_data: list[int], rd_length: int) -> list[int]|None:
        """Write and read in single I2C transaction"""
        raise NotImplementedError()

class FT260Adapter(I2CAdapter):
    """FTDI FT260 I2C adapter class"""
    DEVICE_VID = ft260.DEVICE_VID
    DEVICE_PID = ft260.DEVICE_PID
    NAME = 'FT260'

    def __init__(self, dev):
        self.dev = dev
        ft260.i2c_init(self.dev)

    def i2c_probe(self, addr: int) -> bool:
        return ft260.i2c_probe(self.dev, addr)

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        return ft260.i2c_write(self.dev, addr, data)

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        return ft260.i2c_read(self.dev, addr, length)

    def i2c_write_read(self, addr: int, wr_data: list[int], rd_length: int) -> list[int]|None:
        return ft260.i2c_write_read(self.dev, addr, wr_data, rd_length)

class CP2112Adapter(I2CAdapter):
    """Silicon Labs CP2112 I2C adapter class"""
    DEVICE_VID = cp2112.DEVICE_VID
    DEVICE_PID = cp2112.DEVICE_PID
    NAME = 'CP2112'

    def __init__(self, dev):
        self.dev = dev
        cp2112.i2c_init(self.dev)

    def i2c_probe(self, addr: int) -> bool:
        return cp2112.i2c_probe(self.dev, addr)

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        return cp2112.i2c_write(self.dev, addr, data)

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        return cp2112.i2c_read(self.dev, addr, length)

    def i2c_write_read(self, addr: int, wr_data: list[int], rd_length: int) -> list[int]|None:
        return cp2112.i2c_write_read(self.dev, addr, wr_data, rd_length)

class CH347TAdapter(I2CAdapter):
    """CH347T I2C adapter class"""
    DEVICE_VID = ch347t.DEVICE_VID
    DEVICE_PID = ch347t.DEVICE_PID
    DEVICE_IFN = ch347t.DEVICE_IFN
    NAME = 'CH347T'

    def __init__(self, dev):
        self.dev = dev
        ch347t.i2c_init(self.dev)

    def i2c_probe(self, addr: int) -> bool:
        return ch347t.i2c_probe(self.dev, addr)

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        return ch347t.i2c_write(self.dev, addr, data)

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        return ch347t.i2c_read(self.dev, addr, length)

    def i2c_write_read(self, addr: int, wr_data: list[int], rd_length: int) -> list[int]|None:
        return ch347t.i2c_write_read(self.dev, addr, wr_data, rd_length)

class I2CDeviceCore(Device, HIDMixin):
    """Base class for devices using I2C communication bus"""
    I2C_ADAPTER_TYPE = FT260Adapter # default i2c adapter
    DEVICE_VID = I2C_ADAPTER_TYPE.DEVICE_VID
    DEVICE_PID = I2C_ADAPTER_TYPE.DEVICE_PID
    DEVICE_IFN = I2C_ADAPTER_TYPE.DEVICE_IFN

    def __init__(self, *args):
        super().__init__(*args)
        self.adapter = None

    @classmethod
    def set_i2c_adapter(cls, T):
        cls.I2C_ADAPTER_TYPE = T
        cls.DEVICE_VID = T.DEVICE_VID
        cls.DEVICE_PID = T.DEVICE_PID
        cls.DEVICE_IFN = T.DEVICE_IFN
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
            for T in (FT260Adapter, CP2112Adapter, CH347TAdapter):
                if uval == T.NAME:
                    cls.set_i2c_adapter(T)
                    return True
            return False
        return super().set_model_param(key, val)

    def init(self, nchannels: int = 0):
        if self.adapter is None:
            self.adapter = self.I2C_ADAPTER_TYPE(self.dev)

    @classmethod
    def model_info(cls) -> str:
        """The implementation may redefine this method to provide extended information"""
        return cls.MODEL_NAME + '-' + cls.I2C_ADAPTER_TYPE.NAME

class I2CBusScanner(I2CDeviceCore):
    """The sole purpose of this device class is to scan I2C bus addresses"""
    MODEL_NAME = 'I2C'
    def scan(self):
        for addr in range(8, 128):
            print(('%02x ' % addr) if self.adapter.i2c_probe(addr) else '-- ', end='' if (addr + 1) % 8 else '\n')

class I2CDevice(I2CDeviceCore):
    """Base class for devices using I2C communication bus"""
    I2C_ADDR = None # must be redefined in subclasses

    def __init__(self, *args):
        super().__init__(*args)
        self.channels = None

    def set_i2c_addr(self, addr: int):
        """Set target device address on I2C bus"""
        self.I2C_ADDR = addr

    def set_param(self, key: str, val: str|float) -> bool:
        """
        Set device specific parameter.
        Returns True if key / val pair is recognized, False otherwise.
        """
        try:
            if key.lower() == 'addr':
                self.set_i2c_addr(int(val, 0))
                return True
        except Exception as e:
            log.debug(e, exc_info=True)
            return False
        return super().set_param(key, val)

    def init(self, nchannels: int):
        """
        Initialize device setting the number of channels we are going the read.
        Should be called before first query_raw call.
        """
        super().init(nchannels)
        self.channels = nchannels

    @classmethod
    def attach_to_i2c_bus(cls, master: 'I2CDevice') -> 'I2CDevice':
        """
        Create device attaching it to already initialized I2C bus.
        The master device init() should be already called at this point.
        """
        assert isinstance(master, I2CDevice)
        assert master.adapter is not None
        dev = cls(master.dev, master.path)
        dev.adapter = master.adapter
        return dev

    def get_channel(self, data: Any) -> int | None:
        """
        Returns the index of the channel the data belongs to. If there are multiple
        channels contained in the data, it returns -1. It there are no data, it returns None.
        """
        if not data:
            return None
        return -1 if self.channels > 1 else 0
