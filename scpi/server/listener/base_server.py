#!/usr/bin/python3
#===============================================================================
## @file base_server.py
## @brief Command Server & Request Handler - base classes
## @author Tor Slettnes <tor@slett.net>
#===============================================================================


class BaseRequestHandler (object):
    top = None
    prefix = '-'
    session = None

    @classmethod
    def setTop (cls, top):
        cls.top = top

    def option (self, name, default=None):
        return self.server.options.get(name, default)

    def setup(self):
        pass

    def handle(self):
        if self.session:
            self.session.handle(self.top)

    def finish(self):
        pass


class BaseServer (object):

    def is_available(self) -> bool:
        '''Return True if this server is currently available'''
        return True

    def fileno(self):
        raise NotImplementedError()


server_types = {}
