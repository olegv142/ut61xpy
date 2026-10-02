"""
FNIRSI USB testers communication adapter
The protocol details are taken from https://github.com/yeckel/OpenFNB58 project
"""

import os
import sys
import time
import logging
import struct

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

import bt_engine
from device import Device, HIDMixin, BTMixin

log = logging.getLogger('DEV')

class FnirsiUsbDevice(HIDMixin, Device):
    """USB HID adapter for FNIRSI USB testers"""
    CMD_INIT  = [0xaa, 0x81] + [0] * 61 + [0x8e]
    CMD_START = [0xaa, 0x82] + [0] * 61 + [0x96]
    CMD_POLL  = [0xaa, 0x83] + [0] * 61 + [0x9e]

    CMD_INTERVAL = 0.05
    IDLE_DELAY   = 0.05
    DEF_TOUT     = 4  # default timeout in seconds

    # Channel names for convenience
    CURR_CHAN = 0
    VOLT_CHAN = 1

    def __init__(self, dev, path):
        Device.__init__(self, path)
        self.dev = dev
        self.channels = None
        self.disconnected = False

    def is_connected(self):
        return self.dev and not self.disconnected

    def send_cmd(self, cmd):
        self.dev.write([0] + cmd)

    def init(self, nchannels=1):
        """
        Initialize device setting the number of channels we are going the read.
        Should be called before first query_raw call.
        """
        self.channels = nchannels
        try:
            self.send_cmd(self.CMD_INIT)
            time.sleep(self.CMD_INTERVAL)
            self.send_cmd(self.CMD_START)
            time.sleep(self.CMD_INTERVAL)
        except Exception as e:
            self.disconnected = True
            log.debug(e)

    def get_channels(self, data):
        """Get the number of channels contained in the raw data"""
        if not data:
            return 0
        return self.channels

    def query_raw(self, tout=None, idle_sleep=time.sleep):
        """Queries raw data packet from HID device"""
        wait = tout if tout is not None else self.DEF_TOUT
        try:
            self.send_cmd(self.CMD_POLL)
            while True:
                idle_sleep(self.IDLE_DELAY)
                buf = self.dev.read(64)
                if buf and buf[0] == 0xaa and buf[1] == 4:
                    break
                wait -= self.IDLE_DELAY
                if wait <= 0:
                    return None
        except Exception as e:
            self.disconnected = True
            log.debug(e)
            return None
        return bytes(buf[2:])

    @staticmethod
    def _get_samples(data, off):
        return [struct.unpack_from('<I', data, 15*i + off)[0] / 100000 for i in range(4)]

    def get_value(self, data, channel=0):
        """Converts raw data to the floating point value"""
        if not data:
            return Device.INVALID_VALUE
        samples = self._get_samples(data, (4, 0)[channel])
        return sum(samples) / len(samples)

    def get_mode(self, data, channel=0):
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        return ('A', 'V')[channel]

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        self.dev.close()
        self.dev = None


