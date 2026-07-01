"""
The UNI-T UT61B/D/E+ digital multimeter communication helper.
Its inspired by:
 https://github.com/ljakob/unit_ut61eplus
 https://github.com/aroum/unit_ut61eplus_python
The code was reworked with the following goals in mind:
 - keep code as small and simple as possible
 - seamless working on Windows and Linux
 - support for USB HID and Bluetooth communication channel
"""

import hid
import time
import logging
import threading
import asyncio
from abc import ABC, abstractmethod

log = logging.getLogger('DEV')

DEF_TOUT    = 4
DEF_VID     = 0x1a86
DEF_PID     = 0xe429
DEF_BT_NAME = 'UT-D07B'
BT_TX_CHAR  = '49535343-8841-43f4-a8d4-ecbe34729bb3'
BT_RX_CHAR  = '49535343-1e4d-4bd9-ba61-23c647249616'

TRIGGER_CMD = [0xAB, 0xCD, 0x03, 0x5E, 0x01, 0xD9]
DATA_LEN    = 14

class Device(ABC):
    """Base class for all adapters"""
    def __init__(self, path):
        self.path = path

    @abstractmethod
    def query_raw(self, tout=DEF_TOUT, idle_sleep=time.sleep):
        pass

    @staticmethod
    def _validate_raw_data(data):
        """
        Validates data packet. Returns either valid packet with
        header and checksum stripped or None.
        """
        if data[0] != 0xab or data[1] != 0xcd:
            log.error('bad magic (%#x, %#x)', data[0], data[1])
            return None
        if len(data) != 3 + DATA_LEN + 2:
            log.error('bad data length: %d', len(data))
            return None
        if data[2] != len(data) - 3:
            log.error('bad length: %d, expects %d', data[2], len(data) - 3)
            return None
        cs = data[-2] * 256 + data[-1]
        if cs != sum(data[:-2]):
            log.error('bad checksum')
            return None
        return data[3:-2]

    @staticmethod
    def get_value(data):
        """
        Converts raw data to the floating point value. Here we don't
        care about units since the caller should be aware of them.
        It set mode dial manually after all. So in the mV mode the
        result is expressed in mV rather than volts.
        """
        try:
            space = ord(' ')
            val = float(''.join([chr(d) for d in data[2:9] if d != space]))
        except ValueError:
            return float('nan')
        # Apply range multiplier
        mode, range = data[0], data[1] - ord('0')
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
        range_offset = {
            6 : 2, # Ohms
            9 : 1, # nF
        }
        if mode not in range_offset:
            return val
        return val * 10 ** (3*((range + range_offset[mode]) // 3))

    @staticmethod
    def get_channel(data):
        """
        The UT61E+ can measure DC and AC voltage alternately in DC voltage dial position.
        This function returns 1 in such mode (25) if the data belongs to the alternative
        measuring channel, so it represents AC voltage. Otherwise it returns 0.
        """
        return 1 if (data[0] == 25) and (data[DATA_LEN-1] & 8) else 0

    mode_map = [
        {
            0  : 'ac V',
            1  : 'ac mV',
            2  : 'dc V',
            3  : 'dc mV',
            4  : 'Hz',
            5  : 'pw %',
            6  : 'Ohm',
            7  : 'Ohm',
            8  : 'diode V',
            9  : 'nF',
            10 : '°C',
            11 : '°F',
            12 : 'dc uA',
            13 : 'ac uA',
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

    @staticmethod
    def get_mode(data):
        """Returns measurement mode and units description string"""
        return Device.mode_map[Device.get_channel(data)].get(data[0])

    @abstractmethod
    def close(self):
        pass

    def __enter__(self):
        """Context manager protocol support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes device on exiting 'with' block"""
        self.close()

class HIDDevice(Device):
    """USB HID adapter (D-09A) interface class"""
    def __init__(self, dev, path):
        super().__init__(path)
        self.dev = dev

    @staticmethod
    def list_paths(vid=DEF_VID, pid=DEF_PID):
        """Returns the list of HID device paths"""
        return [dev['path'] for dev in hid.enumerate(vid, pid)]

    @staticmethod
    def open_path(path):
        """Opens device given the path"""
        if isinstance(path, str):
            path = path.encode('ascii')
        dev = hid.device()
        try:
            dev.open_path(path)
        except:
            log.error('failed to open device %s', path)
            return None
        dev.set_nonblocking(True)
        return HIDDevice(dev, path.decode('ascii'))

    @staticmethod
    def open(vid=DEF_VID, pid=DEF_PID):
        """Opens device given its VID, PID. Returns device, path tuple."""
        paths = HIDDevice.list_paths(vid, pid)
        if not paths:
            log.error('not found')
            return None
        if len(paths) > 1:
            log.error('%d devices found', len(paths))
            return None
        return HIDDevice.open_path(paths[0])

    def query_raw(self, tout=DEF_TOUT, idle_sleep=time.sleep):
        """Queries raw data packet from HID device"""
        attempts = int(10 * tout)
        self.dev.write([0, len(TRIGGER_CMD)] + TRIGGER_CMD)
        while True:
            idle_sleep(.1)
            buf = self.dev.read(64)
            if buf:
                break
            attempts -= 1
            if attempts <= 0:
                return None
        # print(' '.join('%02x' % v for v in buf))
        data_len = buf[0]
        if data_len <= 2 or data_len > 63:
            log.error('bad length: %d', data_len)
            return None
        return Device._validate_raw_data(buf[1:1+data_len])

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        self.dev.close()
        self.dev = None

class BTDevice(Device):
    """Bluetooth adapter (UT-D07B) interface class"""
    evloop = None
    evloop_thread = None

    def __init__(self, dev, addr):
        super().__init__(addr)
        self.dev = dev
        self.last_data = None

    @staticmethod
    def _evloop_work():
        """Event loop worker routine"""
        asyncio.set_event_loop(BTDevice.evloop)
        BTDevice.evloop.run_forever()

    @staticmethod
    def _evloop_start():
        """Starts event loop in separate thread to handle BT stuff"""
        if BTDevice.evloop is not None:
            return
        BTDevice.evloop = asyncio.new_event_loop()
        BTDevice.evloop_thread = threading.Thread(target=BTDevice._evloop_work, daemon=True)
        BTDevice.evloop_thread.start()

    @staticmethod
    def _async_exec(co, wait=True):
        """Executes given co-routine and returns result"""
        BTDevice._evloop_start()
        try:
            future = asyncio.run_coroutine_threadsafe(co, BTDevice.evloop)
            return future.result() if wait else future
        except Exception as e:
            log.debug(e)
            return None

    @staticmethod
    def list_addrs(name=DEF_BT_NAME):
        """Returns the list of BT device addresses"""
        addr_list = []
        async def a_list():
            from bleak import BleakScanner
            devices = await BleakScanner.discover()
            for d in devices:
                if d.name == name:
                    addr_list.append(d.address)
        BTDevice._async_exec(a_list())
        return addr_list

    def _notify_cb(self, char, val):
        """BT adapter data changed notification callback"""
        if len(val) == 3 + DATA_LEN + 2:
            self.last_data = val

    @staticmethod
    def open_addr(addr):
        """Opens BT device given its mac address"""
        from bleak import BleakClient
        clnt = BleakClient(addr)
        inst = BTDevice(clnt, addr)
        async def a_connect():
            await clnt.connect()
            if clnt.is_connected:
                await clnt.start_notify(BT_RX_CHAR, inst._notify_cb)
        BTDevice._async_exec(a_connect())
        if not clnt.is_connected:
            log.error('failed to connect to device %s', addr)
            return None
        return inst

    @staticmethod
    def open(name=DEF_BT_NAME):
        """Opens BT device given its name"""
        addrs = BTDevice.list_addrs(name)
        if not addrs:
            log.error('not found')
            return None
        if len(addrs) > 1:
            log.error('%d devices found', len(addrs))
            return None
        return BTDevice.open_addr(addrs[0])

    def query_raw(self, tout=DEF_TOUT, idle_sleep=time.sleep):
        """Queries raw data packet from BT device"""
        async def a_query():
            attempts = int(10 * tout)
            self.last_data = None
            await self.dev.write_gatt_char(BT_TX_CHAR, bytearray(TRIGGER_CMD), response=False)
            while not self.last_data and attempts:
                attempts -= 1
                await asyncio.sleep(.1)
        query = BTDevice._async_exec(a_query(), wait=False)
        while not query.done():
            idle_sleep(.1)
        if not self.last_data:
            return None
        return Device._validate_raw_data(self.last_data)

    def close(self):
        """Closes device if its still open"""
        if self.dev is None:
            return
        BTDevice._async_exec(self.dev.disconnect())
        self.dev = None

if __name__ == '__main__':
    # Open device and print raw readings as well as the corresponding floating point value
    try:
        dev = HIDDevice.open()
        if dev:
            with dev:
                last_data = None
                while True:
                    data = dev.query_raw()
                    if data:
                        if last_data is None: print()
                        print(data[0], ''.join([chr(d) for d in data[1:9]]), data[DATA_LEN-1],
                            '[%d] =' % Device.get_channel(data), Device.get_value(data))
                    else:
                        print('.', end='', flush=True)
                    last_data = data
    except KeyboardInterrupt:
        pass
