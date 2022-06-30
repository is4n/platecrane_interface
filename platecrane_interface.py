import time
import threading
from functools import partial

from tkinter import *
from tkinter.messagebox import showerror

from platecrane_comms import PlateCrane

APPNAME = 'PlateCrane interface'

def uiValToInt(uiVal):
    valStr = uiVal.get()
    try:
        return int(valStr)
    except:
        return None

def entryWithVar(parent, label, var):
    Label(parent, text = label).pack(anchor=W)
    Entry(parent, textvariable = var).pack(anchor=W)

def onJogClicked(uiJogDist, uiJogSpeed, robot, dirMul, axis):
    jogDist = uiValToInt(uiJogDist)
    jogSpeed = uiValToInt(uiJogSpeed)
    
    robot.speed(jogSpeed)
    robot.jog(axis, jogDist * dirMul)

def drawJogger(parent, uiJogDist, uiJogSpeed, robot, axis):
    jogPanel = Frame(parent)
    jogPanel.pack()
    
    Button(
        jogPanel,
        text = axis + "-",
        command = partial(
            onJogClicked,
            uiJogDist,
            uiJogSpeed,
            robot,
            -1,
            axis
        )
    ).pack(side='left')
    Button(
        jogPanel,
        text = axis + "+",
        command = partial(
            onJogClicked,
            uiJogDist,
            uiJogSpeed,
            robot,
            1,
            axis
        )
    ).pack(side='left')

def updatePosition(uiPosReadout, uiInputsReadout, robot):
    while True:
        uiPosReadout.set(robot.getPosition())
        uiInputsReadout.set(robot.getInputs())
        time.sleep(0.1)

def appExit(robot):
    robot.close()
    exit()

def onRecordClicked(robot, uiCurrPoint, uiPointsList):
    robot.here(uiCurrPoint.get())
    updatePointsList(robot, uiPointsList)

def onDeleteClicked(robot, uiCurrPoint, uiPointsList):
    robot.clear(uiCurrPoint.get())
    updatePointsList(robot, uiPointsList)

def gotoClicked(robot, uiCurrPoint, uiPointsList):
    robot.move(uiCurrPoint.get())
    updatePointsList(robot, uiPointsList)

def updatePointsList(robot, uiPointsList):
    oldIndex = uiPointsList.curselection
    uiPointsList.delete(0, END)
    
    for point in robot.getPoints():
        uiPointsList.insert(END, point)
    
    uiPointsList.curselection = oldIndex

def onResetClicked(robot, uiPointsList):
    try:
        robot.reset()
    except Exception as e:
        showerror(
            title = APPNAME,
            message = str(e)
        )
    
    updatePointsList(robot, uiPointsList)

def updateCurrentPointSelection(uiPointsList, uiCurrPoint, e):
    uiCurrPoint.set(uiPointsList.get(uiPointsList.curselection())[2:])

def drawMainUi(root, robot):
    mainUi = Toplevel(root)
    mainUi.protocol("WM_DELETE_WINDOW", partial(appExit, robot))
    
    frame = Frame(mainUi)
    frame.pack()
    
    uiPosReadout = StringVar()
    uiInputsReadout = StringVar()
    uiJogDist = StringVar()
    uiJogDist.set('100')
    uiJogSpeed = StringVar()
    uiJogSpeed.set('100')
    
    statPanel = Frame(frame)
    statPanel.pack()
    
    # the resetBtn event handler is added later because it must
    # access another control defined further down
    resetBtn = Button(
        statPanel,
        text = "Reset and Home",
    )
    resetBtn.pack()
    Label(
        statPanel,
        textvariable = uiPosReadout
    ).pack()
    Label(
        statPanel,
        textvariable = uiInputsReadout
    ).pack()
    
    jogPanel = Frame(frame)
    jogPanel.pack()
    entryWithVar(
        jogPanel,
        'Jog speed',
        uiJogSpeed
    )
    entryWithVar(
        jogPanel,
        'Jog distance',
        uiJogDist
    )
    for axis in robot.axes:
        drawJogger(
            jogPanel,
            uiJogDist,
            uiJogSpeed,
            robot,
            axis
        )
    
    uiCurrPoint = StringVar()
    
    pointsPanel = Frame(frame)
    pointsPanel.pack()
    
    pointsScroll = Scrollbar(pointsPanel)
    pointsScroll.pack(side=RIGHT, fill=BOTH)
    pointsList = Listbox(
        pointsPanel,
        yscrollcommand = pointsScroll.set
    )
    pointsList.pack(side=LEFT, fill=BOTH)
    pointsList.bind('<<ListboxSelect>>', partial(
        updateCurrentPointSelection,
        pointsList,
        uiCurrPoint
    ))
    pointsScroll.config(command=pointsList.yview)
    
    currPointPanel = Frame(frame)
    currPointPanel.pack()
    entryWithVar(
        currPointPanel,
        'Point to edit',
        uiCurrPoint
    )
    Button(
        currPointPanel,
        text = 'GoTo',
        command = partial(
            gotoClicked,
            robot,
            uiCurrPoint,
            pointsList
        )
    ).pack()
    Button(
        currPointPanel,
        text = 'Record',
        command = partial(
            onRecordClicked,
            robot,
            uiCurrPoint,
            pointsList
        )
    ).pack(side=LEFT)
    Button(
        currPointPanel,
        text = 'Delete',
        command = partial(
            onDeleteClicked,
            robot,
            uiCurrPoint,
            pointsList
        )
    ).pack(side=RIGHT)
    
    resetBtn.config(
        command = partial(
            onResetClicked,
            robot,
            pointsList
        )
    )
    
    threading.Thread(
        target = updatePosition,
        args = (uiPosReadout, uiInputsReadout, robot),
        daemon = True
    ).start()

def onConnectClicked(root, parentWindow, uiDevName):
    devName = uiDevName.get()
    
    with open('config/last.device', 'w') as ldevFile:
        ldevFile.write(devName)
    
    if not devName:
        showerror(
            title = APPNAME,
            message = 'no port given'
        )
    
    try:
        robot = PlateCrane(port=devName, sendDriverParams=True)
    except Exception as e:
        showerror(
            title = APPNAME,
            message = str(e)
        )
        return
    
    parentWindow.destroy()
    drawMainUi(root, robot)

def drawConnectUi(root):
    connectUi = Toplevel(root)
    connectUi.protocol("WM_DELETE_WINDOW", exit)
    connectFrame = Frame(connectUi, padx=14, pady=14)
    connectFrame.pack()
    
    uiDevName = StringVar()
    
    try:
        with open('config/last.device', 'r') as ldevFile:
            uiDevName.set(ldevFile.read().strip('\n'))
    except FileNotFoundError:
        pass
    
    Label(
        connectFrame,
        text = "Connect to PlateCrane"
    ).pack()
    entryWithVar(
        connectFrame,
        'serial port',
        uiDevName
    )
    Button(
        connectFrame,
        text = "Connect",
        command=partial(
            onConnectClicked,
            root,
            connectUi,
            uiDevName
        )
    ).pack()

def main():
    root = Tk()
    root.withdraw()
    drawConnectUi(root)
    root.mainloop()


if __name__ == '__main__':
    main()
