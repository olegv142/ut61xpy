import hid
import time
import logging

log = logging.getLogger('DEV')

def dev_open(vid=0x1a86, pid=0xe429):
	devs = hid.enumerate(vid, pid)
	if not devs:
		log.error('not found')
		return None
	if len(devs) > 1:
		log.error('%d devices found' % len(devs))
		return None
	device = hid.device()
	try:
		device.open_path(devs[0]['path'])
	except:
		log.error('failed to open device')
		return None
	device.set_nonblocking(True)
	return device

def dev_query_raw(dev):
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
	try:
		val = float(''.join([chr(d) for d in data[5:12]]))
	except ValueError:
		return float('nan')
	mode, range = data[3], data[4] - ord('0')
	range_offset = {
		6 : 2, # Ohms
		9 : 1, # nF
	}
	if mode not in range_offset:
		return val
	return val * 10 ** (3*((range + range_offset[mode]) // 3))

if __name__ == '__main__':
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

