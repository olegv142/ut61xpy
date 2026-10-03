"""
FTDI FT260 adapter I2C communication routines
"""

import time
import logging
from collections.abc import Callable
log = logging.getLogger('DEV')

DEVICE_VID = 0x403
DEVICE_PID = 0x6030

# Transaction flags
FL_START = 2
FL_STOP  = 4
FL_START_STOP = FL_START | FL_STOP

# Status flags
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

def i2c_write(dev, address: int, data: list[int], flags: int = FL_START_STOP) -> bool:
    assert 0 < len(data) <= 60
    report_id = 0xD0 + (len(data) - 1) // 4
    payload = [report_id, address, flags, len(data)] + data
    dev.write(payload)
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
