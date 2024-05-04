#===============================================================================
## @file branch.py
## @brief Implementation of a "Branch"
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base        import Base, addCommandType
from .leaf        import Leaf
from ..exceptions import Error, CommandError

## Standard Python modules
import re

#===============================================================================
## 'Branch' class definition.
##
## A branch is a subdivision of the command namespace, and functions
## mainly as a container for related subcommands.  It may represent
## a particular instrument subsystem, or a particular aspect of
## a subsystem.
##
## As an example, a 'LASer' branch may contain a 'POWer' subbranch,
## which in turn may contain a 'SETTing', 'SETTing?' and 'READing?'
## leafs:
##
##     LASer:POWer:SETTing 50
##     LASer:POWer:SETTing?
##     LASer:POWer:READing?
##
##
## The role a Branch() subclass object is mainly to delegate subcommands
## to a nested Branch(), Leaf(), or Macro() object.
##
## To define the commands above, the following syntax can be used:
##
##     class LASer (Branch):
##         'Laser subsystem'
##
##         class POWer (Branch):
##             'Laser power control functions'
##
##             class SETTing (Leaf):
##                 'Set the laser power to the specified wattage'
##                 ...
##
##
## Three forms of the class name are added to the command namespace,
## within the containing branch:
##     - The full name of the class
##     - A partially abbreviated version of the class name,
##       where intermediate lowercase letters have been stripped
##       away (but trailing lowercase letters are kept intact)
##     - A fully abbreviated version of the class name, where
##       all lowercase letters have been stripped away.
##
##
## Most branch implementations shuld not be directly sublassed from
## 'Branch', but rather derived from 'FullBranch'.  The latter
## offers a set of predefined children that are normally expected
## within any branch, such as 'HELP?', 'WAIT', 'SUBScription+', etc.

class Branch (Base):
    commandSplitX  = re.compile(r'^:?([^:]*)(:?.*)')
    TypeName       = 'branch'

    class UnknownCommand (CommandError):
        '%(command)s <-- Unknown Command'

    class DelegationRequired (CommandError):
        '%(command)s <-- This command requires a subcommand'

    class NoUpperCaseLetters (CommandError):
        'The name %(name)r has no uppercase letters, as required for the short form'

    class IncorrectType (CommandError):
        '%(foundName)r is a(n) %(foundType)s, not a(n) %(searchType)s'

    __slots__ = ()

    def __init__ (self, *args, **argmap):
        Base.__init__(self, *args, **argmap)
        Branch.init(self)

    def init (self):
        self.children        = {}   # Instantiated children within this scope
        self.childclasses    = {}   # Uninstantiated children within this scope
        self.debugTopic      = self.commandPath(short=True)
        self.addDefaultChildren()

    def addDefaultChildren (self):
#        self.debug('Creating command list for %r'%(self.commandPath()))
#        self.addChild(self, name='.')

        for name in dir(self.__class__):
            cls = getattr(self.__class__, name)
            if isinstance(cls, type) and issubclass(cls, Base):
                command  = cls.scpiName(name)
                if not command.startswith("_"):
                    altnames = cls.alternateNames(command)
                    for n in altnames:
                        self.childclasses[n.lower()] = (cls, altnames, None)

    @property
    def branchData (self):
        try:
            dicts = self._branchData
        except AttributeError as e:
            dicts = self._branchData = {}
        return dicts


    #===========================================================================
    ### The following are used to handle the SCPI command tree


    def addChild (self, obj, name=None, altnames=()):
        if name is None and obj.istype(Base):
            name = obj.name

        if not altnames:
            altnames = self.alternateNames(name)

        instance = (obj, altnames)

        for n in altnames:
            self.children[n.lower()] = instance

        return obj



    def delChild (self, obj):
        refs = 0
        for name, ref in list(self.children.items()):
            child, names = ref
            if child is obj:
                del self.children[name]
                refs += 1

        aliases = 0
        for aliasref in obj.aliasrefs:
            alias = aliasref()
            if alias:
                alias.parent.delChild(alias)
                aliases += 1

        self.debug("Deleted %d child reference(s) and %d alias(es) to %s"%
                   (refs, aliases, self.commandPath(obj.name)))

        if obj:
            del obj


    def getChild (self, name, allowMissing=False, onlyInstances=False, incarnate=True):
        key = name.lower().rstrip(":")

        try:
            obj, names = child = self.children[key]
            return obj

        except KeyError:
            if name == '.':
                return self

            elif name == '..':
                return self.parent or self

            if not onlyInstances:
                try:
                    cls, names, defaults = self.childclasses[key]

                except KeyError:
                    pass

                else:
                    if incarnate:
                        obj = cls(name=names[0], parent=self, defaults=defaults)
                        return self.addChild(obj, name=names[0], altnames=names)
                    else:
                        return cls

            if not allowMissing:
                raise self.UnknownCommand(branch=self.commandPath() or None, command=name)



    def getPrimaryChildName (self, name):
        key = name.lower()

        try:
            obj, names = self.children[key]
            return names[0]

        except KeyError as e:
            try:
                cls, names, defaults = self.childclasses[key]
                return names[0]

            except KeyError as e:
                return None


    def listChildren (self, commandType=Base):
        instanceNames = [ names[0]
                          for (child, names) in self.children.values()
                          if child.istype(commandType) ]

        classNames    =  [ names[0]
                           for (child, names, defaults) in self.childclasses.values()
                           if child.istype(commandType) ]

        return sorted(set(instanceNames + classNames))


    def hasChild (self, name):
        return name.lower() in self.children or name.lower() in self.childclasses





    #===========================================================================
    ### Command delegation and invocation


    def find (self, command, commandType=None):
        path, defaults = self.locate(command)
        obj = path[-1]
        if commandType and not isinstance(obj, commandType):
            raise self.IncorrectType(foundName=obj.name, foundType=obj.getTypeName(),
                                     searchType=commandType.getTypeName())
        return obj


    def locate (self, command):
        elements  = command.split(":")
        start     = self
        _defaults = {}

        if elements and not elements[0]:
            ### if command starts with ":", then begin at the top of the SCPI tree.
            while start.parent:
                start = start.parent

            del elements[0]

        if elements and not elements[-1]:
            del elements[-1]

        _path     = [start]
        _defaults.update(start.defaults)

        if elements and elements[0]:
            start._locate(elements, _path, _defaults)

        return _path, _defaults


    def _locate (self, elements, path, defaults):
        name  = elements[0]

        try:
            child = self.getChild(name)

        except self.UnknownCommand:
            raise self.UnknownCommand(branch=self.commandPath() or None,
                                      command=self.commandPath(name, scope=path[0]))

        else:
            path.append(child)
            defaults.update(child.defaults)
            elements.pop(0)

            if elements:
                child._locate(elements, path, defaults)

    def invoke (self, _command, *args, **kwargs):
        raise self.DelegationRequired(command=_command)

    def estimate (self, _command, *args, **opts):
        raise self.DelegationRequired(command=_command)


    #===========================================================================
    ### Invocation syntax

    def getSyntax (self, margin, columns, defaults=None):
        return [ '%*s%s'%(margin, '', ':'.join((self.name, '<subcommand>'))) ]


addCommandType(Branch)
### Mapping of branch types (names:classes) that can be created using
### the BRANch+ command
branchTypes = {}
