#===============================================================================
## @file return_leafs.py
## @brief SCPI commands that break out of the current command scope
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from ..base.leaf import Leaf, Observing
from ..base.parameter import autoType
from ..exceptions import ReturnValue, NextCommand, Break

class NEXT (Observing, Leaf):
    """
    Cause the remainder of the containing macro or module to be
    executed asynchronously, i.e. in the background.  The client
    (which in turn may be another macro or module) receives a NEXT
    reply, and may at this point issue additional commands.
    """

    def run (self):
        raise NextCommand(self)


class BREak (Observing, Leaf):
    """
    Break out of a REPeat, ITERate, or SCHedule loop.
    """

    def declareInputs(self):
        Leaf.declareInputs(self)
        self.setInput('levels',
                      range=(1, None),
                      description='Number of execution scopes to break out of')

    def run (self,
             levels: int = 1):
        raise Break(levels)


class RETurn (Observing, Leaf):
    """
    Exit out of a macro or module, and return the supplied string to the caller.
    Useful in macros.
    """

    def declareInputs (self):
        Leaf.declareInputs(self)
        self.setInput('delimiter', type=str, default=None, named=True)
        self.setInput('arguments', type=tuple)

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('item', type=tuple, default=None, repeats=(0, None))

    def run (self,
             _session,
             _context,
             split: bool = False,
             delimiter: str = None,
             *arguments: str):

        if split:
            parts = []
            for part in arguments:
                opt, value, raw = part
                if opt:
                    parts.append(part)
                elif delimiter:
                    args = value.split(delimiter)
                    if args and not args[-1]:
                        args.pop()
                    parts.extend([(None, arg) for arg in args])
                else:
                    text, args = _session.expandArgs(value, context=_context)
                    parts.extend(args)
        else:
            parts = arguments

        raise ReturnValue(*parts)

