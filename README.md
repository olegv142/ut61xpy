# The cross-platform digital multimeter communication and data plotting tool supporting variety of popular UNI-T, OWON, ANENG, ZOTEK, BSIDE multimeters and FNIRSI USB testers.

This repository provides simple alternative to vendor data collection programs. It works uniformly on Windows and Linux (not tested on MacOS). One can use it either from command line or GUI. Since the code is written in python it may be easily incorporated onto your complex measuring or automation system. 

The project was started as robust and simple tool for reading data from UNI-T UT61E+ multimeter. It was inspired by https://github.com/ljakob/unit_ut61eplus and https://github.com/aroum/unit_ut61eplus_python. Since then the number of other multimeter and USB tester models were supported and the project was extended with the following goals in mind:
 - keep code as small and simple as possible
 - support for USB and Bluetooth communication channels
 - support for dual channel reading and plotting (DC+AC mode of UT61E+ for ex.)
 - seamless working on Windows and Linux
 - convenient working with several devices simultaneously
 - single CLI tool (**ut61xp-get**) for data collection and visualization
 - simple GUI frontend application (**ut61xp-start**) with the same capabilities as CLI tool
 - ease of adding new multimeter models
 - ease of reuse in other projects

## Supported devices

### UNI-T multimeters
- The UNI-T UT61E+ is high precision low cost digital multimeter with optically isolated USB interface which makes it perfect choice for hobbyist and professionals on tight budget.
The tool works via USB HID adapter D-09A commonly supplied with UT61X+ multimeter. Alternatively one can use UT-D07B Bluetooth adapter which provides the wireless communication channel. However its relatively expensive and very slow. The minimum achievable data readout interval is around 180 msec for USB adapter and around 800 msec for Bluetooth adapter. The latter works especially bad in dual AC+DC mode when timely reading is important.
- The UT61B/D+ models are lower cost 6000 count versions sharing the same DC voltage measuring accuracy of 10µV and having some additional features like thermocouple measuring (UT61D+). They also have smaller shunt resistance for current measurement (100 Ohm vs 500 Ohm for the UT61E+ in µA mode, 1 Ohm vs 5 Ohm in mA mode) at the expense of the worse resolution (0.1 µA vs 0.01 µA, 0.01 mA vs 0.001 mA).
- The UT60BT is inexpensive consumer grade 10000 counts multimeter with built-in BT adapter using the same protocol as UT61X+ devices. It has even better resolution than UT61X+ of 1pF in capacitance mode and 1µV in millivolt mode. Unfortunately, this latter advantage is offset by an annoying hack. To hide fluctuations in readings, the device uses a dead band from -10 µV to +10 µV, where the voltage is always read as zero. Similar dead band exists in A mode between -5mA and +5mA in both UT60BT and UT61X+. Besides it has only two ranges for current measurement. In µA range it has quite high resistance of 3.3 kOhm due to using PTC resettable fuse. Interestingly, the actual shunt resistance is 45 Ohm. So almost all its input resistance comes from the fuse.

### OWON Bluetooth multimeters
The tool supports the number of Bluetooth multimeters using the same 'BDM' protocol. In particular its tested with the following devices:
- The B41T+ is a multimeter with 22000 counts and built-in Bluetooth. However, it is relatively expensive and has a number of disadvantages, including poor display quality and high power consumption when Bluetooth is enabled.
- The OW18E is the most recent 20000 counts model with 1µV resolution. Its better than B41T+ in every respect. It has better display, very low power consumption (1.5mA with BT turned on) and has nice protective rubber sleeve. But at the same time it has one very unpleasant 'feature' - dead band from -5µV to +5µV where input voltage always reads as zero.
- The OW18B is a cheap, low resolution model in OW18 family with built in Bluetooth. It also has better display and lower power consumption than B41T+.
- The CM2100B clamp meter is inexpensive and quite versatile device with 20000 counts capable of measuring AC or DC current without any electrical contact. Note though that while measuring by the clamp it delivers 2000 counts only.

Other compatible OWON multimeters like B35T+ should work with this tool as well.

### OWON desktop multimeters
OWON produces a line of desktop multimeters that use the SCPI communication protocol via USB connection. The tool is tested with XDM1241 model. This is a 55000 count multimeter with 1µV resolution. Its fast on paper but may be painfully slow in practice especially in capacitance mode. The SCPI command set implemented by this device is very basic. However, it significantly outperforms any handheld multimeter in its voltage and current measurement capabilities, thanks to its excellent 1 µV resolution and relays that switch shunt resistors depending on the current measurement range selected. Other similar models like XDM1041 should work with this tool as well.

### OWON programmable laboratory power supplies
OWON produces a line of programmable laboratory power supplies that use the SCPI communication protocol via USB connection. The tool provides the way to read output current value and optionally output voltage in alternative measuring channel. The tool is tested with SPE3051 device. It should be noted that the accuracy of the current values reported by such a device is quite low. It has dead band below 10mA where the current is always reported as zero. Higher current values are reported inaccurately with constant offset of +5mA.

