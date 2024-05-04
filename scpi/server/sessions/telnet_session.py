#===============================================================================
## @file telnet_session.py
## @brief SCPI session for interactive telnet clients
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .network_session import NetworkSession

class TelnetSession (NetworkSession):
    '''
    Handle connections from interactive/telnet clients
    '''

    def __init__ (self, handler, **argmap):
        NetworkSession.__init__(self,
                                connection=handler.sock,
                                instream=handler,
                                outstream=handler,
                                **argmap)

    def handleInput (self, instream, context):
        instream.setAutoComplete(self.autocomplete)
        try:
            return NetworkSession.handleInput(self, instream, context)
        finally:
            instream.setAutoComplete(None)

    def autocomplete (self, text):
        return None
        # return [ text+"a", text+"b" ]

