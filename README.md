# UNI-T UT61B/D/E+ digital multi-meter communication tools
The UNI-T UT61E+ is high precision low cost digital multi-meter with optically isolated USB interface which makes it perfect choice for hobbyist and professionals on tight budget.
The UT61B/D+ models are lower cost 6000 count versions sharing the same excellent DC voltage measuring accuracy of 10uV and having some additional features like thermocouple measuring (UT61D+).
This repository provides simple alternative to vendor data collection program. Since the code is written in python it may be easily incorporated onto your complex measuring or automation system. 

The project is inspired by https://github.com/aroum/unit_ut61eplus_python & https://github.com/ljakob/unit_ut61eplus.
The code was reworked with the following goals in mind:
 - keep code as simple as possible
 - ensure seamless working on Windows and Linux
 - create simple cli tool (**ut61xp-get**) for data collection and visualization
 - support dual channel (DC+AC mode of UT61E+) reading and plotting

## Installation

```
git clone https://github.com/olegv142/ut61xpy.git
```

To use this code you will need *hidapi* package. Use *pip install hidapi* to install it.

To use graph plotting options of **ut61xp-get** data acquisition tool you will need *matplotlib* package. Use *pip install matplotlib* to install it. The tool may be executed without *matplotlib* package installed unless you use *-g* (show data graph) option.

## Basic usage

The **ut61xp-get** will auto detect UT-D09A USB adapter provided that there is exactly one such adapter connected to your computer. The **ut61xp-get list** command prints paths for all connected adapters. The **ut61xp-get once** reads single value from the connected device and prints it to standard output. The **ut61xp-get data** reads values continuously from the connected device and either prints them or saves to the file if *-f/--file* option is provided. With *-p/--progress* option the tool will output dots to standard output while saving values to the file to indicate progress. In case the current reading is invalid (overflowed) the dot will be replaced by exclamation mark. To terminate data reading one can press Ctrl-C. The output file will contain time in seconds since readout start as the first column. With *-e/--epoch* option the epoch time will be used instead. One can use *-d/--delimiter* option to set additional delimiter to be used between columns which is the single space by default. With *-o/--offset, -m/--mult* options the data will be linearly scaled before saving / plotting. These options are handy to remove fixed offset from the data or to convert voltage across current sensing resistor to actual current value. The *-i/--interval* option may be used to specify data reading interval in seconds. Using zero value will result in reading with maximal possible rate.

## Dual channel mode

Dual channel mode is handy while reading data in DC+AC mode of UT61E+. To use this mode you will need to properly setup your device and specify filename for storing second channel by means of *-a/--alt-file* option. This may be convenient, but note that DC+AC mode has several disadvantages compared to other modes:
 - it takes ~0.7 sec to read single value of the single channel
 - the voltage channel fluctuates much more than in other modes

## Graph plotting

The **ut61xp-get data** command will plot data read from device in separate window if *-g* option is provided. To terminate data reading in such mode one can just close graph window. With dual channel mode the graph window will contain two plots. The *-w/--wnd* option may be used to limit the number of recent data samples utilized to produce the plot by the specific number. You can use pan/zoom controls of the graph window while reading the data or use the dedicated button to save plot to the file, yet the acquisition will be paused until you done with plot saving. One can add any number of additional horizontal lines at specific levels to mark some specific value boundaries with *--hline* and *--alt-hline* options (the latter draws them on the second channel plot). These options may be used multiple times to add multiple horizontal lines. There are several other options that can be used for styling the graph window. One can set window title (*-t/--title*), plot title (*--plot-title, --alt-title*), data line style (*--line-style*), horizontal line style (*--hline-style*), data line colors (*--line-color, --alt-line-color*), horizontal line color (*--hline-color*).

## Using configurations

The configuration is the file storing the full set of command line options in the form of json dictionary. Use *--cfg-save* to create such file filled with options specified in the current command line and *-c/--cfg-load* option to load such file back. They may be handy to save typing and even more importantly to make data acquisition from several devices easier. Several examples of using them while reading data from several devices simultaneously will be given below.

## Printing data statistics

With *-s/--stat* the **ut61xp-get data** command will print various collected data statistic metrics upon acquisition termination. In particular
 - the number of data samples (total and valid)
 - the min / max values
 - the median and pure average values
 - the standard deviation (absolute and relative)
 - the 3rd central moment relative to the standard deviation (*skewness*)
 - the 4th central moment relative to the standard deviation minus 3 (*kurtosis exess*)

The last two metrics may be used to characterize deviations from the mean. The smaller they are the close the values distribution to the standard one with *Gaussian* noise.


## Getting help

Execute **ut61xp-get** tool with *-h* option to get detailed information about command line options. On Windows:
```
python ut61xpy/ut61xp-get -h
python ut61xpy/ut61xp-get data -h
```
On Linux the following will work either:
```
./ut61xpy/ut61xp-get -h
./ut61xpy/ut61xp-get data -h
```

