"""
The UNI-T UT61B/D/E+ and UT60BT digital multimeter communication adapters.
Its inspired by:
 https://github.com/ljakob/unit_ut61eplus
 https://github.com/aroum/unit_ut61eplus_python
The code was reworked with the following goals in mind:
 - keep code as small and simple as possible
 - seamless working on Windows and Linux
 - support for USB HID and Bluetooth communication channel
"""

import os
import sys
import time
import logging

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

import bt_engine
from device import Device, HIDMixin, BTMixin

log = logging.getLogger('DEV')

class UTDevice(Device):
    """
    Base class for supported UNI-T devices
    """
    # The following is the data packet that consists of the single '^' symbol
    # prefixed by magic, length and followed by checksum
    # It should be sent to the device to trigger data response
    TRIGGER_CMD = [0xAB, 0xCD, 0x03, 0x5E, 0x01, 0xD9]
    DATA_LEN    = 14 # data response packet length

    def _validate_raw_data(self, data):
        """
        Validates data packet. Returns either valid packet with
        header and checksum stripped or None.
        """
        if data[0] != 0xab or data[1] != 0xcd:
            log.error('%s bad data magic (%#x, %#x)', self, data[0], data[1])
            return None
        if len(data) != 3 + UTDevice.DATA_LEN + 2:
            log.error('%s bad data length: %d', self, len(data))
            return None
        if data[2] != len(data) - 3:
            log.error('%s bad data length: %d, expects %d', self, data[2], len(data) - 3)
            return None
        cs = data[-2] * 256 + data[-1]
        if cs != sum(data[:-2]):
            log.error('%s bad data checksum', self)
            return None
        return data[3:-2]

    @staticmethod
    def get_range_offset(mode):
        return {
            6 : 2, # Ohms
            9 : 1, # nF
        }.get(mode)

    @staticmethod
    def get_scale(mode):
        """
        The UT61X+ reports measurement mode (say voltage) set by the user. The actual measurement units
        may be different across models. For example the UT61E+ reports volts in voltage mode while UT60BT
        reports millivolts. The purpose of this function is to fix scale differences across models.
        """
        return 1

    def get_value(self, data, channel=None):
        """
        Converts raw data to the floating point value. Here we don't
        care about units since the caller should be aware of them.
        It set mode dial manually after all. So in the mV mode the
        result is expressed in mV rather than volts.
        """
        if not data:
            return Device.INVALID_VALUE
        try:
            space = ord(' ')
            val = float(''.join([chr(d) for d in data[2:9] if d != space]))
        except ValueError:
            return Device.INVALID_VALUE
        # Apply range multiplier
        mode, rng = data[0], data[1] - ord('0')
        # There are 3 positions of the decimal place on display.
        # Every time the range value is incremented the decimal place
        # either moves to the right or jumps back to the leftmost
        # position. When its moving to the right we don't need to
        # change multiplier. When it jumps to the left we have to
        # increase multiplier by 3 orders of magnitude.
        # The following map keeps the initial position of the decimal
        # point corresponding to the range 0.
        # Its indexed by the mode. If the mode is not in the map
        # then we don't care about range multiplier at all.
        val *= self.get_scale(mode)
        off = self.get_range_offset(mode)
        if off is not None:
            val *= 10 ** (3*((rng + off) // 3))
        return val

    def get_channel(self, data):
        """
        The UT61E+ can measure DC and AC voltage alternately in DC voltage dial position.
        This function returns 1 in such mode (25) if the data belongs to the alternative
        measuring channel, so it represents AC voltage. Otherwise it returns 0.
        """
        return 1 if (data[0] == 25) and (data[self.DATA_LEN-1] & 8) else 0

    _mode_map = [
        {
            0  : 'ac V',
            1  : 'ac mV',
            2  : 'dc V',
            3  : 'dc mV',
            4  : 'Hz',
            5  : 'duty %',
            6  : 'Ohm',
            7  : 'Ohm',
            8  : 'diode V',
            9  : 'nF',
            10 : '°C',
            11 : '°F',
            12 : 'dc µA',
            13 : 'ac µA',
            14 : 'dc mA',
            15 : 'ac mA',
            16 : 'dc A',
            17 : 'ac A',
            18 : 'hFE',
            20 : 'NCV',
            21 : 'ac V LoZ',
            24 : 'ac V LPF',
            25 : 'dc V',
        }, {
            25 : 'ac V',
        }
    ]

    def get_mode(self, data, channel=None):
        """Returns measurement mode and units description string"""
        if not data:
            return ''
        mode = self._mode_map[self.get_channel(data)].get(data[0], '')
        f1, f2, f3 = data[self.DATA_LEN-3:]
        if f1 & 2:
            mode += ' Hold'
        if f1 & 1:
            mode += ' Rel'
        if f1 & 4:
            mode += ' Min'
        if f1 & 8:
            mode += ' Max'
        if f2 & 1:
            mode += ' Caution!'
        if f2 & 2:
            mode += ' LoBatt'
        # f2 & 4 means manual mode
        # f3 & 1 means current polarity is negative
        if f3 & 2:
            mode += ' P-Min'
        if f3 & 4:
            mode += ' P-Max'
        # f3 & 8 means AC channel in DC+AC mode
        return mode

class UTUsbDevice(HIDMixin, UTDevice):
    """USB HID adapter (D-09A) interface class"""
    DEVICE_VID = 0x1a86
    DEVICE_PID = 0xe429
    TOUT       = 1  # default timeout in seconds
    IDLE_DELAY = .1

    def query_raw(self, idle_sleep=time.sleep):
        """Queries raw data packet from HID device"""
        if not self.is_connected():
            return None
        wait = self.TOUT
        try:
            self.dev.write([0, len(self.TRIGGER_CMD)] + self.TRIGGER_CMD)
            while True:
                idle_sleep(self.IDLE_DELAY)
                buf = self.dev.read(64)
                if buf:
                    break
                wait -= self.IDLE_DELAY
                if wait <= 0:
                    return None
        except Exception as e:
            self.disconnected = True
            log.debug(e, exc_info=True)
            return None
        data_len = buf[0]
        if data_len <= 2 or data_len > 63:
            log.error('%s bad HID message length: %d', self, data_len)
            return None
        return self._validate_raw_data(buf[1:1+data_len])

class UTBtDevice(BTMixin, UTDevice):
    """Bluetooth adapter (UT-D07B) interface class"""
    BT_TX_CHAR  = '49535343-8841-43f4-a8d4-ecbe34729bb3'
    BT_RX_CHAR  = '49535343-1e4d-4bd9-ba61-23c647249616'
    TOUT        = 4  # default timeout in seconds
    IDLE_DELAY  = .1

    def __init__(self, dev, addr):
        BTMixin.__init__(self, dev, addr)
        self.last_data = None

    def _notify_cb(self, char, val):
        """BT adapter data changed notification callback"""
        if len(val) == 3 + self.DATA_LEN + 2:
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
        self.last_data = None
        async def a_trigger():
            await self.dev.write_gatt_char(self.BT_TX_CHAR, bytearray(self.TRIGGER_CMD), response=False)
            return True
        if not bt_engine.async_exec(a_trigger()):
            return None
        while self.last_data is None and wait >= 0:
            idle_sleep(self.IDLE_DELAY)
            wait -= self.IDLE_DELAY
        if not self.last_data:
            return None
        return self._validate_raw_data(self.last_data)

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        bt_engine.async_exec(self.dev.disconnect())
        self.dev = None

class UT61XpUsbDevice(UTUsbDevice):
    MODEL_NAME = 'UT61X+'

class UT61XpBtDevice(UTBtDevice):
    MODEL_NAME = 'UT61X+'
    DEVICE_NAME = 'UT-D07B'

class UT60BTDevice(UTBtDevice):
    """
    UT60BT specific stuff.
    It uses the same protocol with minor particularities related to ranges.
    """
    MODEL_NAME = DEVICE_NAME = 'UT60BT'

    @staticmethod
    def get_range_offset(mode):
        return {
            0 : 2, # ac V
            2 : 2, # dc V
            6 : 2, # Ohms
            14: 2, # dc mA
            15: 2, # ac mA
        }.get(mode)

    @staticmethod
    def get_scale(mode):
        return {
            0 : 1e-3, # ac V is in mV actually
            2 : 1e-3, # dc V is in mV actually
        }.get(mode, 1)

if __name__ == '__main__':
    # Open device and print raw readings as well as the corresponding floating point value
    try:
        if len(sys.argv) > 1:
            name = sys.argv[1]
            dev_type = UT60BTDevice if name == UT60BTDevice.DEVICE_NAME else UT61XpBtDevice
            dev = dev_type.open(name)
        else:
            dev = UT61XpUsbDevice.open()
        if dev:
            with dev:
                last_data = None
                while dev.is_connected():
                    data = dev.query_raw()
                    if data:
                        if last_data is None: print()
                        print(data[0], ''.join([chr(d) for d in data[1:9]]), list(data[dev.DATA_LEN-3:dev.DATA_LEN]),
                            '[%d] =' % dev.get_channel(data), dev.get_value(data), dev.get_mode(data))
                    else:
                        print('.', end='', flush=True)
                    last_data = data
    except KeyboardInterrupt:
        pass
