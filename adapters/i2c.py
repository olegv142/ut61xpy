"""
Bases classes for devices using I2C communication bus
"""

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from device import Device, HIDMixin
import ft260
import cp2112

class I2CAdapter:
    """Base class for I2C adapters"""
    # The following should be defined in subcasses
    DEVICE_VID = None
    DEVICE_PID = None
    NAME = None

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
    NAME = 'FT260'

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
    NAME = 'CP2112'

    def __init__(self, dev):
        self.dev = dev
        cp2112.i2c_init(self.dev)

    def i2c_write(self, addr: int, data: list[int]) -> bool:
        return cp2112.i2c_write(self.dev, addr, data)

    def i2c_read(self, addr: int, length: int) -> list[int]|None:
        return cp2112.i2c_read(self.dev, addr, length)

class I2CDevice(Device, HIDMixin):
    """Base class for devices using I2C communication bus"""
    I2C_ADAPTER_TYPE = FT260Adapter # default i2c adapter
    DEVICE_VID = I2C_ADAPTER_TYPE.DEVICE_VID
    DEVICE_PID = I2C_ADAPTER_TYPE.DEVICE_PID

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
            for T in (FT260Adapter, CP2112Adapter):
                if uval == T.NAME:
                    cls.set_i2c_adapter(T)
                    return True
        return super().set_model_param(key, val)

    @classmethod
    def model_info(cls) -> str:
        """The implementation may redefine this method to provide extended information"""
        return cls.MODEL_NAME + '-' + cls.I2C_ADAPTER_TYPE.NAME

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
