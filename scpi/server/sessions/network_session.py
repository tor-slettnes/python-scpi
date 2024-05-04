#===============================================================================
## @file network_session.py
## @brief SCPI session for connected network clients
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .client_session import ClientSession
from .symbols import AccessLevels, GUEST, ADMINISTRATOR, T_CONNECT, T_DISCONNECT
from ..exceptions import Error
from ...tools.publication import INFO

## Standard Python modules
import threading

class NetworkSession (ClientSession):
    '''
    Handle network connections
    '''

    enterHooks = []
    exitHooks  = []

    def __init__ (self, *, connection, instream, outstream, preexec=None, postexec=None, **argmap):
        self.peer        = connection.getpeername()
        self.interface   = connection.getsockname()

        self.enterHooks  = type(self).enterHooks[:]
        self.addEnterHook(preexec)

        self.exitHooks   = type(self).exitHooks[:]
        self.addExitHook(postexec)

        ClientSession.__init__(self, instream=instream, outstream=outstream, **argmap)


    def setup (self, context):
        cleanupargs  = ClientSession.setup(self, context)
        scope        = context.scope
        commandscope = scope.commandPath()

        self.notify(INFO, T_CONNECT,
                    ('session',     self.sessionid),
                    ('scope',       commandscope),
                    ('accessLevel', AccessLevels[self.accessLevel]),
                    ('accessLimit', AccessLevels[self.accessLimit]),
                    ('authLimit',   AccessLevels[self.authLimit]),
                    ('ifaddr',      "%s:%s"%self.interface),
                    ('ipaddr',      "%s:%s"%self.peer))

        if self.runHooks(self.enterHooks, context, "enter hook"):
            # keys   = 'product', 'version', 'build', 'serialnumber', 'hostname', 'nickname'
            # values = sysconfig.get(keys)
            # items  = list(zip(keys, values))
            items = []
            if commandscope:
                items.append(('scope', commandscope))
            self.sendReady(*items)

        return (scope,) + cleanupargs


    def cleanup (self, context, scope, *cleanupargs):
        self.notify(INFO, T_DISCONNECT,
                    ('scope',      context.scope.commandPath()),
                    ('ifaddr',     "%s:%s"%self.interface),
                    ('ipaddr',     "%s:%s"%self.peer))

        thread = threading.currentThread()
        for subcontext, subthread, func, args, argmap, asynchronous in self.jobs:
            if not asynchronous and subthread is not thread:
                self.debug("Client disconnected, aborting command: %s"%(commandtext.strip(),))
                subthread.abort(recursive=False)

        context.scope = scope
        if self.runHooks(self.exitHooks, context, "exit hook"):
            return ClientSession.cleanup(self, context, *cleanupargs)


    def addEnterHook (self, hook):
        if hook:
            self.enterHooks.append(hook)


    def addExitHook (self, hook):
        if hook:
            self.exitHooks.append(hook)


    def runHooks (self, hooks, context, kind, access=ADMINISTRATOR):
        originalAccess = self.accessLevel
        self.accessLevel = access

        try:
            for text in hooks:
                try:
                    self.runBlock(text, context, catchReturn=True)
                except Error as e:
                    e.insertContext(text)
                    e.insertContext("In %s %s"%(self.description, kind))
                    self.logException(e)
                    self.respondError(text, e)
                    return False
            else:
                return True
        finally:
            self.accessLevel = originalAccess


    #===========================================================================
    ### Access Control

    def interfaceLimit (self, limittype):
        limit = None

        if limit is None:
            host, port = self.interface
            limit = self.accessinfo.get(limittype, {}).get(host, None)

        if limit is None:
            limit = self.accessinfo.get(limittype, {}).get('default', None)

        if limit is None:
            limit = GUEST
        else:
            limit = self.accessLevelIndex(limit)

        return limit
