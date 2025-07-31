# This is a simple PlateCrane motion program. it loops between points
# 1, 2 and 3 a few times.
#
# Be sure to press "Reset and Home" before proceeding. (The robot will move!)
#
# To teach, Use the PlateCrane Interface's jogging buttons to move the robot,
# enter "A" in "Point to edit", and press "Record" to save the point. Repeat 
# for points "B" and "C".
#
# To run, click "Program link", select the program Demo, and click "Run".
#
# WARNING: The interface doesn't yet provide a quick way to stop the program.
# be prepared to kill power to the robot in case it does something unexpected!

for i in range(0, 3):
    robot.move("A")
    robot.move("B")
    robot.move("C")
    robot.move("B")

# test the robot's gripper!
robot.grip()
robot.release()
