# UNI-T UT61E+ digital multi-meter communication tools
The UNI-T UT61E+ is high precision low cost digital multi-meter with optically isolated USB interface which makes it perfect choice for hobbyist and professionals on tight budget.
This repository provides simple alternative to vendor data collection program. Since the code is written in python it may be easily incorporated onto your complex measuring or automation system. 

Its inspired by https://github.com/aroum/unit_ut61eplus_python & https://github.com/ljakob/unit_ut61eplus.
The code was reworked with the following goals in mind:
 - keep code as simple as possible
 - ensure seamless working on Windows and Linux
 - create simple cli tool (**ut61ep-get**) for data collection and visualization

To use this code you will need *hidapi* package. Use pip to install it.

To use graph plotting options of **ut61ep-get** data acquisition tool you will need *matplotlib* package. The tool may be executed without *matplotlib* package installed unless you use -g (show data graph) option. On Linux you will probably have to run **ut61ep-get** under the root to be able to read data from it.

You can run several instances of **ut61ep-get** tool to read from several devices simultaneously. To be able to do it you have to specify device path explicitly with **--path** option since device auto-discovery works with single connected device only. To get the list of connected devices one can use **ut61ep-get list** command. You can run **ut61ep-get** without parameters to obtain full information about its usage.
