####PLATECRANE_INTERFACE CODE BEGIN####
# To run this program without using platecrane_interface:
# - Copy platecrane_comms.py to the same directory as this file.
# - Set the configuration below to your needs (NOTE: config only applies when
#       running standalone)
# - Invoke as a normal python3 script.

# Serial port to connect to the robot on:
plateCraneSerialPort = "/dev/ttyUSB0"

# Set to True to enable sending driver parameters on robot startup. For this
# to work, you must have the file 'config/driver.params' present relative to
# the working directory of this script.
sendDriverParams = False

# Do not edit the next lines:
from platecrane_comms import PlateCrane
if __name__ == "__main__":
    robot = plateCrane(port=plateCraneSerialPort, sendDriverParams=sendDriverParams)
    robot.reset()
####PLATECRANE_INTERFACE CODE END####
