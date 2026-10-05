"""
OWON digital multimeters communication adapter
"""

import os
import sys
import time
import logging

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

import bt_engine
from device import Device, BTMixin

log = logging.getLogger('DEV')

class OwonBtDevice(BTMixin, Device):
    """OWON Bluetooth multimeter interface class"""
    MODEL_NAME  = 'OWON'
    DEVICE_NAME = 'BDM'
    BT_RX_CHAR  = 'FFF4'
    DATA_LEN    = 6 # data response packet length
    TOUT        = 4 # default timeout in seconds
    IDLE_DELAY  = .1

    def __init__(self, *args):
        super().__init__(*args)
        self.last_data = None

    def _notify_cb(self, char, val):
        """BT adapter data changed notification callback"""
        if len(val) == self.DATA_LEN:
            self.last_data = val

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

    def query_raw(self, idle_sleep=time.sleep):
        """Queries raw data packet from BT device"""
        if not self.is_connected():
            return None
        wait = self.TOUT
        while self.last_data is None and wait >= 0:
            idle_sleep(self.IDLE_DELAY)
            wait -= self.IDLE_DELAY
        if not self.last_data:
            return None
        data, self.last_data = self.last_data, None
        return data

    def get_value(self, data, channel=None):
        """
        Converts raw data to the floating point value. Here we don't
        care about units since the caller should be aware of them.
        It set mode dial manually after all. So in the mV mode the
        result is expressed in mV rather than volts.
        """
        if not data:
            return Device.INVALID_VALUE
        mt = self.mode_tag(data)
        _, scale = self._scale_map.get(mt, (mt, 0))
        shift = data[0] & 7
        if shift == 7:
            return Device.INVALID_VALUE
        val = data[-2] + 256 * (data[-1] & 0x7f)
        if data[-1] & 0x80:
            val = -val
        return val * (.1 ** (shift - scale))

    @staticmethod
    def mode_tag(data):
        return (data[0] & 0xF8) + (data[1] & 0x7)

    _mode_map = {
        0x18 : 'dc mV',
        0x20 : 'dc V',
        0x58 : 'ac mV',
        0x60 : 'ac V',
        0xe0 : 'ac A',
        0xa0 : 'dc A',
        0x63 : 'NCV',
        0x31 : 'MOhm',
        0x29 : 'kOhm',
        0x21 : 'Ohm',
        0x49 : 'nF',
        0x51 : 'µF',
        0xa2 : 'diode V',
        0xe2 : 'Ohm',
        0xa1 : 'Hz',
        0xa9 : 'kHz',
        0xb1 : 'MHz',
        0xe1 : 'duty %',
        0xc1 : 'duty %',
        0x22 : '°C',
        0x62 : '°F',
        0x90 : 'dc µA',
        0xd0 : 'ac µA',
        0x98 : 'dc mA',
        0xd8 : 'ac mA',
        0x23 : 'hFE',
    }

    _scale_map = {
        0x18 : (0x20, -3), # dc mV -> dc V
        0x58 : (0x60, -3), # ac mV -> ac V
        0x31 : (0x21, 6),  # MOhm -> Ohm
        0x29 : (0x21, 3),  # kOhm -> Ohm
        0x51 : (0x49, 3),  # µF   -> nF
        0xa9 : (0xa1, 3),  # kHz  -> Hz
        0xb1 : (0xa1, 6),  # MHz  -> Hz
    }

    def get_mode(self, data, channel=None):
        """
        Returns measurement mode and units description string.
        """
        if not data:
            return ''
        mt = self.mode_tag(data)
        # Different vendors use different approaches to reporting measurement mode. The UNI-T reports
        # mode set by user. OWON reports units chosen by auto-range (say millivolts) within the mode
        # set by user (say voltage). So the units may be voluntary switched right in the middle of the
        # data collection which is quite undesirable. Therefore we first map current units to some
        # 'base units' by _scale_map and then retrieve the corresponding label from _mode_map.
        mt, _ = self._scale_map.get(mt, (mt, 0))
        mode  = self._mode_map.get(mt, '')
        flags = data[2]
        if flags & 1:
            mode += ' Hold'
        if flags & 2:
            mode += ' Rel'
        if flags & 0x10:
            mode += ' Min'
        if flags & 0x20:
            mode += ' Max'
        if flags & 8:
            mode += ' LoBatt'
        return mode

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        bt_engine.async_exec(self.dev.disconnect())
        self.dev = None

if __name__ == '__main__':
    try:
        dev = OwonBtDevice.open()
        if dev:
            with dev:
                last_data = None
                while dev.is_connected():
                    data = dev.query_raw()
                    if data:
                        if last_data is None: print()
                        print(' '.join(['%02x' % b for b in data]), 'm%02x' % dev.mode_tag(data), '=', dev.get_value(data), dev.get_mode(data))
                    else:
                        print('.', end='', flush=True)
                    last_data = data
    except KeyboardInterrupt:
        pass
