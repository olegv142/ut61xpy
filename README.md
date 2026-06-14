# UNI-T UT61E+ digital multi-meter communication tools
The UNI-T UT61E+ is high precision low cost digital multi-meter with optically isolated USB interface which makes it perfect choice for hobbyist and professionals on tight budget.
This repository provides simple alternative to vendor data collection program. Since the code is written in python it may be easily incorporated onto your complex measuring or automation system. 

Its inspired by https://github.com/aroum/unit_ut61eplus_python & https://github.com/ljakob/unit_ut61eplus.
The code was reworked with the following goals in mind:
 - keep code as simple as possible
 - ensure seamless working on Windows and Linux
 - create simple cli tool (**ut61ep-get**) for data collection and visualization

To use this code you will need *hid* package or *hidapi* on windows. Use pip to install it.

To use graph plotting options of **ut61ep-get** data acquisition tool you will need matplotlib package. The tool may be executed without matplotlib package installed unless you use -P (show data graph) option.
