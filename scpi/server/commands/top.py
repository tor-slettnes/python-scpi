#===============================================================================
## @file scpiTop.py
## @brief Implementation of a top level branch (trunk).
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from .populated_branch import PopulatedBranch
from ..base.base import Base
from ...tools.scheduler import scheduler

class Top (PopulatedBranch):
    def __init__ (self):
        Base.top = self
        PopulatedBranch.__init__(self, name='Top', parent=None)
        self.addShutDownAction(scheduler.shutdown)
        scheduler.start()

    def shutdown (self):
        for (method, args, kwargs) in self.shutdownHook:
            method(*args, **kwargs)
