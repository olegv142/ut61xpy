"""
CH347T USB HID adapter I2C API
See https://www.wch-ic.com/downloads/CH347DS1_PDF.html
The following repositories were used as a reference:
https://github.com/i2cy/CH347-HIDAPI
https://github.com/serfreeman1337/go-ch347
"""

import time
import logging

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

log = logging.getLogger('DEV')

DEVICE_VID = 0x1A86
DEVICE_PID = 0x55DC
DEVICE_IFN = 1

I2CMode0 = 0 # Low rate 20KHz
I2CMode1 = 1 # Standard rate 100KHz
I2CMode2 = 2 # Fast rate 400KHz
I2CMode3 = 3 # High rate 750KHz

READ_TOUT_MS = 20

def find_device():
    """Find device and open it"""
    import device
    devs = device.find_hid_devices(DEVICE_VID, DEVICE_PID, ifnum=DEVICE_IFN)
    if not devs:
        return None
    if len(devs) > 1:
        log.warning('%d devices found', len(devs))
        return None
    path = devs[0]['path']
    dev = device.hid.device()
    try:
        dev.open_path(path)
    except Exception:
        log.error('failed to open CH347T at %s', path)
        return None
    return dev

def i2c_init(dev, mode: int = I2CMode1):
    dev.set_nonblocking(False)
    dev.write([0, 3, 0, 0xaa, 0x60 + mode, 0])

# The command package of the I2C interface, starting from the secondary byte,
# is the I2C command stream
CmdI2CStream = 0xAA

# Command flow of I2C interface: generate start bit
CmdI2CStart = 0x74

# Command flow of I2C interface: generate stop bit
CmdI2CStop = 0x75

# Command flow of I2C interface: output data, bit 5 - bit 0 is the length,
# subsequent bytes are data, and length 0 only sends one byte and returns an answer
CmdI2CWrite = 0x80

# I2C interface command flow: input data, bit 5 - bit 0 is the length,
# and 0 length only receives one byte and sends no response. Note that a reads must
# be completed with one byte reading (0xc0), otherwise next operation will fail.
CmdI2CRead = 0xc0

def i2c_tx_raw(dev, data: list[int], read_len: int = 0) -> tuple[bool, list[int]]:
    """
    Write and read i2c bus through I2CStream given the length of the data to read
    and the data to write. The first byte of the data to write is always write address
    shifted left by one bit (in wire representation). Returns boolean success status and
    the data read.
    """
    assert read_len <= 64
    assert len(data) >= 1
    addr, addr_cnt = data[0], 0
    tail = []

    if read_len:
        addr_cnt += 1 # transmit read address
        tail += [CmdI2CStart, CmdI2CWrite + 1, addr | 1] # write read address
        if read_len == 1:
            tail += [CmdI2CRead]
        else:
            tail += [CmdI2CRead + read_len - 1, CmdI2CRead]

    tail += [CmdI2CStop]

    if read_len and len(data) == 1: # pure read, data[0] is the address
        payload = [0, 1 + len(tail), 0, CmdI2CStream] + tail
    else:
        addr_cnt += 1 # transmit write address
        payload = [0, 3 + len(data) + len(tail), 0, CmdI2CStream, CmdI2CStart, CmdI2CWrite + len(data)] + data + tail

    dev.write(payload)
    feedback = dev.read(512, timeout_ms=READ_TOUT_MS)
    if not feedback:
        log.error('timeout %s addr %#x', 'reading' if len(data) <= 1 else 'writing', addr >> 1)
        return False, []

    payload_length = feedback[0] + (feedback[1] << 8)
    data_off = 2 + len(data) - 1 + addr_cnt
    return all(ack == 1 for ack in feedback[2:data_off]), feedback[data_off:2+payload_length]

def i2c_write(dev, address: int, data: list[int]) -> bool:
    sta, ret = i2c_tx_raw(dev, [address << 1] + data)
    return sta

def i2c_read(dev, address: int, length: int) -> list[int]|None:
    sta, ret = i2c_tx_raw(dev, [address << 1], length)
    if not sta:
        return None
    return ret

def i2c_write_read(dev, address: int, wr_data: list[int], rd_length: int) -> list[int]|None:
    sta, ret = i2c_tx_raw(dev, [address << 1] + wr_data, rd_length)
    if not sta:
        return None
    return ret

def i2c_probe(dev, address: int) -> bool:
    """Check the device presence at given address"""
    sta, ret = i2c_tx_raw(dev, [address << 1]) # Just check if address was acknowledged
    return sta

#
# GPIO control API
#

CmdGPIOSetup = 0xCC

def gpio_set_pin(dev, pin: int, out_dir: bool, level: bool = False) -> bool|None:
    """
    Setup direction and level of the particular pin given its index.
    Setting level seems to be ignored for the input pins (out_dir = False).
    Returns True on success, None on error. Note that the response from the adapter
    contains the actual level of the output pin after the new level was set up.
    In case it differs from the level set up the function returns False. This may be
    expected due to the low impedance or capacitive load. 
    """
    assert 0 <= pin < 8
    prefix = [11, 0, CmdGPIOSetup, 8, 0]
    pkt = prefix + [0] * 8
    cfg = 0xf0 if out_dir else 0xc0
    if level:
        cfg += 8
    pkt[len(prefix)+pin] = cfg
    dev.write([0] + pkt)
    feedback = dev.read(512, timeout_ms=READ_TOUT_MS)
    if not feedback:
        log.error('GPIO packet response timeout')
        return None
    if feedback[:len(prefix)] != prefix:
        log.error('bad GPIO packet response: %s, expect %s', feedback[:len(prefix)], prefix)
        return None
    cfg_ret = feedback[len(prefix)+pin]
    if out_dir != ((cfg_ret & 0x80) != 0):
        log.debug('failed to set GPIO#%d as %s, got %s', pin,
            'output' if out_dir else 'input', bin(cfg_ret))
        return None
    if out_dir:
        out_level = ((cfg_ret & 0x40) != 0)
        if level != out_level:
            log.debug('failed to set GPIO#%d level to %s', pin, 'high' if level else 'low')
            return False
    return True

