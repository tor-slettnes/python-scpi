#!/bin/echo "Do not invoke directly"
#===============================================================================
## @file base_client.py
## @brief SCPI client - base for SocketClient and SerialClient
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Modules relative to install folder
from .base_client import BaseClient

class SerialClient (BaseClient):
    '''Connect to a SCPI server over a serial interface'''

    def __init__(self, port=None, *,
                 use_index=True,            # <index> COMMand Args...
                 logger=None,               # Callback method for logging: callback(level, message)
                 **serial_options):         # Options for `serial.Serial()`

        BaseClient.__init__(self,
                            use_index=use_index,
                            logger=logger);
        self.serial = None
        self.instream = None
        self.outstream = None
        if port:
            self.open(port=port, **serial_options)

    def open(self, port, threaded=True, **options):
        if not self.serial:
            import serial
            self.serial = serial.Serial(port, **options)
            self.instream = self.outstream = self.serial
            self.is_connected = True
            if threaded:
                self.startReceiveThread()


    def close(self):
        if self.serial:
            self.serial.close()
            self.serial = self.instream = self.outstream = None
            self.is_connected = False
            self.stopReceiveThread()

    def fileno(self):
        return self.serial.fileno() if self.serial else None
