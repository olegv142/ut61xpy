"""
FTDI FT260 adapter I2C and GPIo communication routines
"""

import time
import logging

log = logging.getLogger('DEV')

DEVICE_VID = 0x403
DEVICE_PID = 0x6030

# I2C transaction flags
FL_START = 2
FL_STOP  = 4
FL_START_STOP = FL_START | FL_STOP

# I2C status flags
STA_BUSY        = 1
STA_ERROR       = 2
STA_NACK_ADDR   = 4
STA_NACK_DATA   = 8
STA_ARBITR_LOST = 16
STA_IDLE        = 32
STA_BUSY_BUS    = 64

MIN_DELAY = .005
READ_TOUT = .025
BUSY_TOUT = .050

def i2c_init(dev):
    dev.set_nonblocking(True)
    dev.send_feature_report([0xA1, 0x20]) # reset I2C

def read_packet(dev):
    wait = READ_TOUT
    delay = MIN_DELAY
    while True:
        if pkt := dev.read(64):
            return pkt
        if wait <= 0:
            break
        time.sleep(delay)
        wait -= delay
        delay *= 2
    return None

def i2c_query_status(dev) -> int:
    sta = dev.get_feature_report(0xC0, 61)
    return sta[1]

def i2c_wait_idle(dev) -> int:
    wait = BUSY_TOUT
    delay = MIN_DELAY
    while True:
        sta = i2c_query_status(dev)
        if not (sta & STA_BUSY):
            return sta & ~STA_IDLE
        if wait <= 0:
            break
        time.sleep(delay)
        wait -= delay
        delay *= 2
    return sta

def i2c_write(dev, address: int, data: list[int], flags: int = FL_START_STOP, wait: bool = False) -> bool:
    assert 0 < len(data) <= 60
    report_id = 0xD0 + (len(data) - 1) // 4
    payload = [report_id, address, flags, len(data)] + data
    dev.write(payload)
    if not wait:
        return True
    if sta := i2c_wait_idle(dev):
        log.error('bad status %u writing addr %#x', sta, address)
        return False
    return True

def i2c_read(dev, address: int, length: int, flags: int = FL_START_STOP) -> list[int]|None:
    assert 0 < length <= 60
    dev.write([0xC2, address, flags, length, 0])
    report = read_packet(dev)
    if report is None:
        log.error('timeout reading addr %#x', address)
        return None
    if sta := i2c_wait_idle(dev):
        log.error('bad status %u reading addr %#x', sta, address)
        return None
    if len(report) < 2 + length:
        log.error('bad packet length reading addr %#x: expects %u, got %u',
            address, length + 2, len(report))
    if length != report[1]:
        log.error('bad data length reading addr %#x: expects %u, got %u',
            address, length, report[1])
        return None
    return report[2:2 + length]

#
# GPIO routines
#
# The mapping of GPIO pins to pin names is shown below.
# Pins available for using as GPIO by default are marked.
# GPIO0 DIO5 [SCL]
# GPIO1 DIO6 [SDA]
# GPIO2 DIO7  configurable
# GPIO3 DIO8  unavailable
# GPIO4 DIO10 avail
# GPIO5 DIO11 avail
# GPIOA DIO0  configurable
# GPIOB DIO1  avail
# GPIOC DIO3  avail if no UART
# GPIOD DIO4  avail if no UART
# GPIOE DIO2  avail
# GPIOF DIO9  avail
# GPIOG DIO12 configurable
# GPIOH DIO13 avail
# Note that on CJMCU-260 board the UART is disabled by DCNF bootstrap pins.
# So there are 11 pins available for using as GPIO pins.
#

# GPIO bits definitions
GPIO0 = 1
GPIO1 = GPIO0 << 1
GPIO2 = GPIO1 << 1
GPIO3 = GPIO2 << 1
GPIO4 = GPIO3 << 1
GPIO5 = GPIO4 << 1

GPIOA = 1 << 8
GPIOB = GPIOA << 1
GPIOC = GPIOB << 1
GPIOD = GPIOC << 1
GPIOE = GPIOD << 1
GPIOF = GPIOE << 1
GPIOG = GPIOF << 1
GPIOH = GPIOG << 1

# GPIO control report ID
GPIO_REPORT = 0xB0

def gpio_write(dev, out_mask: int, out_bits: int):
    """
    Setup GPIO direction mask ans set output levels.
    The low order byte corresponds to GPIO0..5 while
    the high order byte corresponds to GPIOA..H pins.
    """
    dev.send_feature_report([GPIO_REPORT, out_bits & 0xff, out_mask & 0xff, out_bits >> 8, out_mask >> 8])

def gpio_read(dev) -> int:
    """Read GPIO bits as 16 bit word with the same mapping to pins as for gpio_write"""
    report = dev.get_feature_report(GPIO_REPORT, 64)
    assert len(report) == 5
    assert report[0] == GPIO_REPORT
    return report[1] + (report[3] << 8)

def gpio_setup_pin2(dev):
    """Configure DIO7 pin as GPIO2"""
    dev.send_feature_report([0xA1, 6, 0])

def gpio_setup_pinA(dev):
    """Configure DIO0 pin as GPIOA"""
    dev.send_feature_report([0xA1, 8, 0])

def gpio_setup_pinG(dev):
    """Configure DIO12 pin as GPIOG"""
    dev.send_feature_report([0xA1, 9, 0])

if __name__ == '__main__':
    # GPIO pins toggling test
    import hid
    dev = hid.device()
    dev.open(DEVICE_VID, DEVICE_PID)
    out_pins = GPIO2|GPIO4|GPIO5|GPIOA|GPIOB|GPIOC|GPIOD|GPIOE|GPIOF|GPIOG|GPIOH
    gpio_setup_pin2(dev)
    gpio_setup_pinA(dev)
    gpio_setup_pinG(dev)
    while True:
        out_bits = out_pins & ~GPIOD
        gpio_write(dev, out_pins, out_bits)
        assert gpio_read(dev) & out_pins == out_bits
        time.sleep(1)
        out_bits = GPIOD
        gpio_write(dev, out_pins, out_bits)
        assert gpio_read(dev) & out_pins == out_bits
        time.sleep(1)
        print('.', end='', flush=True)
