"""
CH347T USB HID adapter I2C API
See https://www.wch-ic.com/downloads/CH347DS1_PDF.html
The following repositories were used as a reference:
https://github.com/i2cy/CH347-HIDAPI
https://github.com/serfreeman1337/go-ch347
"""

import time
import logging

log = logging.getLogger('DEV')

DEVICE_VID = 0x1A86
DEVICE_PID = 0x55DC
DEVICE_IFN = 1

I2CMode0 = 0 # Low rate 20KHz
I2CMode1 = 1 # Standard rate 100KHz
I2CMode2 = 2 # Fast rate 400KHz
I2CMode3 = 3 # High rate 750KHz

READ_TOUT_MS = 20

def i2c_init(dev, mode: int = I2CMode1):
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

def i2c_tx_raw(dev, data: list[int], read_len: int = 0) -> Tuple[bool, list[int]]:
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

    dev.set_nonblocking(False)
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

def i2c_probe(dev, address: int) -> bool:
    """CXheck the device presence at given address"""
    sta, ret = i2c_tx_raw(dev, [address << 1]) # Just check if address was acknowledged
    return sta

if __name__ == '__main__':
    import hid

    def test_scan(dev):
        """Scan bus for devices"""
        for addr in range(8, 128):
            print(('%02x ' % addr) if i2c_probe(dev, addr) else '-- ', end='' if (addr + 1) % 8 else '\n')

    dev = hid.device()
    dev.open(DEVICE_VID, DEVICE_PID)
    i2c_init(dev)
    test_scan(dev)


