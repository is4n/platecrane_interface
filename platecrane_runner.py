import os
import sys
import traceback
from functools import partial
from io import StringIO

from tkinter import *
from tkinter.messagebox import showerror, askquestion
from tkinter.filedialog import asksaveasfilename

def updateProgramsList(uiProgramsList):
    oldIndex = uiProgramsList.curselection
    uiProgramsList.delete(0, END)
    
    for program in os.listdir("programs"):
        uiProgramsList.insert(END, program.replace(".py", ""))
    
    uiProgramsList.curselection = oldIndex

def updateCurrentProgramSelection(uiProgramsList, uiCurrProgram, e):
    uiCurrProgram.set(uiProgramsList.get(uiProgramsList.curselection()))


def getProgramName(uiProgName):
    return os.path.join(os.path.dirname(__file__), "programs", uiProgName.get() + ".py")

def createClick(uiProgramsList, uiProgName, parent):
    programName = getProgramName(uiProgName)
    
    if not os.path.exists(programName):
        with open(programName, "w") as newProgramFile:
            newProgramFile.write("# put your program here")
    
    updateProgramsList(uiProgramsList)
    parent.destroy()

def drawProgramCreator(uiProgramsList):
    createUi = Toplevel()
    createUi.attributes('-topmost', 'true')
    frame = Frame(createUi)
    frame.pack()
    
    uiProgramTitle = StringVar()
    
    Label(
        createUi,
        text = "Program name:"
    ).pack()
    
    Entry(
        createUi,
        textvariable = uiProgramTitle
    ).pack()
    
    Button(
        createUi,
        text = "Create",
        command = partial(
            createClick,
            uiProgramsList,
            uiProgramTitle,
            createUi
        )
    ).pack(side=RIGHT)


def openClicked(uiProgramName):
    programName = getProgramName(uiProgramName)
    
    if os.path.exists(programName):
        os.system(f'xdg-open "{programName}"')

def deleteClicked(uiProgramsList, uiProgramName):
    programName = getProgramName(uiProgramName)
    
    response = askquestion(
        title = "Confirm", 
        message = f"Delete {uiProgramName.get()}?"
    )
    
    if (response == 'yes'):
        os.remove(programName)
    
    updateProgramsList(uiProgramsList)

def exportClicked(uiProgramName):
    programName = getProgramName(uiProgramName)
    
    with open("config/interfacecode.py") as ifcFile:
        interfaceCode = ifcFile.read()
        
        newProgramName = asksaveasfilename()
        if newProgramName:
            programText = ""
            
            with open(programName) as opFile:
                programText = opFile.read()
        
            with open(newProgramName, 'w') as npFile:
                npFile.write(interfaceCode + "\n" + programText)
        

# removes the reference to this file from the error message
def handleRunErr(ex, uiErrors):
    with StringIO() as exMsgFile:
        traceback.print_exc(file=exMsgFile)
        exMsg = exMsgFile.getvalue()[205:].replace(", in <module>\n", ": ")
        uiErrors.set(exMsg)

def runClicked(uiProgramName, uiErrors, robot):
    uiErrors.set("")

    programName = getProgramName(uiProgramName)
    
    if os.path.exists(programName):
        with open(programName) as programFile:
            try:
                exec(programFile.read(), globals(), {"robot": robot})
            except Exception as ex:
                handleRunErr(ex, uiErrors)
    else:
        showerror(
            title = "Program Linker",
            message = "That program doesn't exist!"
        )

def drawPlatecraneRunner(root, robot):
    runnerUi = Toplevel()
    runnerUi.attributes('-topmost', 'true')
    frame = Frame(runnerUi)
    frame.pack()
    
    uiProgramName = StringVar()
    uiErrors = StringVar()
    
    programsPanel = Frame(frame)
    programsPanel.pack()
    
    programsScroll = Scrollbar(programsPanel)
    programsScroll.pack(side=RIGHT, fill=BOTH)
    programsList = Listbox(
        programsPanel,
        yscrollcommand = programsScroll.set,
        width = "27"
    )
    programsList.pack(side=LEFT, fill=BOTH)
    programsList.bind('<<ListboxSelect>>', partial(
        updateCurrentProgramSelection,
        programsList,
        uiProgramName
    ))
    programsScroll.config(command=programsList.yview)
    
    programBtnsPanelTop = Frame(frame)
    programBtnsPanelTop.pack()
    
    Button(
        programBtnsPanelTop,
        text = "Delete",
        command = partial(
            deleteClicked,
            programsList,
            uiProgramName
        )
    ).pack(side=LEFT)
    
    Button(
        programBtnsPanelTop,
        text = "New",
        command = partial(
            drawProgramCreator,
            programsList
        )
    ).pack(side=LEFT)
    
    Button(
        programBtnsPanelTop,
        text = "Export",
        command = partial(
            exportClicked,
            uiProgramName
        )
    ).pack(side=LEFT)
    
    programBtnsPanelBottom = Frame(frame)
    programBtnsPanelBottom.pack()
    
    Button(
        programBtnsPanelBottom,
        text = "Edit",
        command = partial(
            openClicked,
            uiProgramName
        )
    ).pack(side=LEFT)
    
    Button(
        programBtnsPanelBottom,
        text = "Run",
        command = partial(
            runClicked,
            uiProgramName,
            uiErrors,
            robot
        )
    ).pack(side=LEFT)
    
    Label(
        frame,
        textvariable = uiErrors,
        wraplength = 250
    ).pack(side=BOTTOM)
    
    updateProgramsList(programsList)
