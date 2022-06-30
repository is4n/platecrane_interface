import serial
import os
import threading
import time
import logging

NUM_IO = 48
CMD_TERM = b'00\x10\r\n'

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
        
        while True:
            resp = self._s.readline()
            
            if not resp:
                raise ValueError('robot timeout when reading points')
            if (resp == b'\r\n'):
                break
            
            name, values = str(resp[:-2])[2:-1].split(',', 1)
            self.pointStrs[name] = values
    
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
                    msg = f'{self.command}: unexpected robot response:'
                    msg += str(resp)
                    self.error = msg

            self.command = None
    
    def _readIO(self, ioToRead):
        inpStr = bytes(str(ioToRead), 'UTF-8')
        self._writeWithEcho(b'GETINP ' + inpStr + b'\r\n')
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
        
        self.sendDriverParams = sendDriverParams
        self._s = serial.Serial(port, 9600, timeout=0.5)
        self._configPath = config
    
    # the Y- and P-axis drivers lose their params on startup, so
    # we re-send them here
    def driverInit(self):
        # disable all other communcation before entering TERMINAL mode
        self.posnLock.acquire()
        self.ioLock.acquire()
        
        self._addCmd(b'TERMINAL')
        self.expectedResponse = None
        
        with open(os.path.join(self._configPath, 'driver.params'), 'r') as dpFile:
            driverConfig = dpFile.read().split('\n')
            
            for line in driverConfig:
                if line:
                    self._addCmd(bytes(line, 'UTF-8'))
        
        self.expectedResponse = CMD_TERM
        self.ignoreEcho = True
        self._addCmd(b'TERMINAL')
        self.ignoreEcho = False
        
        self.posnLock.release()
        self.ioLock.release()
    
    def reset(self):
        if not self._workerThread or not self._workerThread.is_alive():
            self._workerThread = threading.Thread(
                target=self._serialWorker,
                daemon=True
            )
            self._workerThread.start()
        
        self._addCmd(b'HOME')
        if self.sendDriverParams:
            self.driverInit()
    
    def getPosition(self):
        return str(self.posnStr[:-2]).strip("'b")
    
    def getInputs(self):
        #return str(self.ioStrs).replace(',', '\n').strip('{}b') TODO
        return ""
    
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
    
    def move(self, pointName):
        self._addCmd(b'MOVE ' + bytes(pointName, 'UTF-8'))
    
    def getPoints(self):
        # prevent hanging when called before reset()
        if not self._workerThread or not self._workerThread.is_alive():
            return {}
        
        self.pointStrs = {}
        self.pointsLock.release()
        while not self.pointStrs:
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

