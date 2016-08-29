# SenseSational
Python script for managing and recording data with a Raspberry PI Sense HAT

![Sense HAT](https://dl.dropboxusercontent.com/u/6886662/SenseHATPi.jpg)

This script gathers data using a Raspberry Pi and a Sense HAT. Data is logged to a CSV file with a timestamp. Logging is continuous until recording is stopped. Then the log file is moved into a "Finished" directory.

This is intended to be run automatically when the Raspberry Pi boots. Control the Pi and script functions with the Sense HAT joystick. Activate recording and attach the Pi to a drone, throw it off a cliff, whatever.

## Joystick Functions:

* UP: Toggle low light mode for LED matrix
* DOWN: Shutdown the Pi
* MIDDLE: Display Pi's IP address on LED matrix
* LEFT: Begin data recording
* RIGHT: Stop recording and finalize log file

## Hardware and API Info
https://pythonhosted.org/sense-hat/api/