### OWON programmable electronic loads
OWON produces a line of programmable electronic loads that use the SCPI communication protocol via USB or RS232 connection. The OEL1515 for example can sink current of up to 15A at the voltage of up to 150V. They provide much better resolution in measuring current and voltage than programmable power sources. These device are not directly supported by **ut61xp-get** and **ut61xp-start** tools, but you can interact with them using your own code. See [Working with OWON programmable electronic load](#working-with-owon-programmable-electronic-load).

### ANENG / ZOTEK / BSIDE multimeters
This tool supports Aneng AN9002 model also sold as ZOTEK/BSIDE ZT-300AB. It has 6000 counts display with 10µV voltage measuring resolution, 0.1µA current measuring resolution with 100 Ohm shunt resistance and 1pF capacity resolution. The stand is terrible, the quality of the probes is questionable, but other than that its quite usable with good display and small power consumption (3.5mA with Bluetooth active). Despite such low power consumption it has the best Bluetooth communication range among all tested multimeters. The only thing noticed that may be considered as a drawback is relatively low input impedance in voltage measuring mode. Its around 1 MOhm while other DMM typically have an input impedance of around 10 MOhm.

The Zotek/Aneng multimeters use display segment based encoding for BT communications. So there are as many protocol variants as there are displays in use. Therefore, this tool will not work with other 'Bluetooth DMM' devices like ZT-5B, ZT-5BQ, ZT-5566. Yet the AN9002 is the most interesting model considering the ergonomics and price / performance. The price of this device is smaller than the cost of the single UNI-T Bluetooth adapter.

### FNIRSI USB testers
FNIRSI produces a line of USB testers capable of measuring USB bus voltage, load current and some other parameters. The tool supports reading USB bus current and optionally voltage in alternative measuring channel. Currently supported devices are FNAC28, FNB48P, FNB58 and FNB-C2. The data can be read either via USB or Bluetooth connection (if supported by device). While Bluetooth is convenient the USB connection provides significantly better resolution and reliability.

## Installation
### Working with sources
```
git clone https://github.com/olegv142/ut61xpy.git
```

Alternatively you can download source code archive and unpack it. 
The code uses *hid/hidapi* package for communicating with USB HID multimeters, *pyserial* package for communicating with USB multimeters using serial protocol, *bleak* package for communicating with Bluetooth multimeters and *matplotlib* package for data chart plotting. They can be installed by various ways depending on you operating system. To install them with pip (Windows/Lunix):
```
pip install hidapi pyserial bleak matplotlib
```
On Linux you probably have to create virtual environment first or install packages using package manager like the following:
```
sudo apt install python3-hidapi python3-serial python3-bleak python3-matplotlib
```
On some systems the package *python3-hid* is available instead of *python3-hidapi*. Note that you don't have to install the particular package unless you are not going to use the corresponding features. In particular, you can use the **ut61xp-get** tool without *matplotlib* package if you are not going to plot data charts. You can work without *bleak* package if you have only USB multimeters and without *hid/hidapi* package if you have only Bluetooth multimeters.

### Using portable binaries
Working with sources is the preferred way of using this tool on Linux. On Windows one can just download latest [release](https://github.com/olegv142/ut61xpy/releases) of portable binaries as self-extracting archive, unpack them to readable folder, then go to the *dmm-tools* folder and double click **ut61xp-start** acquisition launcher to start working immediately without any additional installation efforts. See [Working with GUI](#working-with-gui) section for more details. To make your work on windows more convenient you can go to the *dmm-tools/scripts* folder and double click on the *create_links.bat* and *associate_data.bat* scripts. See [Working with standalone executables](#working-with-standalone-executables) for more details. See also notes about [security concerns](#the-windows-protected-your-pc-warning-always-appears-on-attempt-to-run-self-extracting-distribution-archive) related to this installation method.

# Working with command line
The CLI workflow is built around **ut61xp-get** script which implements several commands for data acquisition, plotting and simple statistic analysis like making histogram and calculating momentums. The script has many command line options that we discuss briefly in the following sections. We first consider working with UNI-T UT61B/D/E+ multimeters via the standard USB HID adapter UT-D09A typically supplied with the device. After that we will consider working via Bluetooth and communicating with other supported multimeter models.

## Basic usage

The **ut61xp-get** will auto detect UT-D09A USB adapter provided that there is exactly one such adapter connected to your computer. The **ut61xp-get list** command prints paths for all connected adapters. The **ut61xp-get once** reads single value from the connected device and prints it to standard output. The **ut61xp-get data** reads values continuously from the connected device and either prints them or saves to the file if *-f/--file* option is provided. With *-p/--progress* option the tool will output dots to standard output while saving values to the file to indicate progress. In case the current reading is invalid (overflowed) the dot will be replaced by exclamation mark. To terminate data reading one can press Ctrl-C. The output file will contain time in seconds since readout start as the first column. With *-e/--epoch* option the epoch time will be used instead. One can use *-d/--delimiter* option to set additional delimiter to be used between columns which is the single space by default. With *-o/--offset, -m/--mult* options the data will be linearly scaled before saving / plotting. These options are handy to remove fixed offset from the data or to convert voltage across current sensing resistor to actual current value. The *-i/--interval* option may be used to specify data reading interval in seconds. The default interval is zero so that the data is read with maximal possible rate.

## Automatic file naming

In case the file with the name provided with *-f* option already exists it will be silently overwritten. Therefore, you will either have to use a different name the next time you run data collection, or move the data file to a different location if you need it later. The **ut61xp-get** tool offers a convenient alternative: automatic file naming. In case the name given with *-f* option contains % character(s) it will be treated as the template for current date/time formatting as performed by [strftime](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior) function. Another useful feature is the possibility to add directory part to filename argument. The directory will be automatically created if not yet exists. For example with *-f %Y-%m-%d/%H%M%S.data* option the file with name representing current time will be placed to the directory with the name representing current date. In case the name given with *-f* option contains ${MODEL} substring, it will be replaced by the currently used multimeter model making filenames more informative.

## Dual channel mode

Dual channel mode is handy while reading data in DC+AC mode of UT61E+. To use this feature you will need to choose proper mode on the multimeter mode dial and specify filename for storing second channel by means of *-a/--alt-file* option. Other multimeter models may support dual channel reading for AC voltage and frequency in particular. Programmable power sources and USB testers may report the load current and voltage. 

## Graph plotting

The **ut61xp-get data** command will plot data read from device in separate window if *-g/--graph* option is provided. To terminate data reading in such mode one can just close graph window. With dual channel mode the graph window will contain two plots. The *-w/--wnd* option may be used to limit the number of recent data samples utilized to produce the plot by the specific number. Alternatively, if expressed as negative number of seconds the *-w/--wnd* option will limit the time range of the plot. You can switch window mode on / off while plotting data by pressing 'w' hot key in the plot window. One can add any number of additional horizontal lines at specific levels to mark some specific value boundaries with *--hline* and *--alt-hline* options (the latter draws them on the second channel plot). These options may be used multiple times to add multiple horizontal lines. There are several other options that can be used for styling the graph window. One can set window title (*-t/--title*), plot title (*--plot-title, --alt-title*), data line style (*--line-style*), horizontal line style (*--hline-style*), data line colors (*--line-color, --alt-line-color*), horizontal line color (*--hline-color*). In case plot title is not provided as command line argument the current measuring mode reported by multimeter will be used as the title. In case window title is not provided as command line argument the multimeter model will be used as the title. You can use plot navigation bar as usual. In particular, you can use pan/zoom controls of the graph window while reading the data or use the dedicated button to save plot to the file, yet the acquisition will be paused until you done with plot saving. Additionally double clicking the plot will toggle full screen mode. To open the graph window in full screen mode from the start, you can use the *--full-screen* command line option. With '-z/--with-zero' the zero value will always be included in the displayed vertical axis range. This will help to understand the scale of the signal fluctuations with respect to the signal value. Pressing 'z' key in plot window switches 'with-zero' mode on / off regardless of the '-z/--with-zero' option.

## Plotting already collected data

The **ut61xp-get plot** command followed by the list of filenames plots the data sets reading them from the given files. It is just a convenient tool for viewing the collected data without any complex charting features. You can use plot navigation bar as usual and use double click to toggle full screen mode. While plotting single file you can press space to print statistics to console or press t to toggle showing statistics on the plot window. See [Printing data statistics](#printing-data-statistics) section for more details.

## Data units and scaling

The data reported by multimeter typically contains information about measurement mode (say voltage) and/or measurement units (say millivolts). The units may be voluntary changed by the device as a result of the automatic range selection (for ex. millivolts to volts). Many vendor provided and third party data readout applications just save data in the units reported by device. This practice is bad since the data with sudden change of units will show abrupt jump with several orders of magnitude and will look as a mess overall. The **ut61xp-get** tool takes special care to guarantee that the units of the data will be the same no matter how auto-ranging works on the particular device. The particular units used for the data representation will be shown as the default plot title with *-g* option and will be saved in the first line of the output file with *-f* or *-a* options.

## Using configurations

The configuration is the file storing the full set of command line options in the form of json dictionary. Use *--cfg-save* option with **ut61xp-get data** command to create such file filled with options specified in the current command line and *-c/--cfg-load* option to load such file back. They may be handy to save typing and even more importantly to make data acquisition from several devices easier. Several examples of using them while [working with several devices simultaneously](#working-with-several-devices-simultaneously) will be given below.

## Printing data statistics

With *-s/--stat* option the **ut61xp-get data** command will print various collected data statistic metrics upon acquisition termination. In particular:
 - the number of data samples (total and valid)
 - the min / max values
 - the median and pure average values
 - the standard deviation (absolute and relative)
 - the integral in val * sec units
 - the 3rd central moment relative to the standard deviation (*skewness*)
 - the 4th central moment relative to the standard deviation minus 3 (*kurtosis exess*)

The last two metrics may be used to characterize deviations from the mean. The smaller they are the closer the value distribution to the standard one with *Gaussian* noise.

### Print statistics while plotting data

With *-S/--plot-stat* option the **ut61xp-get data** command will show data statistics on the plot window and update it on every new data sample. The *--plot-stat-loc* option may be used to specify the particular location on the plot where the statistics box will be placed. The default is 'lower left'. With *--plot-stat-loc "best"* options the location will be chosen automatically to minimize overlapping with data curve. The statistic display area may be shown / hidden while plotting by pressing 't' key. This hot key works regardless of the *-S/--plot-stat* option.
Another way to view current statistics is to press the space bar in the chart window. This will print the statistics on the terminal so you can easily copy / paste them.

### Print statistics given the existing data file

The **ut61xp-get stat input_file** command prints statistics of the data stored in the given *input_file*.

## Plot window hotkeys
The following keys (partially discussed above) have special meaning when pressed in the data plot window:
| key                     | meaning                                                                                    |
|-------------------------|--------------------------------------------------------------------------------------------|
| space                   | print current statistics to terminal so you can easily copy/paste them                     |
| t                       | show / hide statistics display area on the plot                                            |
| w                       | turn data window on / off (provided that it was initially configured by *-w/--wnd* option) |
| z                       | turn on / off 'with-zero' mode                                                             |
| p                       | toggle pan / zoom mode                                                                     |
| o                       | toggle zoom to rectangle mode                                                              |
| left / right arrow      | iterate over list of recent views                                                          |
| c, Backspace            | switch to the previous view                                                                |
| r, h, Home              | reset view                                                                                 |
| s, Ctrl+s               | opens file chooser dialog to save plot chart as an image                                   |
| double click, f, Ctrl+f | toggle full screen mode                                                                    |
| q, Ctrl+w               | close plot window                                                                          |

Some of these hot keys are implemented by matplotlib library. Note that in panning / zooming mode the window will stop updating itself on every new data sample. Yet the data acquisition will run as usual. Saving figure as an image will pause data acquisition till saving completion, so use this feature with caution. Switching view does not terminate panning / zooming mode which may be confusing sometimes.

## Working with data histograms

The **ut61xp-get hist input_file** command creates histogram for the given input file. It either prints it to standard output or saves to the file if *-f/--out-file* option is given. The output data formatting may be customized by *-d/--delimiter* option. The *-b/--bins* option may be used to set the required number of bins in the histogram. With *-g/--graph* the histogram will be plotted in the separate window. One can plot the histogram saved to the file by  **ut61xp-get plot** command as any other data file.

## Getting help

Execute **ut61xp-get** tool with *-h* option to get detailed information about command line options. On Windows:
```
python ut61xpy/ut61xp-get -h
python ut61xpy/ut61xp-get data -h
python ut61xpy/ut61xp-get hist -h
```
On Linux the following will work either:
```
./ut61xpy/ut61xp-get -h
./ut61xpy/ut61xp-get data -h
./ut61xpy/ut61xp-get hist -h
```

## Working with several devices simultaneously

Suppose we have UT61E+ and UT61D+ devices and are going to read data from them simultaneously. We use different models just for illustrative purpose, they may be the same. We can find out path to each device by connecting them one by one and using **ut61xp-get list** command. After that we can pass the path to **ut61xp-get data** command like *ut61xp-get --path PATH data OPTIONS* but it takes a lot of typing. Using configurations may make life easier. One can do the following
1. Connect first device (UT61E+) only and issue the command:
```
python ut61xpy/ut61xp-get data -gps -f e.data -t UT61E+ --cfg-save ut61e.cfg
```
It will auto detect device, plot the data saving it to the file e.data, showing a progress and printing stats on termination. It will also create the configuration file ut61e.cfg. The *-t* option will set window title so we can tell which window shows data from which device.

2. Disconnect first device and connect other device (UT61D+) and run the command:
```
python ut61xpy/ut61xp-get data -gps -f d.data -t UT61D+ --cfg-save ut61d.cfg 
```
The corresponding configuration will be saved to ut61d.cfg

3. Now we can connect both devices and run some acquisition in parallel (in separate terminals):
```
python ut61xpy/ut61xp-get data -c ut61d.cfg
python ut61xpy/ut61xp-get data -c ut61e.cfg -a a.data
```
The first command will read data from UT61D+. The second command will acquire data from UT61E+ in DC+AC mode storing AC channel samples to a.data.

4. One can even create specialized configuration file for DC+AC mode by modifying basic configuration:
```
python ut61xpy/ut61xp-get data -c ut61e.cfg -a a.data --cfg-save acdc.cfg
```
Now one can just execute the following short command line to use DC+AC readout with dual plot graph:
```
python ut61xpy/ut61xp-get data -c acdc.cfg
```
Of cause the *./ut61xpy/ut61xp-get* invocation will work on Linux as well since *ut61xp-get* is executable script on this system.
Note that to be able to combine measurements made by different devices you will probably have to use epoch time option (*-e*). Otherwise data samples originated from different devices may be read at different time even if they have the same time stamp (since its relative to acquisition start of the particular readout session).

## Configurations and device paths

The configuration tricks shown above work just because the auto-detected device path becomes part of the configuration saved with *--cfg-save* option. One can check that by looking at the configuration file content saved as text. But what is the device path after all? It turns out that on Windows it contains some unique device identifier but on Linux it depends only on the USB port where the device is attached. So its critically important to use different ports for different devices and always use the same port for the particular device while working with configurations / device paths on Linux.

## Using Bluetooth adapter

Working with Bluetooth adapter conceptually is not different from using USB. Just add *-B/--bt* option right after *ut61xp-get* to force script to use BT adapter. Similar to USB use case the script is able to auto detect BT adapter provided that its powered on and no other adapters are in the accessible range. By means of using the *--cfg-save* option one can save the address of the adapter discovered (which plays the role of USB device path) for the subsequent reuse. One can specify BT address in the command line explicitly via *--path/--addr* option. Opening BT device by its address is significantly faster and more reliable than autodetecting it.

## Working with other supported devices

By default, the **ut61xp-get** tool expects the UT61X+ multimeter as the target device. To change this, one should use *-M/--model* option. In case device works via Bluetooth, the *-B* option must be provided with *-M/--model* option. Both options should be specified right after **ut61xp-get** in the command line. The required options for the particular model family are listed in the following table. The last column of the table shows corresponding model label used in **ut61xp-start** GUI frontend application, see [Working with GUI](#working-with-gui).

| Vendor  | Model family                                 | Command line options  | Model label in **ut61xp-start** UI |
|---------|----------------------------------------------|-----------------------|------------------------------------|
| UNI-T   | UT61B/D/E+                                   | -M UT61X+             | UT61X+ USB                         |
|         | UT61B/D/E+ with UT-D07B Bluetooth adapter    | -M UT61X+ -B          | UT61X+ BT                          |
|         | UT60BT                                       | -M UT60BT -B          | UT60BT BT                          |
| OWON    | Bluetooth multimeters                        | -M OWON -B            | OWON BT                            |
|         | Desktop multimeters with USB port            | -M SCPI-DMM           | SCPI-DMM USB                       |
|         | Programmable power supply with USB port      | -M SCPI-CV            | SCPI-CV USB                        |
| ANENG   | AN9002 Bluetooth multimeter                  | -M ANENG -B           | ANENG BT                           |
| ZOTEK/BSIDE | ZT-300AB Bluetooth multimeter            | -M ANENG -B           | ANENG BT                           |
| FNIRSI  | FNAC28 USB tester                            | -M FNAC28             | FNAC28 USB                         |
|         | FNB48P USB tester via USB connection         | -M FNB48P             | FNB48P USB                         |
|         | FNB48P USB tester via Bluetooth              | -M FNB48P -B          | FNB48P BT                          |
|         | FNB58 USB tester via USB connection          | -M FNB58              | FNB58 USB                          |
|         | FNB58 USB tester via Bluetooth               | -M FNB58 -B           | FNB58 BT                           |
|         | FNB-C2 USB tester                            | -M FNB-C2             | FNB-C2 USB                         |

# Working with GUI
The GUI workflow is built around **ut61xp-start** script that provides convenient UI for setting **ut61xp-get** options and launching data acquisition in separate processes. The single instance of **ut61xp-start** UI can launch any number of data acquisition processes working in parallel, saving data to separate files and showing collected data in their own data plot windows. The following figure illustrates using data acquisition GUI reading data from 3 multimeters simultaneously on Raspberry Pi5.

![ut61xp-start tool collecting data from 3 multimeters on RPi5](/misc/rpi.png)

## Data acquisition launcher
The **ut61xp-start** script opens window with controls providing convenient way of setting data acquisition and plotting options and launching data acquisition in separate windows as if they were opened by running **ut61xp-get** tool from command line. The launcher window consists of the following major parts:
 - the multimeter model selector
 - the data acquisition options (for ex. output file name)
 - the plot styling options (for ex. the plot title)
 - the acquisition start button

Note that there are no options that don't have default values. So one can just choose spectrometer model and press start button. Initially the model list contains only 'unbounded' models. See [Working with other supported devices](#working-with-other-supported-devices) for the complete list of the supported models. Once the tool connects to the particular multimeter by autodetecting it, the 'bounded' model with particular USB path / BT address assigned is added to the list of models. So you can easily connect to the same multimeter later by choosing the particular bounded model. The full set of configured options is saved and restored whenever you select the particular model. Pressing Start button launches data acquisition process in separate window. This window has the same set of useful hot keys as described in [Plot window hotkeys](#plot-window-hotkeys) section. The data collected is being saved to the file with the path configured in the launcher window. By default the output file is located in 'data' folder next to the **ut61xp-start** tool in subfolder with current date as the name. Its name is made by concatenation of the start time and multimeter model name. The real path to the last created data file is shown on **ut61xp-start** tool window right below the file path template. To stop data acquisition one can just close the acquisition window.

## Working with standalone executables
On Windows the *standalone/build_sfx.bat* script builds standalone executables in *standalone/dist/dmm-tools* folder. It then creates a self extracting archive *standalone/dist/dmm-tools-{VERSION}.exe* provided that you have 7-Zip installed. This archive can be extracted to any folder on the target system including the flash drive. The only requirement for the folder where the executable files will be placed is the ability to write to it. Since the application is 'portable' it tends to store all its files next to the executable. The *Program Files* folder on Windows is usually write-protected, so you should choose a different location to store executable files.

The *dmm-tools/scripts* folder contains several *.bat* files that can make setting up your windows environment easier:

| Script                 | What it does                                                               |
|------------------------|----------------------------------------------------------------------------|
| *create_links.bat*     | creates links to executables and data folder on your windows desktop       |
| *delete_links.bat*     | removes links from your windows desktop                                    |
| *associate_data.bat*   | associates output files with .data extension with data plotting executable |
| *deassociate_data.bat* | removes output files association with data plotting executable             |
| *clear_config.bat*     | drops saved configurations reverting all settings to default values        |

On Linux one can build executables by the following command
```
pyinstaller dmm-tools.spec --noconfirm
```
Note that the resulting size of these executables on Linux is drastically larger than on Windows which makes this installation method practically meaningless.

## Other UI tools
There are several other tools that are actually wrappers around **ut61xp-get** tool. They make using particular functionality easy especially on Windows as described in the following table.
| Tools           |  What it does  |
|-----------------|----------------|
| **ut61xp-plot** | Plots one or more files given as command line arguments similar to **ut61xp-get plot** command. On Windows one can drag and drop one or more files to this tool to plot them.       |
| **ut61xp-hist** | Plots histogram for the file passed as command line arguments similar to **ut61xp-get hist** command. On Windows one can drag and drop file to this tool to plot its histogram.     |
| **ut61xp-stat** | Prints statistics for the file passed as command line arguments similar to **ut61xp-get stat** command. On Windows one can drag and drop file to this tool to print its statistics. |

For convenience you can associate .dat files with **ut61xp-plot** tool. To do it right click such file, choose 'Open with', then select 'Choose another app', then click 'Choose an app from your PC' at the bottom of the list, then select **ut61xp-plot** tool in the file chooser and finally click 'Always' button. Now the **ut61xp-plot** tool will plot .dat file every time you double click it.

## Special files and folders
The **ut61xp-start** tool creates several files and directories next to executable to save data, logs and other execution artifacts. By default only data directory is visible. It contains sub-folders named by creation date with data files having time and multimeter model as parts of their names by default. The user may change the name of the output file in **ut61xp-start** window if necessary. There are several other files and folders with names started with dot. One should use *ls* with *-a* switch to see them on Linux or enable 'Show hidden and system files' option in 'System/Advanced/File Explorer' settings on Windows. They are listed in the following table.
| Path relative to executable location |  Description                                 |
|--------------------------------------|----------------------------------------------|
| data/                                | Folder for storing output data (by default)  |
| .config                              | File storing models configuration as json dictionary. One can drop it if something goes wrong. It will be recreated automatically on next **ut61xp-start** tool invocation. |
| .cfg/                                | Folder storing configuration files for recent acquisition runs with names constructed from multimeter model name and communication protocol like 'OWON_BT'. So one can invoke acquisition with the same settings from command line by executing **ut61xp-get data -c .cfg/CONFIG_NAME** |
| .logs/                               | Folder with **ut61xp-start** tool execution logs. One can examine them should something goes wrong or send to the author for analysis. |
| .internal/                           | Folder containing executable components such as a shared libraries and compiled Python code. |

# Known issues

### Unable to connect to Bluetooth multimeter after closing **ut61xp-start** application
The multimeter becomes available for reconnect after dropping of the previous connection. The problem here is that its the operating system that maintains connection. It may not drop connection if application that initiated it was terminated not gracefully, especially on Linux. So the multimeter thinks its still connected to already terminated application. The problem occurs if one close **ut61xp-start** window while some data acquisition windows are still open. In case all such windows are closed before closing **ut61xp-start** window the Bluetooth connections are terminated as expected.

### Data was not saved to the output file after closing **ut61xp-start** application
Closing **ut61xp-start** window while acquisition is still active terminates acquisition process without saving anything. Therefore, if you need the collected data, please close the acquisition plot window first.

### Aneng (ZOTEK/BSIDE) multimeter is powering off automatically after some time while data collection is running
The auto power off feature powers off device after 15 min of inactivity. The Aneng (ZOTEK/BSIDE) multimeters don't consider Bluetooth connection as 'activity'. To disable auto powering off you should press and hold the SEL button while powering on multimeter and selecting desired mode with mode dial. The SEL button should be held until you hear four beeps. The auto power off feature will be disabled until the next power on. With power off disabled the multimeter will still emit alarming beeps periodically but will not power off.

### The *Windows protected your PC* warning always appears on attempt to run self extracting distribution archive
This happens because Windows flags all unsigned executables downloaded from the web as untrusted. There are two ways to overcome it. You can click *More info* and press *Run anyway* button. Otherwise you can clean this flag in advance by right clicking the executable and checking *Unblock* on the *General tab* of the file *Properties*. The release notes contain a link to VirusTotal analysis of the self extracting archive so you can make sure its safe to run. You can even launch validation again if you wish.

### Unable to find OWON desktop multimeter or programmable power source on Linux
There are several system services used to be installed by default that may open connected device preventing its discovery by **ut61xp-get** or **ut61xp-start** tools. Try to the execute the following commands in the terminal and reconnect your device.
```
sudo apt remove brltty
sudo systemctl stop ModemManager
sudo systemctl disable ModemManager
```

### Unable to open device USB port on Linux
An attempt to access the device as plain user may fail on Linux due to restrictive permissions. To be able to access the USB serial port you either have to run the **ut61xp-get** or **ut61xp-start** tool as a root or add iself to *dialout* group:
```
sudo usermod -aG dialout $USER
```
You have to re-login or reboot to apply new group membership properly. However, this approach does not work with HID devices. They require creating a custom udev rule or running as a root.

# Appendixes

## Adding your own device
To add new device you should implement its adapter class inherited from *Device* and *BTMixin* or *USBMixin* from **device.py** (see [Base classes](#base-classes) below). Then the class type should be added to *_supported_devices* from **ut61xp-get** and that's it.
In case the device is using already supported protocol but having different USB VIP/PID or Bluetooth device name, one can try to connect to it by tweaking these parameters specifying *--VID, --PID, --name* command line options.

## Integration with your own code
Just add this project as the sub-module to your source tree and import the necessary device adapter from it. 

### Base classes
Every supported device is represented by an instance of its adapter class. There are 2 major families of such adapters - USB and Bluetooth adapters. There is also a specialized case of USB devices that uses SCPI protocol for communication. The following figure provides the simplified view of the class hierarchy.

![Base classes hierarchy](/misc/base_classes.png)

The *Device* class (from adapters/device.py) is the ancestor of all multimeter adapters regardless of the communication protocol used. It defines several methods that should be used for communicating with the target device. The *init* method initializes communication session. The *query_raw* method reads data from the device and returns them as opaque object. The get_value method extracts floating point value from the data returned by *query_raw* method. The *get_mode* method returns measurement mode and/or units description string. The source of this information may vary. Some implementation may query and store it in the *init* call. Others may extract it from the raw data returned by *query_raw* method.

The *USBMixin* and *BTMixin* classes are used as a second base class for USB and Bluetooth spectrometer adapters respectively. They provide methods for device discovery and adapter instance creation. The *list_paths* and *list_addrs* methods return list of USB device paths and Bluetooth device addresses that may be related to corresponding devices. The *open_path* and *open_addr* methods create device adapter instance given USB path or Bluetooth address respectively. The *open* method auto detects the device and creates its adapter instance provided that there is a single such device connected to USB or reachable via Bluetooth.

The *SCPIDevice* is specialized base class for multimeters and other devices using SCPI protocol for communicating with the host. It implements several methods that can be used to directly call SCPI API of the particular device. The *scpi_send* method sends SCPI command to the device, the *scpi_receive* method reads the response from the device. The *scpi_call* method just does *scpi_send* and *scpi_receive* calls and returns the response. The *scpi_query* method invokes *scpi_call* and converts the response to the floating point value. We will consider using this methods for accessing SCPI device not supported by **ut61xp-get** and **ut61xp-start** tools in the example of [working with OWON programmable electronic load](#working-with-owon-programmable-electronic-load).

### Code examples
The code examples below illustrate techniques that can be used while working with various devices.

#### Reading from OWON Bluetooth multimeter
The following code will read data from OWON Bluetooth multimeter continuously. It will discover the multimeter automatically provided that you have single one nearby.
```python
from ut61xpy.adapters.owon import OwonBtDevice

if dev := OwonBtDevice.open():
    with dev:
        dev.init()
        while dev.is_connected():
            if data := dev.query_raw():
                print(dev.get_value(data), dev.get_mode(data))
            else:
                break
```

#### Reading from Aneng Bluetooth multimeter with known address
If you know the Bluetooth device mac address, you can open it faster without scanning. It will also work if you have several multimeters. The following code will read Aaneng AN9002 or compatible ZOTEK/BSIDE ZT-300AB with particular address.
```python
from ut61xpy.adapters.aneng import AnengBtDevice

if dev := AnengBtDevice.open_addr('C4:A9:B8:3A:5B:A2'):
    with dev:
        dev.init()
        while dev.is_connected():
            if data := dev.query_raw():
                print(dev.get_value(data), dev.get_mode(data))
            else:
                break
```

#### Working with OWON desktop multimeter
While working with OWON desktop multimeter, you can not only read measured values, but also configure measuring mode and input range. The following code
will set mode to DC voltage with 5V range and then read samples continuously two times per second. Note that reading with maximum possible rate does not make
sense in such case. The OWON multimeter does not refresh returned value faster than several times per second even if the sampling rate is much higher on specs.
```python
import time
from ut61xpy.adapters.scpi import SCPIDmm

if dev := SCPIDmm.open():
    with dev:
        dev.scpi_send(b'CONF:VOLT:DC 5')
        dev.init()
        while dev.is_connected():
            if data := dev.query_raw():
                print(dev.get_value(data), dev.get_mode(data))
                time.sleep(.5)
            else:
                break
```

#### Working with OWON programmable power source
While working with OWON programmable power source, you can not only read voltage and current, but also configure the power source output.
The following code will configure OWON power source, turn on its output, wait 2 seconds, print current and voltage and switch output off.
```python
import time
from ut61xpy.adapters.scpi import SCPIPowerSource

if dev := SCPIPowerSource.open():
    with dev:
        dev.init(2)
        dev.scpi_send(b'VOLTage 10')
        dev.scpi_send(b'CURRent 1')
        dev.scpi_send(b'OUTPut 1')
        time.sleep(2)
        if data := dev.query_raw():
            print(dev.get_mode(data, dev.CURR_CHAN), ':', dev.get_value(data, dev.CURR_CHAN))
            print(dev.get_mode(data, dev.VOLT_CHAN), ':', dev.get_value(data, dev.VOLT_CHAN))
        dev.scpi_send(b'OUTPut 0')
```
Note that there are also VOLTage:LIMit and CURRent:LIMit parameters. If any of them is exceeded the OWON power source switches off its output showing warning on the screen. The error is cleared by switching output off either by OUTPut command or by button on the front panel. Therefore, if you need just current limiting, then take care to always have VOLTage:LIMit > VOLTage and CURRent:LIMit > CURRent.

#### Reading voltage and current from FNIRSI USB tester
Similarly to programmable power source, you can read voltage and current from FNIRSI USB tester with the following code:
```python
from ut61xpy.adapters.fnirsi import FNB58Usb

if dev := FNB58Usb.open():
    with dev:
        dev.init(2)
        while dev.is_connected():
            if data := dev.query_raw():
                print('%.4f%s\t%.4f%s' % (
                    dev.get_value(data, dev.VOLT_CHAN), dev.get_mode(data, dev.VOLT_CHAN),
                    dev.get_value(data, dev.CURR_CHAN), dev.get_mode(data, dev.CURR_CHAN)
                ))
            else:
                break
```
To communicate with FNB58 via Bluetooth one can just replace FNB58Usb -> FNB58Bt.

#### Reading data from several devices simultaneously
The next code example illustrates reading data from Aneng and OWON Bluetooth multimeters simultaneously.
```python
from ut61xpy.adapters.aneng import AnengBtDevice
from ut61xpy.adapters.owon  import OwonBtDevice

devs = (AnengBtDevice.open(), OwonBtDevice.open())

if all(devs):
    for d in devs:
        d.init()
    while all(d.is_connected() for d in devs):
        data = [d.query_raw() for d in devs]
        if all(data):
            print('%f %s\t| %f %s' % (
                devs[0].get_value(data[0]), devs[0].get_mode(data[0]),
                devs[1].get_value(data[1]), devs[1].get_mode(data[1])
            ))
        else:
            break

for d in devs:
    if d:
        d.close()
```

#### Working with OWON programmable electronic load
The OWON OEL series electronic loads are not directly supported by **ut61xp-get** and **ut61xp-start** tools, but you can interact with them using your own code. The following code will open connection to such device
given the port name ('COM42'). Then it will configure it in constant current mode and run test sequence linearly increasing load current and printing measured current and voltage. The code is tested with OEL1515 model.
```python
import time
from ut61xpy.adapters.scpi import SCPIDevice

CMD_DELAY  = .1
STEP_DELAY = .5
STEP  = .1
STEPS = 20

if dev := SCPIDevice.open_path('COM42'):
    with dev:
        print('connected to', dev.get_model())
        dev.scpi_send(b'SYST:REM')
        time.sleep(CMD_DELAY)
        dev.scpi_send(b'FUNC CURR')
        time.sleep(CMD_DELAY)
        dev.scpi_send(b'INP 1')
        time.sleep(CMD_DELAY)

        curr = 0
        print('Set\tCurr\tVolt')
        for i in range(STEPS+1):
            dev.scpi_send(b'CURR %f' % curr)
            time.sleep(STEP_DELAY)
            print('%.2f\t%.3f\t%.4f' % (curr, dev.scpi_query(b'MEAS:CURR?'), dev.scpi_query(b'MEAS:VOLT?')))
            curr += STEP

        dev.scpi_send(b'INP 0')
        time.sleep(CMD_DELAY)
        dev.scpi_send(b'SYST:LOC')
```

The next code example illustrates interfacing with electronic load in similar setup but with OWON desktop multimeter (XDM1041, XDM1241) measuring current between power source and electronic load. The script prints current set, current reported by electronic load and the current error with respect to the value reported by multimeter. Note that unlike other examples the code uses SCPIDevice class and its scpi_query method for interacting with multimeter instead of generic query_raw/get_value API.
```python
import time
from ut61xpy.adapters.scpi import SCPIDevice

CMD_DELAY  = .1
STEP_DELAY = 1.5
STEP  = .1
STEPS = 20

dmm = SCPIDevice.open_path('COM11')
el  = SCPIDevice.open_path('COM42')

if dmm and el:
    dmm.scpi_send(b'CONF:CURR:DC 5')

    el.scpi_send(b'SYST:REM')
    time.sleep(CMD_DELAY)
    el.scpi_send(b'FUNC CURR')
    time.sleep(CMD_DELAY)
    el.scpi_send(b'INP 1')
    time.sleep(CMD_DELAY)

    curr = 0
    print('Set\tCurr\tErr')
    for i in range(STEPS+1):
        el.scpi_send(b'CURR %f' % curr)
        time.sleep(STEP_DELAY)
        curr_el = el.scpi_query(b'MEAS:CURR?')
        curr_dmm = dmm.scpi_query(b'MEAS?')
        print('%.2f\t%.4f\t%.4f' % (curr, curr_el, curr_el - curr_dmm))
        curr += STEP

    el.scpi_send(b'INP 0')
    time.sleep(CMD_DELAY)
    el.scpi_send(b'SYST:LOC')

if dmm:
    dmm.close()
if el:
    el.close()
```
