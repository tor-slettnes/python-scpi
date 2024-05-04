#===============================================================================
## @file symbols.py
## @brief Container for external/internal SCPI client sessions
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

import copy

### Handling of NextReply exception
NextOp = ('sync', 'async', 'raise', 'passthrough')
(SYNC, ASYNC, RAISE, PASSTHROUGH) = list(range(len(NextOp)))

### Access levels
AccessLevels = ('Guest', 'Observer', 'Controller', 'Administrator', 'Full')
(GUEST, OBSERVER, CONTROLLER, ADMINISTRATOR, FULL) = list(range(len(AccessLevels)))

### Notification triggers
Triggers = ('Connect', 'Disconnect',  # An external client connects or disconnects
            'Access', 'Authenticate', # An external client changes access level or authenticates
            'Error')                  # A command returns an error.
(T_CONNECT, T_DISCONNECT, T_ACCESS, T_AUTH, T_ERROR) = list(range(len(Triggers)))

#===============================================================================
### Context

class Context (object):
    DefaultInvocation = ('invoke', ())

    def __init__ (self, session, scope, invocation=None, data=None,
                  text=None, leaf=None, response=None, exception=None, **opts):
        if data is None:
            data = {}

        self.update(session=session, scope=scope,
                    invocation=invocation, data=data, text=text,
                    leaf=leaf, response=response, exception=exception, **opts)

    def clone (self, **updates):
        return copy.copy(self).update(**updates)

    def update (self, **updates):
        for k, v in list(updates.items()):
            setattr(self, k, v)
        return self

    def getOutputs (self, alwaysNamed=False, raw=False):
        if self._outputs is not None:
            return self._outputs
        elif self.leaf and self._invocation in (None, self.DefaultInvocation):
            return self.leaf.formatOutputs(self.response, alwaysNamed=alwaysNamed, raw=raw)
        else:
            return []

    def setOutputs (self, outputs):
        self._outputs = outputs

    outputs = property(getOutputs, setOutputs)


    def _getInvocation (self):
        return self._invocation or self.DefaultInvocation

    def _setInvocation (self, invocation):
        self._invocation = invocation

    invocation = property(_getInvocation, _setInvocation)

