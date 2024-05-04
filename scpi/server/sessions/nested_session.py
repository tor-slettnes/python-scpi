#===============================================================================
## @file nested_session.py
## @brief Container for external/internal SCPI client sessions
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from .symbols import SYNC, ASYNC
from .base_session import BaseSession

class NestedSession (BaseSession):
    '''
    Nested command execution.
    '''

    def __init__ (self, parent, input, access=None, **argmap):
        BaseSession.__init__(self, input, **argmap)

        if access is not None:
            self.accessLimit = self.accessLevel = self.authLimit = access

        elif parent:
            self.accessLimit = parent.accessLimit
            self.accessLevel = parent.accessLevel
            self.authLimit   = parent.authLimit
            self.jobs        = parent.jobs

        self.parent = parent

    #===========================================================================
    ### Property functions for access to <instance>.parent

    def setparent (self, parent):
        if parent:
            self._parent = weakref.ref(parent)
        else:
            self._parent = None

    def getparent (self):
        if self._parent:
            return self._parent()
        else:
            return None

    def delparent (self):
        self._parent = None

    parent = property(getparent, setparent, delparent)

    def handleInput (self, input, context, nextReply=ASYNC, nextCommand=ASYNC, catchReturn=True):
        try:
            return self.runBlock(input, context,
                                 nextReply=nextReply,
                                 nextCommand=nextCommand,
                                 catchReturn=catchReturn)
        except Error as e:
            e.insertContext("In %s"%(self.description,))
            e.throw()


    #===========================================================================
    ### PUBLish/SUBScribe support

    def subscribe (self, *args, **kwargs):
        parent = self.parent
        if parent:
            parent.subscribe(*args, **kwargs)

    def unsubscribe (self, *args, **kwargs):
        parent = self.parent
        if parent:
            parent.unsubscribe(*args, **kwargs)

    def clearSubscriptions (self, *args, **kwargs):
        parent = self.parent
        if parent:
            parent.clearSubscriptions(*args, **kwargs)

    def getSubscriptions (self, *args, **kwargs):
        parent = self.parent
        if parent:
            return parent.getSubscriptions(*args, **kwargs)

