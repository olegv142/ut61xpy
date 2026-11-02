"""
FTDI FT260 UART functions
"""

import os
import sys
import time
import logging
import struct
import threading

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
    """
    Receive UART data. Note that the FT260 delivers data received in hid reports ASAP,
    typically once a millisecond. So with low baud rate it may deliver only single byte per hid report.
    The problem is that OS has a per-handle queue keeping only 32 recent hid reports. So the receiver
    should read reports faster than once in 32 milliseconds to avoid data loss.
    """
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

class UARTReceiver:
    """Class reading received data in separate thread"""
    IDLE_WAIT = .01

    def __init__(self, dev):
        self.dev    = dev
        self.worker = None
        self.cancel = None
        self.lock = threading.Lock()
        self.buff = []
        self.failed = False

    def start(self):
        assert self.worker is None
        self.cancel = False
        self.worker = threading.Thread(target=self._work, daemon=True)
        self.worker.start()

    def stop(self):
        assert self.worker is not None
        self.cancel = True
        self.worker.join()
        self.worker = None

    def _work(self):
        while not self.cancel:
            try:
                with self.lock:
                    chunk = uart_rx(self.dev)
                    self.buff += chunk
            except Exception as e:
                log.debug(e, exc_info=True)
                self.failed = True
                return
            time.sleep(self.IDLE_WAIT)

    def get(self) -> list[int]:
        assert self.worker is not None
        with self.lock:
            buff, self.buff = self.buff, []
            return buff

    def is_failed(self) -> bool:
        return self.failed


if __name__ == '__main__':
    import random

    dev = find_uart()
    uart_init(dev, 19200, PARITY_ODD)
    receiver = UARTReceiver(dev)
    receiver.start()
    BUNCH = 16
    try:
        while True:
            sent = []
            for _ in range(BUNCH):
                n = random.randrange(1, 60)
                chunk = list(random.randbytes(n))
                uart_tx(dev, chunk)
                sent += chunk
            time.sleep(.5)
            if receiver.is_failed():
                print('\naborted')
                break
            received = receiver.get()
            assert sent == received
            print('.', end='', flush=True)
    except KeyboardInterrupt:
        receiver.stop()
        assert not receiver.is_failed()
