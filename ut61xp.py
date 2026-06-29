"""
The UNI-T UT61B/D/E+ digital multimeter communication helper.
Its inspired by:
 https://github.com/aroum/unit_ut61eplus_python
 https://github.com/ljakob/unit_ut61eplus
The code was reworked with the following goals in mind:
 - keep code as simple as possible
 - seamless working on Windows and Linux
"""

import hid
import time
import logging
import threading

log = logging.getLogger('DEV')

DEF_TOUT = 5
DEF_VID = 0x1a86
DEF_PID = 0xe429
DEF_BT_NAME = 'UT-D07B'
BT_TX_CHAR = '49535343-8841-43f4-a8d4-ecbe34729bb3'
BT_RX_CHAR = '49535343-1e4d-4bd9-ba61-23c647249616'

TRIGGER_CMD = [0xAB, 0xCD, 0x03, 0x5E, 0x01, 0xD9]
DATA_LEN = 14

class Device:
    @staticmethod
    def hid_list_paths(vid=DEF_VID, pid=DEF_PID):
        """Returns the list of HID device paths"""
        return [dev['path'] for dev in hid.enumerate(vid, pid)]

    @staticmethod
    def bt_list_addrs(name=DEF_BT_NAME):
        """Returns the list of BT device addresses"""
        import asyncio
        addr_list = []
        async def a_list():
            from bleak import BleakScanner
            devices = await BleakScanner.discover()
            for d in devices:
                if d.name == name:
                    addr_list.append(d.address)
        asyncio.run(a_list())
        return addr_list

    def __init__(self, dev, path, bt=False):
        self.dev  = dev
        self.path = path
        self.bt   = bt

    @staticmethod
    def hid_open_path(path):
        """Open device given the path"""
        if isinstance(path, str):
            path = path.encode('ascii')
        dev = hid.device()
        try:
            dev.open_path(path)
        except:
            log.error('failed to open device %s', path)
            return None
        dev.set_nonblocking(True)
        return Device(dev, path.decode('ascii'))

    @staticmethod
    def hid_open(vid=DEF_VID, pid=DEF_PID):
        """Open device given its VID, PID. Returns device, path tuple."""
        paths = Device.hid_list_paths(vid, pid)
        if not paths:
            log.error('not found')
            return None
        if len(paths) > 1:
            log.error('%d devices found', len(paths))
            return None
        return Device.hid_open_path(paths[0])

    @staticmethod
    def bt_open_addr(addr):
        """Open BT device given its mac address"""
        import asyncio
        from bleak import BleakClient
        dev = BleakClient(addr)
        async def a_connect():
            try:
                await dev.connect()
            except Exception:
                pass
        asyncio.run(a_connect())
        if not dev.is_connected:
            return None
        return Device(dev, addr, True)

    @staticmethod
    def bt_open(name=DEF_BT_NAME):
        """Open BT device given its name"""
        addrs = Device.bt_list_addrs(name)
        if not addrs:
            log.error('not found')
            return None
        if len(addrs) > 1:
            log.error('%d devices found', len(addrs))
            return None
        return Device.bt_open_addr(addrs[0])

    def query_raw(self, tout=DEF_TOUT, idle_sleep=time.sleep):
        """Read and validate raw data packet"""
        if not self.bt:
            return self.hid_query_raw(self.dev, tout, idle_sleep)
        else:
            return self.bt_query_raw(self.dev, tout, idle_sleep)

    def close(self):
        if self.dev is None:
            return
        if not self.bt:
            self.dev.close()
        else:
            import asyncio
            asyncio.run(self.dev.disconnect())
        self.dev = None

    @staticmethod
    def hid_query_raw(dev, tout=DEF_TOUT, idle_sleep=time.sleep):
        attempts = int(10 * tout)
        dev.write([0, len(TRIGGER_CMD)] + TRIGGER_CMD)
        while True:
            idle_sleep(.1)
            buf = dev.read(64)
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
        return Device.validate_raw_data(buf[1:1+data_len])

    @staticmethod
    def bt_query_raw(dev, tout=DEF_TOUT, idle_sleep=time.sleep):
        import asyncio
        data = None
        def notify_cb(char, val):
            nonlocal data
            if len(val) == 3 + DATA_LEN + 2:
                data = val

        async def a_query():
            attempts = int(10 * tout)
            await dev.start_notify(BT_RX_CHAR, notify_cb)
            await dev.write_gatt_char(BT_TX_CHAR, bytearray(TRIGGER_CMD))
            while not data and attempts:
                attempts -= 1
                await asyncio.sleep(.1)
            await dev.stop_notify(BT_RX_CHAR)

        req = threading.Thread(target=lambda: asyncio.run(a_query()))
        req.start()
        while req.is_alive():
            idle_sleep(.1)
        req.join()
        if not data:
            return None
        return Device.validate_raw_data(data)

    @staticmethod
    def validate_raw_data(data):
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

    def get_value(data):
        """
        Convert raw data to the floating point value. Here we don't
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

if __name__ == '__main__':
    # Open device and print raw readings as well as the corresponding floating point value
    try:
        dev = Device.hid_open()
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
