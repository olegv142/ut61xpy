"""
Adapters communicating with device by SCPI commands.
Currently tested only with OWON multimeters and programmable
power supplies.
"""

import os
import sys
import time
import logging

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from device import CDCMixin, Device

log = logging.getLogger('DEV')

class SCPIDevice(CDCMixin, Device):
    """Base class for adapters using SCPI commands over CDC link"""
    TOUT = 1
    EOL_SYMBOL = b'\n'
    IDLE_DELAY = .01

    def __init__(self, *args):
        super().__init__(*args)
        self.model = None

    def get_model(self):
        """The implementation may redefine this method to return actual model name"""
        if self.model:
            return self.model
        if resp := self.scpi_call(b'*IDN?'):
            self.model = b' '.join(resp.split(b',')[:2]).decode('ascii')
            return self.model
        else:
            self.disconnected = True
            return self.MODEL_NAME

    def scpi_send(self, cmd):
        try:
            self.dev.write(cmd + self.EOL_SYMBOL)
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)

    def scpi_receive(self, idle_sleep=time.sleep):
        wait = self.TOUT
        resp = bytes()
        while True:
            idle_sleep(self.IDLE_DELAY)
            try:
                rd = self.dev.read(64)
            except Exception as e:
                self.disconnected = True
                log.debug(e, exc_info=True)
                return None
            if rd:
                resp += rd
                if resp[-1:] == self.EOL_SYMBOL:
                    return resp.strip().strip(b'"')
            wait -= self.IDLE_DELAY
            if wait <= 0:
                return None

    def scpi_call(self, cmd, idle_sleep=time.sleep):
        self.scpi_send(cmd)
        return self.scpi_receive(idle_sleep)

    def scpi_query(self, cmd, idle_sleep=time.sleep):
        sval = self.scpi_call(cmd, idle_sleep)
        if not sval:
            return None
        try:
            return float(sval)
        except ValueError:
            return Device.INVALID_VALUE

class SCPIDmm(SCPIDevice):
    """SCPI multimeter interface adapter. Tested with OWON XDM1241."""
    MODEL_NAME  = 'SCPI-DMM'
    # CH340 USB-serial chip
    DEVICE_VID = 0x1a86
    DEVICE_PID = 0x7523

    NO_VALUE = b'NONe'
    DEF_MODE = 'DUTY%'
    OVERLOAD_VAL = 1e9

    def __init__(self, *args):
        super().__init__(*args)
        self.channels = None
        self.modes = None

    def init(self, nchannels=1):
        """
        Initialize device setting the number of channels we are going the read.
        Should be called before first query_raw call.
        """
        assert nchannels in (1, 2)
        self.channels = nchannels
        funcs = [self.scpi_call(b'FUNC%d?' % (i+1)) for i in range(nchannels)]
        self.modes = [f.decode('ascii') if f and f != self.NO_VALUE else self.DEF_MODE for f in funcs]

    def query_raw(self, idle_sleep=time.sleep):
        """Queries raw data from device"""
        if not self.is_connected():
            return None
        resp = self.scpi_call(b'MEAS?', idle_sleep)
        if not resp:
            return None
        vals = resp.split(b',')
        if len(vals) < self.channels:
            if val2 := self.scpi_call(b'MEAS2?', idle_sleep):
                vals.append(val2)
        return vals

    def get_channels(self, data):
        if not data:
            return 0
        return min(self.channels, len(data))

    def get_value(self, data, channel=0):
        if not data:
            return Device.INVALID_VALUE
        try:
            val = float(data[channel])
            if val == self.OVERLOAD_VAL:
                return Device.INVALID_VALUE
            return val
        except ValueError:
            return Device.INVALID_VALUE

    def get_mode(self, data, channel=0):
        if not data:
            return ''
        return self.modes[channel]

class SCPIPowerSource(SCPIDevice):
    """
    SCPI programmable power supplies interface adapter. Tested with OWON SPE3051.
    It always measures current in the main channel and voltage in the secondary one.
    """
    MODEL_NAME  = 'SCPI-CV'
    # CH340 USB-serial chip
    DEVICE_VID = 0x1a86
    DEVICE_PID = 0x7523
    # Channel names for convenience
    CURR_CHAN = 0
    VOLT_CHAN = 1

    def __init__(self, *args):
        super().__init__(*args)
        self.channels = None

    def init(self, nchannels=1):
        """
        Initialize device setting the number of channels we are going the read.
        Should be called before first query_raw call.
        """
        assert nchannels in (1, 2)
        self.channels = nchannels

    def query_raw(self, idle_sleep=time.sleep):
        """Queries raw data from device"""
        if not self.is_connected():
            return None
        if self.channels < 2:
            resp = self.scpi_call(b'MEAS:CURR?', idle_sleep)
            return (resp,) if resp else None
        resp = self.scpi_call(b'MEAS:ALL?', idle_sleep)
        if not resp:
            return None
        return tuple(reversed(resp.split(b',')[:2]))

    def get_channels(self, data):
        if not data:
            return 0
        return min(self.channels, len(data))

    def get_value(self, data, channel=0):
        if not data:
            return Device.INVALID_VALUE
        try:
            return float(data[channel])
        except ValueError:
            return Device.INVALID_VALUE

    def get_mode(self, data, channel=0):
        if not data:
            return ''
        return ('CURR', 'VOLT')[channel]
