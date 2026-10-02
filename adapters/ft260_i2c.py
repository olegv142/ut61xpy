"""
FTDI FT260 adapter I2C communication routines
"""

import time
import logging
log = logging.getLogger('DEV')

DEVICE_VID = 0x403
DEVICE_PID = 0x6030

# Transaction flags
FL_START = 2
FL_STOP  = 4
FL_START_STOP = FL_START | FL_STOP

# Status flags
STA_BUSY  = 1
STA_ERROR = 2

DEF_TOUT = 1
IDLE_DELAY = .025

def i2c_init(dev):
    dev.set_nonblocking(True)
    dev.send_feature_report([0xA1, 0x20]) # reset I2C

def i2c_query_status(dev):
    sta = dev.get_feature_report(0xC0, 61)
    return sta[1]

def i2c_write(dev, address: int, data: list[int], flag: int = FL_START_STOP):
    assert 0 < len(data) <= 60
    report_id = 0xD0 + (len(data) - 1) // 4
    payload = [report_id, address, flag, len(data)] + data
    dev.write(payload)

def i2c_read(dev,
        address: int, length: int, flag: int = FL_START_STOP,
        tout: float|None = None, idle_sleep: Callable[[float], None] = time.sleep
    ):
    assert 0 < length <= 60
    wait = tout if tout is not None else DEF_TOUT
    while True: # wait device ready
        sta = i2c_query_status(dev)
        if sta & STA_ERROR:
            log.error('bad status %u waiting addr %#x', sta, address)
            return None
        if not (sta & STA_BUSY):
            break
        idle_sleep(IDLE_DELAY)
        wait -= IDLE_DELAY
        if wait <= 0:
            log.error('timeout waiting addr %#x', address)
            return None

    dev.write([0xC2, address, flag, length, 0])
    while True: # wait response
        report = dev.read(64)
        if report:
            break
        idle_sleep(IDLE_DELAY)
        wait -= IDLE_DELAY
        if wait < 0:
            log.error('timeout reading addr %#x', address)
            return None

    if length != report[1]:
        log.error('bad length reading addr %#x: expects %u, got %u', address, length, report[1])
        return None
    sta = i2c_query_status(dev)
    if sta & (STA_BUSY | STA_ERROR):
        log.error('bad status %u reading addr %#x', sta, address)
        return None
    return report[2:2 + length]
