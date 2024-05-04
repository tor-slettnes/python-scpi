#===============================================================================
## @file module_session.py
## @brief SCPI session for running module files
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install folder
from .symbols import *
from .nested_session import NestedSession
from ..exceptions import RunError
from ...tools.publication import debug, info

## Standard Python modules
import os.path

### Path for module files
_modpath = [ ]

def getModulePath ():
    return _modpath

def setModulePath (path):
    global _modpath
    _modpath = path

class ModuleSession (NestedSession):
    '''
    Module file session.
    '''

    class NoSuchModule (RunError):
        '''Unable to locate module %(filename)r'''

    defaultSuffixes = ('.scpi', '.mod')

    def __init__ (self, module, **argmap):
        if hasattr(module, 'read'):
            instream = module
        else:
            filepath = self.filepath(module)
            instream = open(filepath)

        NestedSession.__init__(self, input=instream, **argmap)

    @classmethod
    def filepath (cls, filename, ignoreMissing=False):
        root, ext = os.path.splitext(filename)
        candidates = [ filename ]
        if not ext in cls.defaultSuffixes:
            candidates.extend([ filename+suffix for suffix in cls.defaultSuffixes ])

        for d in getModulePath():
            for candidate in candidates:
                filepath = os.path.join(d, candidate)
                if os.path.isfile(filepath):
                    return filepath

        if not ignoreMissing:
            debug("Module %r not found. Candidate names: %s. Search path:%s"%
                  (filename, ", ".join(candidates), ''.join([ "\n\t"+d for d in getModulePath()])))
            raise cls.NoSuchModule(filename=filename)

    def handleInput (self, instream, context, nextReply=ASYNC, nextCommand=RAISE, catchReturn=True):
        commandPath = context.scope.commandPath()

        self.debug("Running module in command scope %s: %r" %
                   (commandPath or "(ROOT)", instream.name))

        return NestedSession.handleInput(self, instream, context,
                                         nextReply=nextReply,
                                         nextCommand=nextCommand,
                                         catchReturn=catchReturn)
