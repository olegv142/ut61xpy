"""
FTDI FT260 UART functions
"""

import os
import sys
import time
import logging
import struct
import random

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

import device
from ft260 import DEVICE_VID, DEVICE_PID

log = logging.getLogger('DEV')

def find_uart():
    """Find UART device and open it"""
    devs = device.find_hid_devices(DEVICE_VID, DEVICE_PID, ifnum=1)
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
        log.error('failed to open FT260 at %s', path)
        return None
    return dev

UART_DISABLED     = 0
FLOW_CTL_RTS_CTS  = 1
FLOW_CTL_DTR_DSR  = 2
FLOW_CTL_XON_XOFF = 3
FLOW_CTL_NONE     = 4

PARITY_NONE = 0
PARITY_ODD  = 1
PARITY_EVEN = 2

def uart_init(dev, baud_rate: int, parity: int = PARITY_NONE, flow_ctrl: int = FLOW_CTL_NONE):
    """Initialize UART given baud rate and parity"""
    dev.set_nonblocking(True)
    dev.send_feature_report([0xA1, 0x40]) # reset UART
    dev.send_feature_report([0xA1, 0x41,  # configure UART
            flow_ctrl,
            *struct.pack('<I', baud_rate),
            8, # data bits
            parity,
            0, # one stop bit
            0  # no break
        ])

def uart_disable(dev):
    """Disable UART and use its pins as GPIO"""
    uart_init(dev, 0, flow_ctrl = UART_DISABLED)

def data_report_id(length: int):
    return 0xF0 + (length - 1) // 4

def uart_tx(dev, data: list[int]):
    """Transmit chunk of data"""
    assert 0 < len(data) <= 60
    payload = [data_report_id(len(data)), len(data)] + data
    dev.write(payload)

def uart_rx(dev, tout=0) -> list[int]:
    """Receive UART data"""
    data = []
    IDLE_WAIT = .01
    while True:
        if pkt := dev.read(64):
            if 0xF0 <= pkt[0] <= 0xFE:
                data_len = pkt[1]
                data += pkt[2:2+data_len]
        elif tout <= 0:
            return data
        else:
            time.sleep(IDLE_WAIT)
            tout -= IDLE_WAIT

if __name__ == '__main__':
    dev = find_uart()
    uart_init(dev, 19200, PARITY_ODD)
    BUNCH = 4
    while True:
        sent = []
        for _ in range(BUNCH):
            n = random.randrange(1, 60)
            chunk = list(random.randbytes(n))
            uart_tx(dev, chunk)
            sent += chunk
        received = uart_rx(dev, 1)
        assert sent == received
        print('.', end='', flush=True)
