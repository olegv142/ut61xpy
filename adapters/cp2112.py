"""
Silicon Labs CP2112 adapter I2C and GPIO communication routines
"""

import time
import logging

log = logging.getLogger('DEV')

DEVICE_VID = 0x10C4
DEVICE_PID = 0xEA90

MIN_DELAY = .005
READ_TOUT = .025
BUSY_TOUT = .050

# I2C status
STA_IDLE    = 0
STA_BUSY    = 1
STA_SUCCESS = 2
STA_FAILURE = 3

def i2c_init(dev):
    dev.set_nonblocking(True)

def read_packet(dev, pkt_id: int):
    wait = READ_TOUT
    delay = MIN_DELAY
    while True:
        if pkt := dev.read(64):
            if pkt[0] == pkt_id:
                return pkt
        if wait <= 0:
            break
        time.sleep(delay)
        wait -= delay
        delay *= 2
    return None

def i2c_query_status(dev) -> int:
    dev.write([0x15, 0x01])
    pkt = read_packet(dev, 0x16)
    return pkt[1] if pkt else None

def i2c_wait_idle(dev) -> bool:
    wait = BUSY_TOUT
    delay = MIN_DELAY
    while True:
        sta = i2c_query_status(dev)
        if sta in (STA_IDLE, STA_SUCCESS):
            return True
        if sta != STA_BUSY:
            log.debug('bad status %sx', sta)
            return False
        if wait <= 0:
            break
        time.sleep(delay)
        wait -= delay
        delay *= 2
    log.debug('bad status %s', sta)
    return False

def i2c_write(dev, address: int, data: list[int]):
    assert 0 < len(data) <= 61
    payload = [0x14, (address << 1), len(data)] + data
    dev.write(payload)
    if not i2c_wait_idle(dev):
        log.error('error writing addr %#x', address)
        return False
    return True

def i2c_read(dev, address: int, length: int) -> list[int]|None:
    dev.write([0x10, address << 1, 0, length])
    if not i2c_wait_idle(dev):
        log.error('error reading addr %#x', address)
        return None
    dev.write([0x12, length])
    report = read_packet(dev, 0x13)
    if report is None:
        log.error('timeout reading addr %#x', address)
        return None
    if len(report) < 3 + length:
        log.error('bad packet length reading addr %#x: expects %u, got %u',
            address, length + 3, len(report))
        return None
    if length != report[2]:
        log.error('bad data length reading addr %#x: expects %u, got %u',
            address, length, report[2])
        return None
    return bytes(report[3:length + 3])

#
# GPIO routines
#

# GPIO bits definitions
GPIO0 = 1
GPIO1 = GPIO0 << 1
GPIO2 = GPIO1 << 1
GPIO3 = GPIO2 << 1
GPIO4 = GPIO3 << 1
GPIO5 = GPIO4 << 1
GPIO6 = GPIO5 << 1
GPIO7 = GPIO6 << 1

# Note that CJMCU-2112 board has the following
# cryptically named gpio pins:
# WAK - GPIO2
# INT - GPIO3
# RST - GPIO4
# So there are 6 gpio pins available.
# The GPIO0,1 are connected to on-board LEDs:
# GPIO0 - red   LED, active low
# GPIO1 - green LED, active low

def gpio_config(dev, out_mask: int, push_pull_mask: int = 0xff):
    """
    Set bitmask of output pins and push pull pins. Pins having
    corresponding bit set to 0 in push_pull_mask will be configured as open drain.
    Note that all pins also have built-in pull up resistors ~5k. The only difference
    between push pull and open drain configuration is the high level driving current. In
    push pull configuration the chip is able to deliver ~35mA of short circuit current.
    """
    dev.send_feature_report([0x02, out_mask, push_pull_mask, 0, 0])

def gpio_set(dev, bits: int, mask: int):
    """
    Set output pin levels given the valid bits mask. Pins having corresponding bit
    set to 0 in the mask will not be affected.
    """
    dev.send_feature_report([0x04, bits, mask])

def gpio_get(dev) -> int:
    """
    Get input/output pin levels as bitmask. This function returns the actual pin level
    even in case the pin is configured as output. So it will return zero bit for short
    circuited pin even if it was set to high level by gpio_set.
    """
    response = dev.get_feature_report(0x03, 2)
    return response[1]

if __name__ == '__main__':
    # GPIO pins toggling test
    import hid
    dev = hid.device()
    dev.open(DEVICE_VID, DEVICE_PID)
    pins = 0xff
    gpio_config(dev, pins)
    while True:
        gpio_set(dev, 0x55, pins)
        assert gpio_get(dev) == 0x55
        time.sleep(1)
        gpio_set(dev, ~0x55 & 0xff, 0x55)
        assert gpio_get(dev) == 0
        time.sleep(1)
        gpio_set(dev, 0xaa, pins)
        assert gpio_get(dev) == 0xaa
        time.sleep(1)
        gpio_set(dev, ~0xaa & 0xff, ~0xaa & 0xff)
        assert gpio_get(dev) == 0xff
        time.sleep(1)
        print('.', end='', flush=True)

