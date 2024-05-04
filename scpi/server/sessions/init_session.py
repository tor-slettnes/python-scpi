#===============================================================================
## @file init_session.py
## @brief SCPI session for running startup/shutdown modules
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from .detached_session import DetachedSession
from .module_session import ModuleSession
from .symbols import FULL, SYNC, ASYNC
from ...tools.publication import info

class InitSession (DetachedSession, ModuleSession):
    '''
    Initialization module session.  These are run at a higher access
    level than modules invoked by a client.
    '''

    def __init__ (self, module, *args, **argmap):
        ModuleSession.__init__(self, module=module, parent=None, access=FULL, *args, **argmap)
        info('Loading init module: %s'%(module,))

    def handleInput (self, instream, context, nextReply=ASYNC, nextCommand=ASYNC, catchReturn=True):
        return DetachedSession.handleInput(self,
                                           instream,
                                           context,
                                           nextReply=nextReply,
                                           nextCommand=nextCommand,
                                           catchReturn=catchReturn)
