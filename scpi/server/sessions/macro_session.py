#===============================================================================
## @file macro_session.py
## @brief SCPI session for running macros
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .nested_session import NestedSession
from .symbols import ASYNC, RAISE

class MacroSession (NestedSession):
    '''
    Macro command session; process NEXT and RETurn
    '''

    def handleInput (self, input, context, nextReply=ASYNC, nextCommand=RAISE, catchReturn=True):
        return NestedSession.handleInput(self,
                                         input,
                                         context,
                                         nextReply=nextReply,
                                         nextCommand=nextCommand,
                                         catchReturn=catchReturn)

