"""
Bluetooth communication engine
"""

import threading
import asyncio
import logging

log = logging.getLogger('DEV')

evloop = None
evloop_thread = None

def _evloop_work():
    """Event loop worker routine"""
    asyncio.set_event_loop(evloop)
    evloop.run_forever()

def evloop_start():
    """Starts event loop in separate thread to handle BT stuff"""
    global evloop
    global evloop_thread
    if evloop is not None:
        return
    evloop = asyncio.new_event_loop()
    evloop_thread = threading.Thread(target=_evloop_work, daemon=True)
    evloop_thread.start()

def async_exec(co, wait=True):
    """Executes given co-routine and returns result"""
    evloop_start()
    try:
        future = asyncio.run_coroutine_threadsafe(co, evloop)
        return future.result() if wait else future
    except Exception as e:
        log.debug(e, exc_info=True)
        return None

def name_matches(devname, name):
    if not devname:
        return False
    if not name:
        return True
    if name[-1] != '*':
        return devname == name
    prefix = name[:-1]
    return devname[:len(prefix)] == prefix

def list_addrs(name):
    """Returns the list of addresses of BT devices with given name"""
    from bleak import BleakScanner
    async def a_list():
        return await BleakScanner.discover()
    addr_list = []
    if devices := async_exec(a_list()):
        for d in devices:
            if name_matches(d.name, name):
                addr_list.append(d.address)
    return addr_list
