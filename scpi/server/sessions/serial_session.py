#===============================================================================
## @file scpiSession.py
## @brief Container for external/internal SCPI client sessions
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .client_session import ClientSession
from .symbols import GUEST

class SerialSession (ClientSession):
    '''
    Handle serial connections
    '''

    #===========================================================================
    ### Access Control

    def __init__ (self, serial, **argmap):
        ClientSession.__init__(self, serial, serial, **argmap)

    def interfaceLimit (self, limittype):
        strlimit = None

        if strlimit is None:
            strlimit = self.accessinfo.get(limittype, {}).get('serial', None)

        if strlimit is None:
            strlimit = self.accessinfo.get(limittype, {}).get('default', None)

        return self.accessLevelIndex(strlimit) if strlimit else GUEST

