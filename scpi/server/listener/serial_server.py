#!/usr/bin/python3
#===============================================================================
## @file scpiServer.py
## @brief Instrument Command Server & Request Handler
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base_server import BaseRequestHandler, BaseServer, server_types
from ..sessions.serial_session import SerialSession
from ...tools.publication import info

## Standard Python modules
from threading import Thread
from os.path import exists

class SerialRequestHandler (BaseRequestHandler):
    '''
    Manage a serial connection
    '''

    def __init__ (self, serial):
        self.session = SerialSession(
            serial,
            description = 'Serial listener on %s'%(serial.port,),
            id_prefix = 'S')


class SerialServer (BaseServer):
    def __init__(self, port, **opts):
        import serial
        self.serial = serial.Serial(port, **opts)
        self.active = False

    def is_available(self):
        return exists(self.serial.port()) and not self.handler

    def fileno(self):
        return self.serial.fileno()

    def handle_request(self):
        t = Thread(target=self.handle_request_thread,
                   name="SerialRequestHandler",
                   daemon=True)
        t.start()

    def handle_request_thread(self):
        self.active = True
        handler = SerialRequestHandler(self.serial)
        handler.handle()
        self.active = False

server_types['serial'] = SerialServer
