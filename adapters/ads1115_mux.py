"""
Helper functions for using ADS115 with FT260 adapter and 16 channel external
multiplexer (CD74HC4067) driven by GPIOB,C,D,E outputs of FT260.
"""

import os
import sys

if __package__: sys.path.append(os.path.realpath(os.path.dirname(__file__)))

from ads1115 import ADS1115Device
import ft260

MUX_GPIO_MASK = ft260.GPIOB | ft260.GPIOC | ft260.GPIOD | ft260.GPIOE

def channel_to_gpio_bits(channel: int) -> int:
    val = 0
    if channel & 1:
        val += ft260.GPIOB
    if channel & 2:
        val += ft260.GPIOC
    if channel & 4:
        val += ft260.GPIOD
    if channel & 8:
        val += ft260.GPIOE
    return val

def mux_read_positive(dev: ADS1115Device,
        channel: int, div: float, gain: int = 0,
        xgpio: int = 0, xgpio_mask: int = 0
    ) -> float:
    """
    Sample the particular positive channel (0..15) given the input divider ratio
    calculated as R0 / (R0 + R1), see schematic. To improve precision you can set
    gain to 1 if VCC <= 4V. The xgpio and xgpio_mask parameters can be used to
    control additional GPIO pins of the FT260 chip.
    """
    ft260.gpio_set(dev.dev, MUX_GPIO_MASK + xgpio_mask, channel_to_gpio_bits(channel) + xgpio)
    val = dev.exec_conversion(dev.MUX_1_G, gain)
    return val / div

def mux_read_negative(dev: ADS1115Device,
        channel: int, div: float, gain: int = 0,
        xgpio: int = 0, xgpio_mask: int = 0
    ) -> float:
    """
    Sample the particular negative voltage channel (0..15) given the input divider ratio
    calculated as R0 / (R0 + R2), see schematic. To improve precision you can set
    gain to 1 if VCC <= 4V. The xgpio and xgpio_mask parameters can be used to
    control additional GPIO pins of the FT260 chip.
    """
    ft260.gpio_set(dev.dev, MUX_GPIO_MASK + xgpio_mask, channel_to_gpio_bits(channel) + xgpio)
    vcc = dev.exec_conversion(dev.MUX_0_G, gain)
    val = dev.exec_conversion(dev.MUX_0_1, gain)
    return vcc - val / div

if __name__ == '__main__':
    if dev := ADS1115Device.open():
        with dev:
            dev.init()
            while dev.is_connected():
                print(
                    mux_read_positive(dev, 0, .5),
                    mux_read_negative(dev, 3, .5)
                )

 