class FnirsiBtDevice(BTMixin, Device):
    """BLE adapter for FNIRSI USB testers"""
    BT_RX_CHAR = 'FFE4'
    BT_TX_CHAR = 'FFE9'
    CMD_INIT   = [0xaa, 0x81, 0, 0xf4]
    CMD_START  = [0xaa, 0x82, 0, 0xa7]
    IDLE_DELAY = .1
    DEF_TOUT   = 4  # default timeout in seconds

    # Channel names for convenience
    CURR_CHAN = 0
    VOLT_CHAN = 1

    def __init__(self, dev, addr):
        Device.__init__(self, addr)
        self.dev = dev
        self.channels = None
        self.last_data = None

    def is_connected(self):
        return self.dev.is_connected

    def init(self, nchannels=1):
        """
        Initialize device setting the number of channels we are going the read.
        Should be called before first query_raw call.
        """
        self.channels = nchannels
        async def a_init():
            await self.dev.write_gatt_char(self.BT_TX_CHAR, bytearray(self.CMD_INIT),  response=True)
            await self.dev.write_gatt_char(self.BT_TX_CHAR, bytearray(self.CMD_START), response=True)
        bt_engine.async_exec(a_init())

    def get_channels(self, data):
        """Get the number of channels contained in the raw data"""
        if not data:
            return 0
        return self.channels

    def _notify_cb(self, char, val):
        """BT adapter data changed notification callback"""
        n, i = len(val), 0
        while True:
            if i == n:
                return
            if i + 2 >= n or val[i] != 0xaa:
                log.debug('bad packet: %s', val)
                return
            tag, sz = val[i+1], val[i+2]
            if i + sz + 4 > n:
                log.debug('bad packet: %s', val)
                return
            elif tag == 7 and sz >= 4:
                self.last_data = val[i + 3: i + 3 + sz]
            i += sz + 4

    @classmethod
    def open_addr(cls, addr):
        """Opens BT device given its mac address"""
        from bleak import BleakClient
        clnt = BleakClient(addr)
        inst = cls(clnt, addr)
        async def a_connect():
            await clnt.connect()
            if clnt.is_connected:
                await clnt.start_notify(cls.BT_RX_CHAR, inst._notify_cb)
        bt_engine.async_exec(a_connect())
        if not clnt.is_connected:
            log.error('failed to connect to %s BT device %s', cls.MODEL_NAME, addr)
            return None
        return inst

    def query_raw(self, tout=None, idle_sleep=time.sleep):
        """Queries raw data packet from BT device"""
        if not self.dev.is_connected:
            return None
        wait = tout if tout is not None else self.DEF_TOUT
        while self.last_data is None and wait >= 0:
            idle_sleep(self.IDLE_DELAY)
            wait -= self.IDLE_DELAY
        if not self.last_data:
            return None
        data, self.last_data = self.last_data, None
        return data

    def get_value(self, data, channel=0):        
        """Converts raw data to the floating point value"""
        if not data:
            return Device.INVALID_VALUE
        return struct.unpack_from('<H', data, (2, 0)[channel])[0] / 1000

    def get_mode(self, data, channel=0):
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        return ('A', 'V')[channel]

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        bt_engine.async_exec(self.dev.disconnect())
        self.dev = None


class FNB48pUsb(FnirsiUsbDevice):
    DEVICE_VID = 0x2e3c
    DEVICE_PID = 0x0049
    MODEL_NAME = 'FNB48P'

class FNB58Usb(FnirsiUsbDevice):
    DEVICE_VID = 0x2e3c
    DEVICE_PID = 0x5558
    MODEL_NAME = 'FNB58'

class FNB48pBt(FnirsiBtDevice):
    MODEL_NAME = 'FNB48P'
    DEVICE_NAME = 'FNB48*'

class FNB58Bt(FnirsiBtDevice):
    MODEL_NAME = 'FNB58'
    DEVICE_NAME = 'FNB58*'

class FNAC28(FnirsiUsbDevice):
    DEVICE_VID = 0x0483
    DEVICE_PID = 0x003B
    MODEL_NAME = 'FNAC28'

class FNBC2(FnirsiUsbDevice):
    DEVICE_VID = 0x2e3c
    DEVICE_PID = 0x5558
    MODEL_NAME = 'FNB-C2'

if __name__ == '__main__':
    if '--bt' in sys.argv[1:]:
        devT = FNB48pBt if '--48' in sys.argv[1:] else FNB58Bt
    else:
        devT = FNB48pUsb if '--48' in sys.argv[1:] else FNAC28 if '--28' in sys.argv[1:] else FNB58Usb
    if dev := devT.open():
        print(dev)
        with dev:
            dev.init(2)
            while dev.is_connected():
                data = dev.query_raw()
                print(dev.get_value(data, 0), dev.get_mode(data, 0), dev.get_value(data, 1), dev.get_mode(data, 1))

