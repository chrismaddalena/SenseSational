#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Small script to gather data using a Rasp PI and Sense HAT. Data is logged to
a CSV file with a timestamp. Logging is continuous until recording is stopped.
Then log file is moved into a "Finished" directory.

This is intended to be run automatically on Rasp Pi boot. Control the Pi
and script functions with the Sense HAT joystick. Activate recording and
attach the Pi to a drone, throw it off a cliff, whatever.

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
import sys, os, time, socket, struct, fcntl

# Setup Sense HAT
sense = SenseHat()
sense.low_light = True

# Globals
filenamePrefix = None
outputDirectory = "Finished" 
batch_data = []

# Setup output file
if filenamePrefix is None:
	filenamePrefix = "SenseLog" 

# Create directory for finished reports
if not os.path.exists("Finished"):
	try:
		os.makedirs("Finished")
	except:
		print("Failed to make Finished report directory!")

# Setup values for displays
X = [255, 0, 0]  # Red
O = [255, 255, 255]  # White
B = [0, 0, 0] # Black
Y = [0, 255, 0] # Green
Z = [255, 255, 0] # Yellow

recording = [
	O, O, O, O, O, O, O, O,
	O, O, O, O, O, O, O, O,
	O, O, X, X, X, X, O, O,
	O, O, X, X, X, X, O, O,
	O, O, X, X, X, X, O, O,
	O, O, X, X, X, X, O, O,
	O, O, O, O, O, O, O, O,
	O, O, O, O, O, O, O, O
]

logged = [
	O, O, O, O, O, O, O, O,
	O, O, O, O, O, O, O, O,
	O, O, O, O, O, O, Y, O,
	O, O, O, O, O, Y, O, O,
	Y, O, O, O, Y, O, O, O,
	O, Y, O, Y, O, O, O, O,
	O, O, Y, O, O, O, O, O,
	O, O, O, O, O, O, O, O
]

ready = [
        B, B, Z, Z, Z, Z, B, B,
	B, Z, B, B, B, B, Z, B,
	Z, B, Z, B, B, Z, B, Z,
	Z, B, B, B, B, B, B, Z,
	Z, B, Z, B, B, Z, B, Z,
	Z, B, B, Z, Z, B, B, Z,
	B, Z, B, B, B, B, Z, B,
	B, B, Z, Z, Z, Z, B, B
]

areYouSure = [
        B, X, B, B, B, X, B, B,
	B, B, X, B, X, B, B, B,
	B, B, B, X, B, B, B, B,
	B, B, B, X, B, B, B, B,
	B, B, X, B, B, X, B, B,
	B, B, X, X, B, X, B, B,
	B, B, X, B, X, X, B, B,
	B, B, X, B, B, X, B, B
]


openedFileName = None

#sense.set_pixels(ready)
#sense.load_image("space_invader.png")
sense.show_message("Ready!", back_colour=[0, 255, 0])
sense.set_pixels(ready)
time.sleep(5)
sense.clear()

# Setup for output CSV file - headers are the columns and match data collected in getSenseData()
def fileSetup(prefix):
	global openedFileName
	header = ["temp_h","temp_p","humidity","pressure","pitch","roll","yaw","mag_x","mag_y","mag_z","gyro_x","gyro_y","gyro_z","timestamp"]
	filename = "%s-%s.csv" % ( prefix, time.strftime('%Y%m%d_%H%M%S', time.localtime()))
	openedFileName = filename
	print("Opening file %s for writing." % filename)
	record = open(filename, "w")
	record.write(",".join(repr(value) for value in header) + "\n")
	# Return file descriptor
	return record

# Function to log collected data to the CSV file
def logData(fd, sensedData):
	output = ", ".join([str(value) for value in sensedData])
	#output = ", ".join([ "%.2f" % value for value in sensedData[:-1])
	fd.write("{}\n".format(output))

