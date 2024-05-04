#!/usr/bin/python3
#===============================================================================
## @file telnet_server.py
## @brief Instrument Command Server & Request Handler - Telnet server
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base_server import server_types
from .socket_server import SocketRequestHandler, SocketServer
from ..sessions.telnet_session import TelnetSession
from ...tools.telnethandler import TelnetHandler

## Standard Python modules
from socketserver import StreamRequestHandler

class TelnetRequestHandler (SocketRequestHandler):
    """
    Request handler for incoming telnet clients.
    """

    prefix = 'T'
    initstring  = '''
--- Type "HELP? OVERVIEW" for help on commands and syntax.
--- Press [ESC] then [H] for a list of editing keys.
'''

    def setup (self):
        StreamRequestHandler.setup(self)
        telnetHandler = TelnetHandler(self.connection, self.initstring)
        description   = 'telnet client at %s:%d'%self.connection.getpeername()
        self.session  = TelnetSession(handler=telnetHandler,
                                      description=description,
                                      id_prefix=self.prefix)


class TelnetServer (SocketServer):
    RequestHandler = TelnetRequestHandler
    default_port   = 2323

    def __init__ (self, *args, **kwargs):
        SocketServer.__init__(self, *args, **kwargs)


server_types['telnet'] = TelnetServer
