#===============================================================================
## @file scpiSessionBranch.py
## @brief Commands to manage client sessions
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from ..base.leaf import Public, Leaf
from ..sessions.symbols import AccessLevels

class ACCess (Public, Leaf):
    '''
    Request a specific access level for this session.

    Each instrument controller command is restricted according to
    access level.  Before executing a given command, the client must
    obtain the corresponding access level or higher.

    Once a client connects to the instrument controller via a specific
    communications interface (e.g. a specific ethernet port on the
    instrument), a default access level is granted.  The client may
    then request a lower access level, or - more commonly - a higher
    one.

    To request an access level that is higher than this initial level,
    the client must first authenticate using hte "AUTHenticate"
    command. After this, the client may request access up to the
    lesser of:
      - the level allowed by the authentication credentials used, and
      - the maximum level allowed over the communications interface

    The client may also request exclusive access to the given level.
    This means that the command will fail if any other sesson
    currently holds the given access level or above, and that no other
    clients will be granted access to this level while the original
    client holds the exclusive access.  In effect, this is a "lock"
    that can be used to perform instrument control.

Examples:
    * Gain exclusive controller access to the instrument, perform
      a run, then relinquish controller access.

        ACCess -exclusive CONTROLLER
        FLAG MyRun RunProtocol MyProtocol ...
        ...
        SYNC MyRun
        ACCess OBSERVER
    '''

    def run (self, _session,
             stealth: bool = False,
             exclusive: bool = False,
             level = AccessLevels):
        _session.setAccessLevel(level, exclusive, stealth)


class ACCess_Query (Public, Leaf):
    '''
    Return the current access level for this session.
    '''
    Properties = ('level', 'limit', 'exclusive', 'stealth')

    def declareInputs (self):
        Leaf.declareInputs(self)
        self.setInput('named', type=bool, named=True, default=False)
        self.setInput('properties', type=self.Properties, repeats=(0, len(self.Properties)))

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('values', type=tuple, repeats=(1, None))

    def run (self, _session, named=False, *properties):
        if not properties:
            properties = list(range(len(self.Properties)))
            named = True

        values = (_session.getLevelName(_session.getAccessLevel()),
                  _session.getLevelName(_session.getAccessLimit()),
                  _session.getExclusiveFlag(),
                  _session.getStealthFlag())

        items = [((None, self.Properties[p])[named], values[p]) for p in properties]
        return tuple(items)

