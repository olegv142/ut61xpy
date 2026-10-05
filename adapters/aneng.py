"""
ANENG digital multimeter communication adapter
Supports AN9002 model also sold as ZOTEK/BSIDE ZT-300AB
"""

import os
import sys
import time
import logging

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

import bt_engine
from device import Device, BTMixin

log = logging.getLogger('DEV')

class AnengBtDevice(BTMixin, Device):
    """
    Bluetooth multimeter interface class for Aneng AN9002 also sold as ZOTEK/BSIDE ZT-300AB.
    The Zotek/Aneng multimeters uses display segment based encoding for BT communications.
    So there are as many protocol variants as there are displays in use. Therefore this
    adapter class will not work with other 'Bluetooth DMM' devices like ZT-5B, ZT-5BQ, ZT-5566.
    Yet the AN9002 is the most interesting model considering the ergonomics and price / performance.
    """
    MODEL_NAME  = 'ANENG'
    DEVICE_NAME = 'Bluetooth DMM'
    BT_RX_CHAR  = 'FFF4'
    DATA_LEN    = 11 # data response packet length
    TOUT        = 4  # default timeout in seconds
    DATA_PREFIX = [0x5a, 0xa5, 0x3]
    XOR_KEY     = [0x41, 0x21, 0x73, 0x55, 0xa2, 0xc1, 0x32, 0x71, 0x66, 0xaa, 0x3b]
    IDLE_DELAY  = .1
    #
    # There is a direct mapping between BT packet bits and DMM display segments
    # as described in https://github.com/ludwich66/Bluetooth-DMM/wiki
    # So we have to map 7seg codes back to decimal digits
    _d = 1
    _c = 2
    _g = 4
    _b = 8
    _e = 0x20
    _f = 0x40
    _a = 0x80
    _all = _a + _b + _c + _d + _e + _f + _g
    _dp = 0x10

    DIGIT_MAP = {
        _all - _g           : '0',
        _b + _c             : '1',
        _all - _c - _f      : '2',
        _all - _e - _f      : '3',
        _all - _a - _d - _e : '4',
        _all - _b - _e      : '5',
        _all - _b           : '6',
        _a + _b + _c        : '7',
        _all                : '8',
        _all - _e           : '9'
    }

    def __init__(self, dev, addr):
        BTMixin.__init__(self, dev, addr)
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
        data = [data[i] ^ self.XOR_KEY[i] for i in range(self.DATA_LEN)]
        if data[:3] != self.DATA_PREFIX:
            log.debug('bad prefix: %s', data)
        return data[3:]

    def get_value(self, data, channel=None):
        """
        Converts raw data to the floating point value.
        """
        if not data:
            return Device.INVALID_VALUE
        digit_codes = [
            (data[0] & 0xf0) | (data[1] & 0xf),
            (data[1] & 0xf0) | (data[2] & 0xf),
            (data[2] & 0xf0) | (data[3] & 0xf),
            (data[3] & 0xf0) | (data[4] & 0xf)
        ]
        dp = self._dp
        dp_mask = 0xff ^ dp
        val_str = '-' if digit_codes[0] & dp else ''
        digit_codes[0] &= dp_mask
        for c in digit_codes:
            if c & dp:
                val_str += '.'
            val_str += self.DIGIT_MAP.get(c & dp_mask, '?')
        try:
            val = float(val_str)
        except ValueError:
            return Device.INVALID_VALUE
        # Apply scale to some auto ranged values, Ohm and nF in particular.
        # We don't want the units and hence the value scale to be voluntary changed
        # as a result of auto range selection.
        if data[6] & 4:
            val *= 1e3 # kOhm
        elif data[6] & 8:
            val *= 1e6 # MOhm
        if data[5] & 0x20:
            val *= 1e3 # µF
        elif data[5] & 0x40:
            val *= 1e6 # mF
        return val

    def get_mode(self, data, channel=None):
        """
        Returns measurement mode and units description string.
        """
        if not data:
            return ''
        mode = ''
        if data[5] & 8:
            mode += 'ac '
        if data[6] & 0x40:
            mode += 'dc '
        if data[4] & 0x80:
            mode += 'diode '

        if data[6] & 0x20:
            mode += 'm'
        if data[6] & 0x10:
            mode += 'V'

        if data[7] & 0x4:
            mode += 'µ'
        if data[7] & 0x8:
            mode += 'm'
        if data[6] & 0x80:
            mode += 'A'

        if data[6] & 2:
            mode += 'Ohm'
        if data[5] & 0x10:
            mode += 'nF'
        if data[6] & 1:
            mode += 'Hz'
        if data[5] & 4:
            mode += 'duty %'
        if data[4] & 0x20:
            mode += '°F'
        if data[4] & 0x40:
            mode += '°C'

        if data[4] & 0x10:
            mode += ' Hold'
        if data[0] & 2:
            mode += ' Rel'
        if data[5] & 1:
            mode += ' Max'
        if data[5] & 2:
            mode += ' Min'
        if data[0] & 1:
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
        dev = AnengBtDevice.open()
        if dev:
            with dev:
                last_data = None
                while dev.is_connected():
                    data = dev.query_raw()
                    if data:
                        if last_data is None: print()
                        print(' '.join(['%02x' % b for b in data]), dev.get_value(data), dev.get_mode(data))
                    else:
                        print('.', end='', flush=True)
                    last_data = data
    except KeyboardInterrupt:
        pass
