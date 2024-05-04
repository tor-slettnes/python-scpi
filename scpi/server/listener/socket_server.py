#!/usr/bin/python3
#===============================================================================
## @file socket_server.py
## @brief Instrument Command Server & Request Handler - Network/TCP server
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base_server import BaseRequestHandler, BaseServer, server_types
from ..sessions.socket_session import SocketSession
from ...tools.publication import info

## Standard Python modules
from socket import error as SocketError
from socketserver  import TCPServer, StreamRequestHandler
from threading import Thread


class SocketRequestHandler (BaseRequestHandler, StreamRequestHandler):
    """
    Request handler for incoming client connections.
    """

    prefix = 'N'
    OptionNames = (PREEXEC, POSTEXEC) = ('preexec', 'postexec')

    def setup (self):
        StreamRequestHandler.setup(self)

        description   = 'network client at %s:%d'%self.connection.getpeername()
        self.session  = SocketSession(connection=self.connection,
                                      instream=self.rfile,
                                      outstream=self.wfile,
                                      description=description,
                                      id_prefix=self.prefix)

class SocketServer (TCPServer, BaseServer):
    RequestHandler      = SocketRequestHandler
    default_interface   = ''
    default_port        = 7000
    daemon_threads      = True
    allow_reuse_address = True

    def __init__ (self, **opts):
        address = opts.pop('address', self.default_interface)
        port    = opts.pop('port', self.default_port)
        TCPServer.__init__(self, (address, port), self.RequestHandler)
        self.session_id = 0
        self.options    = opts
        info('Attached %s to %s port %s'%(self.RequestHandler.__name__, address or "TCP", port))

    def get_request (self):
        try:
            return TCPServer.get_request(self)
        except SocketError:
            raise EOFError

    def process_request_thread (self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        except BaseException:
            shutdown(reason="Initiated from %s"%(self.RequestHandlerClass.__name__))
        finally:
            self.shutdown_request(request)

    def process_request (self, request, client_address):
        self.session_id += 1
        t = Thread(target=self.process_request_thread,
                   args=(request, client_address),
                   name="%s%d"%(self.RequestHandler.prefix, self.session_id),
                   daemon=True)
        t.start()

server_types['plain'] = server_types[None] = SocketServer
