#===============================================================================
## @file socket_session.py
## @brief SCPI Session for clients connected over a plain TCP socket
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .network_session import NetworkSession

## Standard Python modules
import threading, queue


class SocketSession (NetworkSession):
    '''
    Handle connections on plain TCP sockets
    '''

    def __init__ (self, *args, **kwargs):
        NetworkSession.__init__(self, *args, **kwargs)
        self.writeQueue = queue.Queue()

    def setup (self, context):
        cleanupargs = NetworkSession.setup(self, context)
        outputThread = threading.Thread(target=self._outputHandler,
                                        name="%s-Output"%(self.sessionid,),
                                        daemon=True)
        outputThread.start()
        return (outputThread,) + cleanupargs

    def cleanup (self, context, outputThread, *args):
        self.writeQueue.put(None)
        outputThread.join()
        NetworkSession.cleanup(self, context, *args)

    def send (self, text, callback=None):
        self.writeQueue.put((text, callback))

    def _outputHandler (self):
        item = self.writeQueue.get()
        while item is not None:
            NetworkSession.send(self, *item)
            item = self.writeQueue.get()