def gpio_get_pin(dev, pin: int) -> bool|None:
    """
    Read the particular GPIO pin level given its index. Returns True if the level is high,
    False if low, None in case of error. This function returns the actual pin level
    even in case the pin is configured as output. So it will return zero bit for short
    circuited pin even if it was set to high level by gpio_set_pin.
    """
    assert 0 <= pin < 8
    prefix = [11, 0, CmdGPIOSetup, 8, 0]
    pkt = prefix + [0] * 8
    dev.write([0] + pkt)
    feedback = dev.read(512, timeout_ms=READ_TOUT_MS)
    if not feedback:
        log.error('GPIO packet response timeout')
        return None
    cfg_ret = feedback[len(prefix)+pin]
    return ((cfg_ret & 0x40) != 0)

def gpio_set(dev, pin_mask : int, out_mask: int, out_bits: int) -> bool|None:
    """
    Setup pin direction and levels for the pins having corresponding bit set in pin_mask.
    Returns True on success, None on error. Note that the response from the adapter
    contains the actual level of the output pin after the new level was set up.
    In case it differs from the level set up the function returns False. This may be
    expected due to the low impedance or capacitive load.
    """
    prefix = [11, 0, CmdGPIOSetup, 8, 0]
    pkt = prefix + [0] * 8
    for pin in range(8):
        bit = 1 << pin
        if pin_mask & bit:
            cfg = 0xf0 if (out_mask & bit) else 0xc0
            if out_bits & bit:
                cfg += 8
            pkt[len(prefix)+pin] = cfg
    dev.write([0] + pkt)
    feedback = dev.read(512, timeout_ms=READ_TOUT_MS)
    if not feedback:
        log.error('GPIO packet response timeout')
        return None
    if feedback[:len(prefix)] != prefix:
        log.error('bad GPIO packet response: %s, expect %s', feedback[:len(prefix)], prefix)
        return None
    res = True
    for pin in range(8):
        bit = 1 << pin
        if pin_mask & bit:
            cfg_ret = feedback[len(prefix)+pin]
            out_dir = ((out_mask & bit) != 0)
            if out_dir != ((cfg_ret & 0x80) != 0):
                log.debug('failed to set GPIO#%d as %s, got %s', pin,
                    'output' if out_dir else 'input', bin(cfg_ret))
                return None
            if out_dir:
                level = ((out_bits & bit) != 0)
                out_level = ((cfg_ret & 0x40) != 0)
                if level != out_level:
                    log.debug('failed to set GPIO#%d level to %s', pin, 'high' if level else 'low')
                    res = False
    return res

def gpio_get(dev) -> int:
    """
    Get input/output pin levels as bitmask. This function returns the actual pin level
    even in case the pin is configured as output. So it will return zero bit for short
    circuited pin even if it was set to high level by gpio_set.
    """
    prefix = [11, 0, CmdGPIOSetup, 8, 0]
    pkt = prefix + [0] * 8
    dev.write([0] + pkt)
    feedback = dev.read(512, timeout_ms=READ_TOUT_MS)
    if not feedback:
        log.error('GPIO packet response timeout')
        return None
    bitmask = 0
    for pin in range(8):
        cfg_ret = feedback[len(prefix)+pin]
        if (cfg_ret & 0x40) != 0:
            bitmask += 1 << pin
    return bitmask

# GPIO4 drives LED on MUSE LAB board (active low)
LED_GPIO_PIN = 4

if __name__ == '__main__':
    import hid

    def test_scan(dev):
        """Scan bus for devices"""
        for addr in range(8, 128):
            print(('%02x ' % addr) if i2c_probe(dev, addr) else '-- ', end='' if (addr + 1) % 8 else '\n')

    def test_gpio_02(dev):
        """Test GPIO input/output with pins GPIO0,2 interconnected"""
        gpio_set_pin(dev, 2, out_dir=False)
        for i in range(100):
            level = (i & 1) != 0
            gpio_set_pin(dev, 0, True, level)
            time.sleep(.005)
            assert level == gpio_get_pin(dev, 0)
            assert level == gpio_get_pin(dev, 2)
            assert (gpio_get(dev) & 5) == (5 if level else 0)
        for i in range(100):
            level = (i & 1) != 0
            gpio_set(dev, 5, 4, 4 if level else 0)
            time.sleep(.005)
            assert level == gpio_get_pin(dev, 0)
            assert level == gpio_get_pin(dev, 2)
            assert (gpio_get(dev) & 5) == (5 if level else 0)

    def led_blink(dev):
        for i in range(20):
            gpio_set_pin(dev, LED_GPIO_PIN, True, i % 2 != 0)
            time.sleep(.05)

    def test_gpio_blink(dev):
        cnt = 0
        while True:
            assert gpio_set(dev, 0xff, 0xff, 1 << (cnt % 8))
            print('.', end='', flush=True)
            time.sleep(.5)
            cnt += 1

    logging.basicConfig(level=logging.DEBUG)
    dev = find_device()
    i2c_init(dev)
    test_scan(dev)
    #test_gpio_02(dev)
    led_blink(dev)
    #test_gpio_blink(dev)
