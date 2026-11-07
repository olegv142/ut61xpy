"""
Silicon Labs CP2112 adapter I2C and GPIO communication routines
See https://www.silabs.com/documents/public/application-notes/an495-cp2112-interface-specification.pdf
"""

import time
import logging

log = logging.getLogger('DEV')

DEVICE_VID = 0x10C4
DEVICE_PID = 0xEA90

IDLE_DELAY = .005
READ_TOUT  = .025
BUSY_TOUT  = .050

# I2C status
STA_IDLE    = 0
STA_BUSY    = 1
STA_SUCCESS = 2
STA_FAILURE = 3

STA2_NACK_ADDR   = 0
STA2_BUSY_BUS    = 1
STA2_ARBITR_LOST = 2
STA2_NACK_READ   = 3
STA2_NACK_WRITE  = 4
STA2_SUCCESS     = 5

def i2c_init(dev):
    dev.set_nonblocking(True)
    # Set retry count to 1. With default value of 0 the failed write will be retried indefinitely till power off.
    dev.send_feature_report([0x06,
            0, 1, 0x86, 0xa0, # 100kHz clock
            2, # wake up address
            0, # auto send read (disabled)
            0, 0, # write timeout
            0, 0, # read timeout
            0, # SCL low timeout (disabled)
            1  # retry count
        ])

def read_packet(dev, pkt_id: int, tout = READ_TOUT) -> list[int] | None:
    while True:
        if pkt := dev.read(64):
            if pkt[0] == pkt_id:
                return pkt
        if tout <= 0:
            break
        time.sleep(IDLE_DELAY)
        tout -= IDLE_DELAY
    return None

def i2c_query_status(dev) -> tuple[int, int] | None:
    dev.write([0x15, 0x01])
    pkt = read_packet(dev, 0x16)
    return (pkt[1], pkt[2]) if pkt else None

def i2c_wait_idle_status(dev, tout = BUSY_TOUT) -> tuple[int, int] | None:
    while True:
        sta = i2c_query_status(dev)
        if sta is None:
            return sta
        if sta[0] != STA_BUSY:
            return sta
        if tout <= 0:
            return sta
        time.sleep(IDLE_DELAY)
        tout -= IDLE_DELAY

def i2c_wait_idle(dev) -> bool:
    """Write to the given address"""
    sta = i2c_wait_idle_status(dev)
    if sta is None:
        log.error('failed to query i2c status')
        return False
    if sta[0] in (STA_IDLE, STA_SUCCESS):
        return True
    if sta[0] == STA_FAILURE:
        log.debug('bad i2c status: %s', sta)
        return False
    log.error('timeout waiting i2c idle status: %s', sta)
    return False

def i2c_write(dev, address: int, data: list[int]):
    """Read from the given address"""
    assert 0 <= len(data) <= 61
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
    return report[3:length + 3]

def i2c_write_read(dev, address: int, wr_data: list[int], length: int) -> list[int]|None:
    """Write and read in single I2C transaction"""
    dev.write([0x11, address << 1, 0, length, len(wr_data)] + wr_data)
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
    return report[3:length + 3]


def i2c_probe(dev, address: int):
    """Test presence of the address on the bus. Typically the zero payload write is used for that purpose.
    Unfortunately the CP2112 completely ignores NAKed address during such transaction. So we are using
    dummy 1-bytes read and check STA2_NACK_ADDR status bit afterwards.
    """
    dev.write([0x10, address << 1, 0, 1])
    sta = i2c_wait_idle_status(dev)
    if sta is None:
        return False
    if sta[0] in (STA_IDLE, STA_SUCCESS):
        return True
    if sta[0] == STA_FAILURE:
        if sta[1] == STA2_NACK_ADDR:
            return False
        if sta[1] == STA2_NACK_READ:
            return True
    log.warning('bad i2c status probing addr %d: %s', address, sta)
    return False

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

GPIO_LED_RED   = GPIO0
GPIO_LED_GREEN = GPIO1

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
    import hid    
    def test_gpio(dev):
        """GPIO pins toggling test"""
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

    def test_scan(dev):
        """Scan bus for devices"""
        for addr in range(8, 128):
            print(('%02x ' % addr) if i2c_probe(dev, addr) else '-- ', end='' if (addr + 1) % 8 else '\n')

    dev = hid.device()
    dev.open(DEVICE_VID, DEVICE_PID)
    i2c_init(dev)
    test_scan(dev)
    test_gpio(dev)
