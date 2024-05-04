#===============================================================================
## @file scpiMacroLeafs.py
## @brief Commands to support macro creation & query
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from ..base.macro import Macro
from ..base.dynamic_base import DynamicCommandLeaf
from ..base.leaf import Asynchronous, Singleton, Controlling, Observing

from ..exceptions import RunError
from ..sessions.symbols import SYNC, ASYNC, RAISE

class MacroLeaf (DynamicCommandLeaf):
    _dynamicCommandType = Macro

class MACRo_Add (Controlling, MacroLeaf):
    '''
    Create or redefine a macro command.  The macro will remain until
    either deleted, redefined, or the instrument is restarted.

    See also the MACROS help topic ("HELP? MACROS") for information
    about macro parameters/substitutions and inline macros.
    '''

    class TooMuchAccess (RunError):
        'You cannot create macro with a higher access level than your own.'

    class InvalidEstimationCriterion (RunError):
        'No such estimation criterion exists: %(criterion)r'


    AsyncOptions = { "BLOCK"      : SYNC,
                     "BACKGROUND" : ASYNC,
                     "PROPAGATE"  : RAISE }

    def declareInputs (self):
        MacroLeaf.declareInputs(self)

        self.setInput('replaceExisting',
                      description=
                      'If another dynamic command by the same name already '
                      'exists, replace it')

        self.setInput('asynchronous', hidden=True,
                      description='Deprecated; please use "background" instead.')

        self.setInput('background', type=bool, named=True, default=None,
                      description=
                      'Execute the macro in the background, allowing further '
                      'commands to be issued while it is running.')

        self.setInput('onNext', type=self.AsyncOptions, named=True, default=ASYNC,
                      description=
                      'Determines how asynchronous commands invoked in this macro '
                      'are handled. The default is to run them in the background '
                      'while moving on to the subsequent commands in the macro. '
                      'NEXT does the same, but also issues a NEXT response from '
                      'the macro itself to allow the caller to move on to the next '
                      'command.  BLOCK causes all commands to run until completion '
                      'before moving on.')

        self.setInput('inline', type=bool, named=True, default=False,
                      description='Run within the parent execution context '
                      '(i.e., command scope, exception space, etc), '
                      'even if invoked within a different branch.')

        self.setInput('hidden',
                      description=
                      'Hide the macro from the list of commands presented '
                      'in the HELP? and XMLHelp? outputs')

        self.setInput('singleton',
                      description=
                      'Allow only one instance of this command to run at '
                      'any given time.')

        self.setInput('access', type=AccessLevels,
                      description=
                      'Access level granted to the macro upon invocation. '
                      'By default, the macro will run with the access '
                      'level of the session that created it.')

        self.setInput('requiredAccess', type=AccessLevels,
                      description=
                      'Access level required to run the macro.  By default, '
                      'macros whose name ends with a "?" or "*", typically '
                      'indicating a query, require Observer access, wheras '
                      'other macros require the lesser of "Controller" '
                      'access and the access level of the session in '
                      'which the macro is defined.')

        self.setInput('modifyAccess', type=AccessLevels,
                      description=
                      'Access level required to delete or replace the macro.'
                      'By default, this is copied from the current access level '
                      'of the session in which the macro is defined.')

        self.setInput('name',
                      description='Name of the macro.')

        self.setInput('arguments',
                      description=
                      'Macro arguments; the last argument is the macro text '
                      '(i.e. the commands that are executed when then macro '
                      'is invoked)')


    def run (self, _session, 
             asynchronous=False,
             background=False,
             onNext=AsyncOptions,
             inline=False,
             hidden=False,
             singleton=False,
             replaceExisting=False,
             access=None,
             requiredAccess=None,
             modifyAccess=None,
             name=str, *arguments):

        try:
            text = arguments[-1]

            if text.startswith('\r'):
                text = text[1:]
            if text.startswith('\n'):
                text = text[1:]

            if not text.endswith('\n'):
                text += '\n'

        except IndexError:
            text = '\n'

        arguments     = arguments[:-1]
        currentAccess = _session.getAccessLevel()
        defaultAccess = self.defaultAccess(name)
        defaultAccess = min(defaultAccess, currentAccess)

        if access is None:
            access = currentAccess
        elif access > currentAccess:
            raise self.TooMuchAccess(requestedAccess=access, currentAccess=currrentAccess)

        if requiredAccess is None:
            requiredAccess = defaultAccess

        classes = []
        if background or (background is None and asynchronous):
            classes.append(Asynchronous)
        if singleton:
            classes.append(Singleton)
        classes.append((Macro, InlineMacro)[inline])
        obj = self.incarnate(name, tuple(classes), parent=self.parent)

        obj.arguments      = arguments
        obj.text           = text
        obj.requiredAccess = requiredAccess
        obj.access         = access
        obj.onNext         = onNext
        obj.declareMacroInputs()

        debug("Adding macro %s"%(name,))

        self.addinstance(_session, name, obj,
                         replaceExisting=replaceExisting,
                         modifyAccess=modifyAccess,
                         hidden=hidden,
                         singleton=singleton,
                         parent=self.parent)




class MACRo_Remove (Controlling, MacroLeaf):
    '''
    Delete a macro branch previously created within this scope.
    '''

    def run (self, _session, ignoreMissing=False, name=str):
        self.delinstance(_session, name, ignoreMissing, parent=self.parent)




class MACRo_Query (Observing, MacroLeaf):
    '''
    Show the definition of the given macro.
    '''
    def declareOutputs (self):
        MacroLeaf.declareOutputs(self)
        self.addOutput('argument', type=str, repeats=(0, None))


    def run (self, name=str):
        obj = self.findDynamicCommand(name, parent=self.parent, searchType=Macro)
        return obj.arguments + ("\n%s"%obj.text,)


class MACRo_Enumerate (Observing, MacroLeaf):
    '''
    Return a list of dynamic subbranches in this branch.
    '''

    def declareOutputs (self):
        MacroLeaf.declareOutputs(self)
        self.addOutput('command', type=str, repeats=(0, None))

    def run (self):
        return tuple(self.listinstances(parent=self.parent))

