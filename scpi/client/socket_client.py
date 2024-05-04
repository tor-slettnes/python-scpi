#!/bin/echo "Do not invoke directly"
#===============================================================================
## @file base_client.py
## @brief SCPI client - base for SocketClient and SerialClient
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Modules relative to install folder
from .base_client import BaseClient

### Standard Python modules
import threading
import socket

DEFAULT_SERVER = ("127.0.0.1", 7000)

#===============================================================================
### @class SocketClient

class SocketClient (BaseClient):
    '''Connect to a SCPI server over a TCP socket'''

    def __init__(self,
                 serveraddr : tuple[str, int] = None,
                 **baseargs):

        BaseClient.__init__(self, **baseargs)
        self.socket = None
        if serveraddr:
            self.connect(serveraddr)


    def __del__(self):
        self.disconnect()

    def connect(self,
                serveraddr: tuple[str, int] = None,
                timeout: float = None,
                threaded: bool = True,
                ignoreFailure: bool = False) -> bool:
        '''
        Inputs:
          @param[in] serveraddr
            Server Host/port
          @param[in] timeout
            Timeout for initial connect, in seconds
          @param[in] threaded
            Use dedicated thread for receiving from server
          @param[in] ignoreFailure
            Do not raise error if connection fails (just return boolean indicator)
          @return
            Boolean indicator of whether connection succeeded
        '''

        if self.is_connected and self.socket:
            if not ignoreFailure:
                raise self.SCPIAlreadyConnected(
                    "Already connected to server %s"%(self.socket.getpeername(),))

            return False

        if serveraddr:
            self.serveraddr = serveraddr
        elif not self.serveraddr:
            self.serveraddr = DEFAULT_SERVER

        self.log(self.LOG_CONNECT, 'Connecting to %s:%s, timeout=%s'%(self.serveraddr + (timeout, )))

        ### Communication
        self.socket    = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fileno    = self.socket.fileno
        self.instream  = self.socket.makefile('rb', -1)
        self.outstream = self.socket.makefile('wb', -1)
        self.connectionError = None

        self.socket.settimeout(timeout)

        try:
            self.socket.connect(self.serveraddr)

        except socket.error as e:
            self.on_disconnect()
            self.connectionError = e
            if not ignoreFailure:
                raise SCPICommunicationError(e.args[-1])

            return False

        self.socket.settimeout(None)
        self.is_connected = True

        self.log(self.LOG_CONNECT, 'Connected to %s:%s'%self.serveraddr)

        if threaded:
            self.startReceiveThread()

        self.on_connect()
        return True


    def disconnect(self):
        gotThread = self.is_receiving

        if self.is_connected:
            if self.serveraddr:
                self.log(self.LOG_CONNECT, 'Disconnecting from %s:%s'%self.serveraddr)
            self.is_connected = False
            self.socket.shutdown(socket.SHUT_RDWR)

        elif not gotThread:
            self.on_disconnect()

    def fileno(self) -> int:
        return self.socket.fileno

    def writeline(self, text):
        data = text.encode() if isinstance(text, str) else text
        self.socket.send(data + b'\r\n')

    def send_command(self, command):
        '''Send a command to the SCPI Server'''

        if not self.is_connected and self.autoconnect:
            self.connect()

        return BaseClient.send_command(self, command)


    def on_disconnect(self):
        if self.socket:
            self.socket.close()
            self.socket = None
            self.states = None

        BaseClient.on_disconnect(self)
