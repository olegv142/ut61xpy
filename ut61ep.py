"""
The UNI-T UT61E+ digital multi-meter communication helper.
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

log = logging.getLogger('DEV')

def dev_open_path(path):
	"""Open device given the path"""
	device = hid.device()
	try:
		device.open_path(path)
	except:
		log.error('failed to open device ' + path)
		return None
	device.set_nonblocking(True)
	return device

def dev_open(vid=0x1a86, pid=0xe429):
	"""Open device given its VID, PID"""
	devs = hid.enumerate(vid, pid)
	if not devs:
		log.error('not found')
		return None
	if len(devs) > 1:
		log.error('%d devices found' % len(devs))
		return None
	return dev_open_path(devs[0]['path'])

def dev_query_raw(dev):
	"""Read and validate raw data packet"""
	attempts = 10
	CMD = [0xAB, 0xCD, 0x03, 0x5E, 0x01, 0xD9]
	dev.write([0, len(CMD)] + CMD)
	while True:
		time.sleep(.1)
		buf = dev.read(64)
		if buf:
			break
		attempts -= 1
		if attempts <= 0:
			return None
	data_len = buf[0]
	if data_len <= 2 or data_len > 63:
		log.error('bad length: %d' % data_len)
		return None
	data = buf[1:1+data_len]
	cs = data[-2] * 256 + data[-1]
	if cs != sum(data[:-2]):
		log.error('bad checksum')
		return None
	return data[:-2]

def get_value(data):
	"""
	Convert raw data to the floating point value. Here we don't
	care about units since the caller should be aware of them.
	It set mode dial manually after all. So in the mV mode the
	result is expressed in mV rather than volts.
	"""
	try:
		val = float(''.join([chr(d) for d in data[5:12]]))
	except ValueError:
		return float('nan')
	# Apply range multiplier
	mode, range = data[3], data[4] - ord('0')
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

if __name__ == '__main__':
	# Open device and print raw readings as well as the corresponding floating point value
	dev = dev_open()
	if dev:
		last_data = None
		while True:
			data = dev_query_raw(dev)
			if data:
				if last_data is None: print()
				print(data[3], ''.join([chr(d) for d in data[4:12]]), get_value(data))
			else:
				print('.', end='', flush=True)
			last_data = data

