#===============================================================================
## @file help_leafs.py
## @brief HELP? command
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Modules relaive to install path
from ..base.base import Base, Hidden, commandTypes
from ..base.leaf import Leaf, Public, Observing
from ..base.branch import Branch
from ..base.dynamic_base import Dynamic
from ..sessions.symbols import AccessLevels, OBSERVER
from ..exceptions import RunError

### Standard Python modules
from fnmatch import fnmatchcase

class HELP (Hidden, Public, Leaf):
    """
    Do nothing, but do it well.
    """
    hidden = True

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('text',
                       type=list,
                       description='Human readable text')


    def run (self, *arguments):
        return ([
            'For a list of subcommands and help topics, try "HELP?".',
            'For more information on getting help: "HELP? HELP?".',
            'For a general overview, issue the command "HELP? OVERVIEW".',
            ],)



class _HelpLeaf (Public, Leaf):

    def declareInputs (self):
        Leaf.declareInputs(self)

        self.setInput('unique',
                      type=bool,
                      named=True,
                      default=False,
                      description='List only commands that are unique '
                      'to this branch - i.e. that are not part of a '
                      '"generic" branch.')

        self.setInput('type',
                      type=commandTypes,
                      named=True,
                      default=commandTypes[None],
                      description='Restrict command list to a specific class of commands. '
                      'Note that the different types are not mutually exclusive; for instance '
                      'a "Macro" is also a "Leaf"')

        self.setInput('static',
                      type=bool,
                      named=True,
                      default=False,
                      description='List only static (built-in) commands')

        self.setInput('dynamic',
                      type=bool,
                      named=True,
                      default=False,
                      description='List only dynamic commands')

        self.setInput('all',
                      type=bool,
                      named=True,
                      default=False,
                      description='List all subcommands, even hidden ones.')


    def getCommands (self, branch, commandType, allCommands, uniqueOnly, static, dynamic, mask=None):
        commandList   = []

        staticOnly  = static and not dynamic
        dynamicOnly = dynamic and not static

        for name in branch.listChildren():
            child     = branch.getChild(name, incarnate=False)
            hidden    = child.hidden
            dolist    = True

            if hidden and not allCommands:
                dolist = False

            elif not child.istype(commandType):
                dolist = False

            elif dynamicOnly and not child.istype(Dynamic):
                dolist = False

            elif staticOnly and child.istype(Dynamic):
                dolist = False

            elif mask and not fnmatchcase(name.lower(), mask.lower()):
                dolist = False

            if dolist:
                commandList.append((name, child))

        return commandList


    def listCommands (self, branch, commandType, allCommands, unique, static, dynamic, mask=None):
        commands = self.getCommands(branch, commandType, allCommands, unique, static, dynamic, mask)
        maxlen   = max([len(name) for name, obj in commands] + [20])
        return [ '%-*s: %s'%(maxlen, name, obj.getTypeName()) for name, obj in commands ]


    def describeCommand (self, session, branch, command):
        child = branch.getChild(command)
        if child.istype(Leaf):
            session.checkAccess(child.requiredAccess)
        return child.getDocumentation(4, 80)



class HELP_Query (_HelpLeaf):
    '''
    If a command is supplied, usage information for that subcommand
    (or help topic) is given.  Otherwise, available subcommands
    within this branch are listed.

Examples:
    # List all commands at the top level:
        HELP?

    # List commands that only appear at the top level:
        HELP? -unique

    # List all commands within the "LOGGer" branch:
        LOGGer:HELP?

    # List commands that are unique to the "LOGGer" branch:
        LOGGer:HELP? -unique

    # Give information about the "LOGGer" branch:
        HELP? LOGGer

    # Give information about the "LOGGer:ADD" command:
        LOGGer:HELP? ADD
    '''


    def declareInputs (self):
        _HelpLeaf.declareInputs(self)
        self.setInput('command',
                      type=str,
                      default='',
                      description='Command for which you want help.')

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('text', type=list,
                       description='Human readable text')


    def run (self, _session, type=None, all=False, unique=False, static=False, dynamic=False, command=str):
        if not command:
            output = self.listCommands(self.parent, type, all, unique, static, dynamic, command)
        else:
            output = self.describeCommand(_session, self.parent, command)
        return (output,)



class _Enumerate (Observing, _HelpLeaf):
    '''Enumerate commands in the current branch/scope'''

    def declareInputs (self):
        _HelpLeaf.declareInputs(self)
        self.setInput('branchSuffix', type=str, default=':', named=True)


    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('command', type=str, repeats=(1, None))


    def run (self, type=None, all=False, unique=False, static=False, dynamic=False, branchSuffix=":", mask=''):
        commands = self.getCommands(self.parent, type, all, unique, static, dynamic, mask)
        commands.sort()
        return tuple([(name+branchSuffix if isinstance(obj, Branch) else name)
                      for (name, obj) in commands])


class _List (Observing, _HelpLeaf):
    '''List commands in the current branch/scope'''

    def declareOutputs (self):
        Leaf.declareOutputs (self)
        self.addOutput('commands', type=list)

    def run (self, type=None, all=False, unique=False, static=False, dynamic=False, mask=''):
        commands = self.listCommands(self.parent, type, all, unique, static, dynamic, mask)
        return (commands,)

    def listCommands (self, branch, commandType, allCommands, unique, static, dynamic, mask=None):
        commands = self.getCommands(branch, commandType, allCommands, unique, static, dynamic, mask)
        lines = []
        for name, obj in commands:
            isbranch = obj.istype(Branch)
            isdynamic = obj.istype(Dynamic)

            props = [ ("type", obj.getTypeName()),
                      ("branch", isbranch),
                      ("dynamic", isdynamic) ]

            lines.append('"%s" %s'%(name, " ".join(["-%s=%s"%item for item in props])))
        return lines




class _Query (_HelpLeaf):
    '''Get information about the specified command'''

    class NoSuchProperty (RunError):
        '''Command %(command)r does not have a %(property)r property'''

    def declareInputs (self):
        Leaf.declareInputs(self)
        self.setInput('properties', type=str, repeats=(0, None))

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('value', type=tuple, repeats=(0, None))


    def run (self, _session, ignoreMissing=False, command=str, *properties):
        child = self.parent.getChild(command, allowMissing=ignoreMissing)

        if not child:
            _session.checkAccess(OBSERVER)
            outputs = []

        else:
            if child.istype(Leaf):
                _session.checkAccess(child.requiredAccess)
            props = [ ("branch", child.istype(Branch)) ]
            props.extend(child.getProperties())

            if not properties:
                outputs = props

            else:
                propmap = dict([ (p.lower(), v) for (p, v) in props ])
                outputs = []
                for p in properties:
                    try:
                        outputs.append((None, propmap[p.lower()]))
                    except KeyError:
                        if not ignoreMissing:
                            raise self.NoSuchProperty(command=child.name, property=p)
                        outputs.append("")

        return tuple(outputs)



class _Exists (Observing, _HelpLeaf):
    '''Return True if the specified command exists, False otherwise.'''


    def declareInputs (self):
        Leaf.declareInputs(self)

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('exists', type=bool)

    def run (self, command=str):
        c = self.parent.getChild(command, allowMissing=True, incarnate=False)
        return bool(c)
