import serial
import os
import re
import threading
import time
import logging

NUM_IO = 48
CMD_TERM = b'00\x10\r\n'


class DummySerialDevice:
    def __init__(self, port, baudrate, timeout=0):
        self.last_command = b""
    
    def write(self, data):
        print(f"(DummySerialDevice) robot received: {data}")
        self.last_command = data
    
    def flush(self):
        print("(DummySerialDevice) (flush)")
        pass
    
    def readline(self):
        time.sleep(0.04)
        echo = self.last_command
        if (echo == b'LISTPOINTS\r\n'):
            self.last_command = b"dummy, 0, 0, 0, 0\r\n"
        elif (echo == b"dummy, 0, 0, 0, 0\r\n"):
            self.last_command = b"\r\n"
        elif (echo == b'GETPOS\r\n'):
            self.last_command = b'1, 3, 5, 7\r\n'
        elif len(echo):
            self.last_command = CMD_TERM
        else:
            self.last_command = b''
        print(f"(DummySerialDevice) robot wrote: {echo}")
        return echo
    
    def readall(self):
        time.sleep(0.01)
        self.last_command = ""
        return ""
    
    def close(self):
        self.last_command = ""

class PlateCrane:
    areMotorsOff = False
    axes = ['R', 'Y', 'Z', 'P']
    
    command = None
    expectedResponse = CMD_TERM # set to * to save response to receivedResponse
    receivedResponse = None
    ignoreEcho = False # for the special case of exiting TERMINAL mode
    cmdLock = threading.Lock()
    error = None
    
    pointStrs = {}
    pointsRead = False
    pointsLock = threading.Lock()
    
    posnStr = b'0, 0, 0, 0\r\n'
    posnLock = threading.Lock()
    
    ioStrs = {}
    ioLock = threading.Lock()
    
    fastIoNum = -1
    
    _workerThread = None
    
    def _writeWithEcho(self, data):
        self._s.write(data)
        self._s.flush()
        if self.ignoreEcho:
            return
        echo = self._s.readline()
        if (echo != data):
            raise ValueError(f'robot communication error: got {str(echo)}')
    
    
    def _readPoints(self):
        self._writeWithEcho(b'LISTPOINTS\r\n')
        hasInvalidPoints = False
        
        while True:
            resp = self._s.readline()
            
            if not resp:
                raise ValueError('robot timeout when reading points')
            if (resp == b'\r\n'):
                break
            try:
                name, values = str(resp[:-2])[2:-1].split(',', 1)
            except ValueError:
                hasInvalidPoints = True
                continue
            # if the controller is powered on without a CMOS battery,
            # the points will contain random ASCII data which can
            # break the name/values parsing. If values is malformed,
            # skip and move to the next line.
            if not re.match(r' [-\d]+, [-\d]+, [-\d]+, [-\d]+', values):
                hasInvalidPoints = True
                continue
            self.pointStrs[name] = values
        
        # if bad data was returned from LISTPOINTS, clear points list
        if hasInvalidPoints:
            print('Invalid points found in points list, clearing')
            self._s.write(b'CLEARPOINTS\r\n')
            self.pointStrs = {}
            self._s.readall()
        
        self.pointsRead = True
    
    def _readPosn(self):
        self._writeWithEcho(b'GETPOS\r\n')
        self.posnStr = self._s.readline()
    
    def _sendCmdIfAny(self):
        if self.command:
            self.error = None
            self._writeWithEcho(self.command)
            
            if (self.expectedResponse):
                resp = None
                while not resp:
                    try:
                        resp = self._s.readline()
                    except serial.timeout:
                        pass
                
                if (self.expectedResponse == '*'):
                    self.receivedResponse = resp
                elif (resp != self.expectedResponse):
                    msg = f'{self.command}: unexpected robot response: '
                    msg += str(resp)
                    msg += f'\n(expected {self.expectedResponse})'
                    self.error = msg

            self.command = None
    
    def _readIO(self, ioToRead):
        inpStr = bytes(str(ioToRead), 'UTF-8')
        self._writeWithEcho(b'READINP ' + inpStr + b'\r\n')
        self.ioStrs[ioToRead] = self._s.readline()
    
    
    def _serialWorker(self):
        currIoRead = 0
        
        while True:
            if self.pointsLock.acquire(blocking=False):
                self._readPoints()
                self.pointsLock.release()
                
            if self.posnLock.acquire(blocking=False):
                self._readPosn()
                self.posnLock.release()
            
            if self.cmdLock.acquire(blocking=False):
                self._sendCmdIfAny()
                self.cmdLock.release()
            
            if self.ioLock.acquire(blocking=False):
                # we scan one input at a time to reduce loop time.
                # setting fastIoNum >= 0 will cause that input to read every loop
                # (and ignore all the others), used when seeking.
                if (self.fastIoNum >= 0):
                    self._readIO(self.fastIoNum)
                else:
                    self._readIO(currIoRead)
                    if (currIoRead >= NUM_IO):
                        currIoRead = 0
                    else:
                        currIoRead += 1
                
                self.ioLock.release()
    
    def _addCmd(self, cmd, block=True):
        logging.info(f'sending "{cmd}"')
        self.cmdLock.acquire()
        self.command = cmd + b'\r\n'
        self.cmdLock.release()
        
        if block:
            while self.command:
                time.sleep(0.05)
        
        if self.error:
            raise ValueError(self.error)
    
    
    def __init__(self, port='/dev/ttyUSB0', config='config/', sendDriverParams=False):
        # pointsLock is normally locked
        self.pointsLock.acquire()
        
        self.fastIoNum = 22
        self.sendDriverParams = sendDriverParams
        
        # enable debugging with dummy device
        if (port == ""):
            self._s = DummySerialDevice(port, 9600, timeout=0.25)
        else:
            self._s = serial.Serial(port, 9600, timeout=0.25)
        
        self._configPath = config
    
    # the Y- and P-axis drivers lose their params on startup, so
    # we re-send them here
    def driverInit(self):
        self._s.write(b'TERMINAL\r\n')
        print(self._s.readall())
        
        with open(os.path.join(self._configPath, 'driver.params'), 'r') as dpFile:
            driverConfig = dpFile.read().split('\n')
            
            for line in driverConfig:
                if line:
                    self._s.write(bytes(line, 'UTF-8') + b'\r\n')
                    print(self._s.readall())
        
        self._s.write(b'TERMINAL\r\n')
        print(self._s.readall())
    
    # system params to send on startup
    def systemInit(self):
        print(self._s.readall())
        
        with open(os.path.join(self._configPath, 'system.params'), 'r') as spFile:
            systemConfig = spFile.read().split('\n')
            
            for line in systemConfig:
                if line:
                    self._s.write(bytes(line, 'UTF-8') + b'\r\n')
                    print(self._s.readall())
    
    def reset(self):
        self.systemInit()
        if self.sendDriverParams:
            self.driverInit()
        
        if not self._workerThread or not self._workerThread.is_alive():
            self._workerThread = threading.Thread(
                target=self._serialWorker,
                daemon=True
            )
            self._workerThread.start()
        
        self._addCmd(b'HOME')
    
    def getPosition(self):
        return str(self.posnStr[:-2]).strip("'b")
    
    #TODO: getInput(input) to replace getInputs()?
    def getInputs(self):
        return str(self.ioStrs) \
            .strip("{}") \
            .replace(",", " ") \
            .replace("\\r\\n", "") \
            .replace("b", "") \
            .replace("'", "")
    
    def motorsOff(self):
        self.areMotorsOff = True
        self.posnLock.acquire()
        self.ioLock.acquire()
        self._addCmd(b'LIMP 0')
    
    def motorsOn(self):
        self._addCmd(b'LIMP 1')
        if self.areMotorsOff:
            self.posnLock.release()
            self.ioLock.release()
            self.areMotorsOff = False
    
    def speed(self, speed):
        if (speed < 0 or speed > 100):
            raise ValueError('speed must be 0-100')
        self._addCmd(b'SPEED ' + bytes(str(speed), 'UTF-8'))
    
    def jog(self, axis, dist):
        if axis not in self.axes:
            raise ValueError('invalid axis')
        self._addCmd(b'JOG ' + bytes(axis, 'UTF-8') + b','
            + bytes(str(dist), 'UTF-8'))
    
    def here(self, pointName):
        self._addCmd(b'HERE ' + bytes(pointName, 'UTF-8'))
    
    def clear(self, pointName):
        self._addCmd(b'DELETEPOINT ' + bytes(pointName, 'UTF-8'))
    
    def move(self, pointName):
        self._addCmd(b'MOVE ' + bytes(pointName, 'UTF-8'))
    
    # 0=low, 3=max
    def gripForce(self, amount):
        self._addCmd(b'SETGRIPSTRENGTH ' + bytes(str(amount), 'UTF-8'))
    
    def grip(self):
        self._addCmd(b'CLOSE')
    
    def release(self):
        self._addCmd(b'OPEN')
    
    def getPoints(self):
        # prevent hanging when called before reset()
        if not self._workerThread or not self._workerThread.is_alive():
            return {}
        
        self.pointStrs = {}
        self.pointsRead = False
        self.pointsLock.release()
        while not self.pointsRead:
            time.sleep(0.01)
        self.pointsLock.acquire()
        
        return self.pointStrs
    
    def close(self):
        #TODO: home pos
        # stop all worker activity
        #self.posnLock.acquire()
        #self.ioLock.acquire()
        #self.cmdLock.acquire()
        self._s.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    robot = PlateCrane()
    
    robot.reset()
    
    robot.close()

