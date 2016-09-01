#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright 2016, Chris Maddalena <cmaddy@chrismaddalena.com> 

Small script to gather data using a Rasp PI and Sense HAT. Data is logged to
a CSV file with a timestamp. Logging is continuous until recording is stopped.
Then the log file is moved into a "Finished" directory.

This is intended to be run to be automatically when the Rasp Pi boots.
You control the Pi and script functions with the Sense HAT joystick.
Activate recording and attach the Pi to a drone, throw it off a cliff, whatever.

Joystick Functions:

UP: Toggle low lght mode for LED matrix
DOWN: Shutdown the Pi
MIDDLE: Display Pi's IP address on LED matrix

LEFT: Begin data recording
RIGHT: Stop recording and finalize log file

https://pythonhosted.org/sense-hat/api/
"""

from sense_hat import SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED
import datetime
from logbook import Logger, FileHandler
import sys, os, time, socket, struct, fcntl

# Setup Sense HAT and logger
sense = SenseHat()
sense.low_light = True
log = Logger('Sense Logger')
logHandler = FileHandler('SenseSational Logs')

# Globals
filenamePrefix = None
outputDirectory = "Finished"
batch_data = []
outputFD = None
currentFileName = None

# Setup color values for display
R = [255, 0, 0]  # Red
W = [255, 255, 255]  # White
B = [0, 0, 0] # Black
G = [0, 255, 0] # Green
Y = [255, 255, 0] # Yellow

recording = [
	W, W, W, W, W, W, W, W,
	W, W, W, W, W, W, W, W,
	W, W, R, R, R, R, W, W,
	W, W, R, R, R, R, W, W,
	W, W, R, R, R, R, W, W,
	W, W, R, R, R, R, W, W,
	W, W, W, W, W, W, W, W,
	W, W, W, W, W, W, W, W
]

logged = [
	W, W, W, W, W, W, W, W,
	W, W, W, W, W, W, W, G,
	W, W, W, W, W, W, G, W,
	W, W, W, W, W, G, W, W,
	G, W, W, W, G, W, W, W,
	W, G, W, G, W, W, W, W,
	W, W, G, W, W, W, W, W,
	W, W, W, W, W, W, W, W
]

ready = [
	B, B, Y, Y, Y, Y, B, B,
	B, Y, B, B, B, B, Y, B,
	Y, B, Y, B, B, Y, B, Y,
	Y, B, B, B, B, B, B, Y,
	Y, B, Y, B, B, Y, B, Y,
	Y, B, B, Y, Y, B, B, Y,
	B, Y, B, B, B, B, Y, B,
	B, B, Y, Y, Y, Y, B, B
]

areYouSure = [
	B, R, B, B, B, R, B, B,
	B, B, R, B, R, B, B, B,
	B, B, B, R, B, B, B, B,
	B, B, B, R, B, B, B, B,
	B, B, R, B, B, R, B, B,
	B, B, R, R, B, R, B, B,
	B, B, R, B, R, R, B, B,
	B, B, R, B, B, R, B, B
]

# Setup output file
if filenamePrefix is None:
	filenamePrefix = "SenseLog"

# Create directory for finished reports if it doesn't otherwise exist
if not os.path.exists(outputDirectory):
	try:
		os.makedirs(outputDirectory)
		log.info("Successfully created the Finished directory for CSV files.")
	except:
		log.critical("Failed to create Finished directory for final CSV files!")
        sys.exit(-1)
elif not os.path.isdir(outputDirectory):
    log.critical("outputDirectory '{}' exists but is not a directory.".format(outputDirectory))
    sys.exit(-1)
    

"""
Beginning of function definitons
"""

# Setup for output CSV file - headers are the columns and match data collected in getSenseData()
def fileSetup(outputFileName):
	header = [ "temp_h", "temp_p", "humidity", "pressure", "pitch", "roll", "yaw", "mag_x", "mag_y", "mag_z", "gyro_x", "gyro_y", "gyro_z", "timestamp"]
	log.info("Opening file {} for writing.".format(outputFileName))
	outputFile = open(outputFileName, "w")
	log.info("Recording file, {}, opened. Writing column headers.".format(record))
	outputFile.write("{}\n".format(", ".join(repr(value) for value in header)))
    
	# Return the file descriptor
	return outputFile

# Function to log collected data to the CSV file
def logData(fd, sensedData):
	output = ", ".join([str(value) for value in sensedData])
	fd.write("{}\n".format(output))

# Primary function to collect data from Sense HAT
def getSenseData():
	sense_data = []

	# Temperature, humidity, and air pressure
	sense_data.append(sense.get_temperature_from_humidity())
	sense_data.append(sense.get_temperature_from_pressure())
	sense_data.append(sense.get_humidity())
	sense_data.append(sense.get_pressure())

	# Orientation
	o = sense.get_orientation()
	sense_data.extend([o["pitch"],o["roll"],o["yaw"]])

	# Magnetometer
	mag = sense.get_compass_raw()
	sense_data.extend([mag[x],mag[y],mag[z]])

	# Accelerometer
	acc = sense.get_accelerometer_raw()
	sense_data.extend([acc[x],acc[y],acc[z]])

	# Gyroscope
	gyro = sense.get_gyroscope_raw()
    sense_data.extend([gyro[x], gyro[y], gyro[z]]) 

	# Add a timestamp for data collection
	sense_data.append(datetime.datetime.now())

	return sense_data

# Get the IPv4 address of the specified interface
def getIPAddress(ifname):
	log.info("Retrieving IPv4 address of interface '{}'.".format(ifname))

    # Open a socket of type DGRAM to request SIOCGIFADDR for the supplied ifname
    #
    # Expect Exception OSError with errno 19 (-ENODEV) if the indicated ifname does not exist or
    # OSError with errno 99 (-EADDRNOTAVAIL) if the indicated ifname does not have an
    # IPv4 address assigned.
    # 
    # Constant 0x8915 is SIOCGIFADDR.
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', bytes(ifname[:15], 'utf-8')))[20:24])

currentFileName = None

def main():
	recordingState = False
	try:
		while True:
			# Wait for an event from the Sense HAT's joystick
			if sense.stick._wait(2):
				# Enumerate the events from the past 2 seconds
				for event in sense.stick.get_events():
                    if event.action == "pressed":
                        # LEFT begins recording
                        if event.direction == "left":
                            if not recordingState:
                                currentFileName = "{}-{}.csv".format(prefix, time.strftime('%Y%m%d_%H%M%S', time.localtime()))
                                outputFD = fileSetup(currentFileName)
                                log.info("Switching to recording due to joystick LEFT input." )
                                sense.set_pixels(recording)
                            recordingState = True
                        # RIGHT sets recordingState to False and finalizes logging
                        elif event.direction == "right":
                            if recordingState:
                                outputFD.close()
                                os.rename(currentFileName, os.path.join(outputDirectory, currentFileName))
                                log.info("Finishing recording due to right RIGHT input.")
                                sense.set_pixels(logged)
                                time.sleep(2)
                                sense.set_pixels(ready)
                            recordingState = False
                        # MIDDLE displays the Pi's IP address on the provided iface
                        elif event.direction == "middle":
                            try:
                                ipAdd = getIPAddress('wlan0')
                                sense.show_message("IP: {}".format(ipAdd))
                            except OSError as e:
                                log.warn("Failed to retrive address for adapter wlan0 with OSError '{}'".format(e))
                                sense.show_message("IP: none or error")
                        # UP toggle low light mode
                        elif event.direction == "up":
                            # Display a reference image
                            sense.load_image("space_invader.png")
                            if sense.low_light:
                                log.info("Toggling to High brightness due to joystick UP input.")
                                sense.low_light = False
                            else:
                                log.info("Toggling to Low brightness due to joystick UP input.")
                                sense.low_light = True
					# DOWN will run shutdown
					elif event.direction == "down" and event.action == "held":
						log.warn("Shutdown command, holding DOWN joystick, was used!")
						sense.set_pixels(areYouSure)
						time.sleep(2)
						userInput = sense.stick.wait_for_event()
						if userInput.direction == "up" and (userInput.action == "pressed" or userInput.action == "held"):
							sense.show_message("SHUTDOWN", back_colour=[255, 0, 0])
							if recordingState:
								outputFD.close()
								os.rename(currentFileName, os.path.join(outputDirectory, currentFileName))
								recordingState = False
								log.warn("Finished active recording due to shutdown command.")
								sense.set_pixels(logged)
								time.sleep(2)
                            log.warn("User confirmed shutdown command - shutting down!")
                            os.system("sudo shutdown -h now")
						if userInput.direction == "down" and userInput.action == "pressed":
							sense.set_pixels(ready)
							time.sleep(2)
							sense.clear()
							log.info("Shutdown command was aborted due to user selecting N.")
							break
					# Handle any other unexpected input, like "released" events
					else:
						# This will trigger for every joystick "released" event, so it's noisy.
						#log.debug("Unused or unrecognized event input: {}".format(event))

			# While recordingState is True, keep logging data
			if recordingState:
				log.info("Saving data at time {}.".format(time.ctime(time.time())))
				logData(outputFD, getSenseData())

	# No matter what happens to end script, clear the LEDs
	finally:
		sense.clear()

"""
End of function defintions.
Begin execution.
"""

if __name__ == "__main__":
	# Display message/image to let user know script is ready to go
	#sense.load_image("space_invader.png")
	sense.show_message("Go!", back_colour=[0, 255, 0])
	sense.set_pixels(ready)
	time.sleep(2)
	sense.clear()
	with logHandler.applicationbound():
		main()
