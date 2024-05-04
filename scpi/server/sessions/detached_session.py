#===============================================================================
## @file detached_session.py
## @brief SCPI session for running detached macros
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from .macro_session import MacroSession
from .symbols import Context, SYNC, ASYNC
from ...tools.publication import info

class DetachedSession (MacroSession):
    '''
    Command execution detached from any controlling sessions
    '''
    def handleInput (self,
                     input,
                     context=None,
                     scope=None,
                     nextReply=ASYNC,
                     nextCommand=ASYNC,
                     catchReturn=True):

        if context is None:
            context = Context(self, scope)

        args = (input, context)
        kwargs = dict(nextReply=nextReply, nextCommand=nextCommand, catchReturn=catchReturn,
                      where='In %s'%(self.description,))
        self.handleExceptions(context, self.runBlock, args, kwargs, info)

