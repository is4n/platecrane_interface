# Hudson PlateCrane Python interface

![Alt text](/screenshot_new.png?raw=true)

A virtual teach pendant and programming interface for the Hudson PlateCrane robot arm. To do list:

☑ Robot connection

☑ Jogging

☑ Position readout

☑ Record and GoTo points

☑ Delete points

☑ Gripper open/close

☐ Input readout

☑ Seek function - this is handled by the robot itself

# Use

Prerequisites:
 - pyserial
 - tkinter

Tested on Ubuntu 20.04.

NOTE: My PlateCrane has an issue where some of the motor drivers do not have the correct configuration on startup. As a workaround, the PlateCrane class can enter TERMINAL mode and send driver parameters on startup automatically (set sendDriverParams to True). The parameter setting commands are in config/driver.params, one per line.

To teach: run platecrane_interface.py, jog the robot to the points you want to teach, hit Record to save them.

To program: TODO