# Primary function to collect data from Sense HAT
def getSenseData():
	sense_data = []
	# Temperature, humidity, and air pressure
	sense_data.append(round(sense.get_temperature_from_humidity(), 2))
	sense_data.append(round(sense.get_temperature_from_pressure(), 2))
	sense_data.append(round(sense.get_humidity(), 2))
	sense_data.append(round(sense.get_pressure(), 2))

	# Orientation
	o = sense.get_orientation()
	yaw = round(o["yaw"], 2)
	pitch = round(o["pitch"], 2)
	roll = round(o["roll"], 2)
	sense_data.extend([pitch,roll,yaw])

	# Magnetometer
	mag = sense.get_compass_raw()
	mag_x = round(mag["x"], 2)
	mag_y = round(mag["y"], 2)
	mag_z = round(mag["z"], 2)
	sense_data.extend([mag_x,mag_y,mag_z])

	# Accelerometer
	acc = sense.get_accelerometer_raw()
	acc_x = round(acc["x"], 2)
	acc_y = round(acc["y"], 2)
	acc_z = round(acc["z"], 2)
	sense_data.extend([acc_x,acc_y,acc_z])

	# Gyroscope
	gyro = sense.get_gyroscope_raw()
	gyro_x = round(gyro["x"], 2)
	gyro_y = round(gyro["y"], 2)
	gyro_z = round(gyro["x"], 2)

	# Add a timestamp for data collection
	sense_data.append(datetime.datetime.now())
	return sense_data

def getIPAddress(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', bytes(ifname[:15], 'utf-8')))[20:24])

outputFD = None
recordingState = False

print("File opened, waiting for stick input.")

try:
	while True:
		# Wait for an event from the Sense HAT's joystick
		if sense.stick._wait(2):
			# Enumerate the events from the past 2 seconds
			for event in sense.stick.get_events():
				# LEFT begins recording
				if event.direction == "left" and event.action == "pressed":
					if not recordingState:
						outputFD = fileSetup(filenamePrefix)
						print("Switching to recording due to joystick input." )
						sense.set_pixels(recording)
					recordingState = True
				# RIGHT sets recordingState to False and finalizes logging
				elif event.direction == "right" and event.action == "pressed":
					if recordingState:
						outputFD.close()
						os.rename(openedFileName, "{}/{}".format(outputDirectory, openedFileName))
						print("Finishing recording due to right input.")
						sense.set_pixels(logged)
						time.sleep(2)
						sense.clear()
					recordingState = False
				# MIDDLE displays the Pi's IP address on the provided iface
				elif event.direction == "middle" and event.action == "pressed":
					ipAdd = getIPAddress('wlan0')	
					sense.show_message("IP: {}".format(ipAdd))
				# UP toggle low light mode
				elif event.direction == "up" and event.action == "pressed":
					# Display a reference image
					sense.load_image("space_invader.png")
					if sense.low_light:
						print("Toggling to High brightness!")
						sense.low_light = False
					else:
						print("Toggling to Low birghtness!")
						sense.low_light = True
				# DOWN will run shutdown
				elif event.direction == "down" and event.action == "held":
					sense.set_pixels(areYouSure)
					time.sleep(2)
					userInput = sense.stick.wait_for_event()
					if userInput.direction == "up" and userInput.action == "pressed":
						sense.show_message("Shutting down", back_colour=[255, 0, 0])
						print("Will shutdown")
						if recordingState:
							outputFD.close()
							os.rename(openedFileName, "{}/{}".format(outputDirectory, openedFileName))
							print("Finishing recording due to shutdown.")
							sense.set_pixels(logged)
							time.sleep(2)
							recordingState = False
							os.system("sudo shutdown -h now")
						else:
							print("No logs to write, shutdown commencing...")
							os.system("sudo shutdown -h now")
					if userInput.direction == "down" and userInput.action == "pressed":
						sense.set_pixels(ready)
						time.sleep(2)
						sense.clear()
						print("Shutdown aborted!")
						break
				# Handle any other unexpected input, like "released" events
				else:
					print("Unused or unrecognized event input: {}".format(event))
		
		# While recordingState is True, keep logging data
		if recordingState:
			print("Saving data at time {}.\n".format(time.ctime(time.time()))) 
			sensedData = getSenseData()
			logData(outputFD, sensedData)

# No matter what happens to end script, clear the LEDs
finally:
	sense.clear()

