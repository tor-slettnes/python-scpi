#===============================================================================
## @file base.py
## @brief Abstract command element; superclass of Base and Leaf.
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .parameter           import Missing
from ..exceptions         import CommandError
from ..sessions.symbols   import OBSERVER, CONTROLLER, SYNC, ASYNC
from ...tools.publication import publish, info, TRACE, DEBUG, INFO, NOTICE, WARNING, ERROR
from ...tools.config      import Config
from ...tools.parser      import QUOTE_ATTRIBUTES

## Standard Python modules
import re, weakref

### Regular expression for extracting "short" version of command name
prefixMap = {
    'Common' : '*',
}

suffixMap = {
    'Set'       : '=',
    'Add'       : '+',
    'Remove'    : '-',
    'Clear'     : '~',
    'Query'     : '?',
    'Count'     : '#',
    'Enumerate' : '*',
    'List'      : '@',
    'Exists'    : '!',
    'Load'      : '<',
    'Save'      : '>',
}

prefixRevMap = dict(list(zip(list(prefixMap.values()), list(prefixMap.keys()))))
suffixRevMap = dict(list(zip(list(suffixMap.values()), list(suffixMap.keys()))))
querySuffixes = ('?', '#', '*', '@', '!')
_lowerCaseX  = re.compile(r'[a-z]')
#_interCaseX  = re.compile(r'[a-z]+([^a-z%s])'%''.join([re.escape(c) for c in suffixRevMap]))
_interCaseX  = re.compile(r'[a-z]+([^a-z])')

### Mix-in class for commands that should not show up in HELP? output.
class Hidden (object):
    hidden       = True


### Base class for all command types (Branch, Leaf, Macro)
class Base (object):
    hidden         = False
    shutdownHook   = []
    globalData     = {}

    def __init__ (self, name, parent, defaults=None):
        self.name         = name
        self.description  = self.__class__.__doc__
        self.defaults     = defaults or {}
        self.aliasrefs    = set()
        if parent:
            self._parentref = weakref.ref(parent)


    #===========================================================================
    ### Property functions for access to <instance>.parent

    _parentref = None

    @property
    def parent (self):
        if self._parentref:
            return self._parentref()

    @property
    def super (self):
        return super(self.__class__, self)


    #===========================================================================
    ### Method for translating class names to SCPI commands


    _prefixX = re.compile('^(%s)_'%'|'.join(list(prefixMap.keys())))
    _suffixX = re.compile('_(%s)$'%'|'.join(list(suffixMap.keys())))

    @classmethod
    def scpiName (cls, ident=None):
        if not ident:
            ident = cls.__name__

        name = ident
        if match := cls._suffixX.search(name):
            try:
                suffix = suffixMap[match.group(1)]
            except KeyError:
                assert False, "Invalid command class %r suffix %r"%(ident, match.group(1))
            else:
                name = name[:match.start()] + suffix

        if match := cls._prefixX.search(name):
            try:
                prefix = prefixMap[match.group(1)]
            except KeyError:
                assert False, "Invalid command class %r prefix %r"%(ident, match.group(1))
            else:
                name = prefix + name[match.end():]

        return name


    @classmethod
    def alternateNames (cls, name):
        shortname = _lowerCaseX.sub('', name)
        intername = _interCaseX.sub(r'\1', name)
        names     = (name, intername, shortname)

        if not names[-1]:
            raise cls.NoUpperCaseLetters(name=names[0])

        return names

    @classmethod
    def className (cls, command):
        name = command
        try:
            suffix = suffixRevMap[name[-1]]
        except (IndexError, TypeError):
            pass
        else:
            name = '_'.join((name[:-1], suffix))

        try:
            prefix = prefixRevMap[name[0]]
        except (IndexError, TypeError):
            pass
        else:
            name = '_'.join((prefix, name[1:]))

        return name


    def getCommandClass (self, obj):
        if isinstance(obj, type):
            return obj
        else:
            return obj.__class__


    def defaultAccess (self, subcommand=None):
        path = self.commandPath(subcommand)
        return (CONTROLLER, OBSERVER)[path[-1:] in querySuffixes]


    class ConflictingOptions (CommandError):
        '''Conflicting command options: %(options)s'''

    def checkConflictingOptions (self, **options):
        provided = [ key for (key, value) in list(options.items()) if value ]
        if len(provided) > 1:
            raise self.ConflictingOptions(options=",".join(provided))




    #===========================================================================
    ### The following functions are used to support HELP?/XMLHelp?

    def getDocumentation (self, margin=0, columns=0, defaults=None):
        doc     = []
        props   = self.listProperties(margin, columns)
        syntax  = self.getSyntax(margin, columns, defaults=defaults)
        desc    = self.getDescription(margin, not columns)

        for section, lines in (('Properties:',   props),
                               ('Usage:',        syntax),
                               ('Description:',  desc)):
            if lines:
                if doc:
                    doc.append('')
                doc.append(section)
                doc.extend(lines)

        return doc


    def listProperties (self, margin, columns):
        proplist = self.getProperties()
        maxlen   = max([ len(prop) for (prop, value) in proplist ])
        proptext = []
        return [ '%*s%-*s: %s'%(margin, '', maxlen, prop, value)
                 for prop, value in proplist ]


    def getProperties (self):
        props = []

        props.append(('PrimaryName', self.name))
#        for name in self.names[1:]:
#            props.append(('AlternateName', name))

        props.append(('FullCommand', ':'+self.commandPath(short=False)))
        props.append(('ShortCommand', ':'+self.commandPath(short=True)))

        props.append(('Type',  self.getTypeName()))
        return props


    indentX = re.compile(r'^( +)\S+', re.MULTILINE)

    def getDescription (self, margin, unwrap=False, doc=None):
        if doc or self.description:
            text  = (doc or self.description or '').expandtabs()


            ### 'De-dent' the document string
            match  = self.indentX.search(text)
            indent = match and match.group(1) or ''
            text   = '%s%s'%(indent, text.strip())
            adjust = margin - len(indent)

            if unwrap:
                text = re.compile(r'( +\S*)\n%s(\S)'%indent).sub(r'\1 \2', text)
                text = re.compile(r'\n\s*\n').sub(r'\n', text)

            lines = text.splitlines()

            if adjust < 0:
                for idx, line in enumerate(lines):
                    if line[:-adjust].isspace():
                        lines[idx] = line[-adjust:]

            elif adjust > 0:
                fill = ''.ljust(adjust)
                for idx, line in enumerate(lines):
                    if line.startswith(' ') or not indent:
                        lines[idx] = fill + line

            return lines


    def getSyntax (self, margin, columns, defaults=None):
        return [ '%*s%s'%(margin, '', self.name) ]


    #===========================================================================
    ### Description of command type; overwritable in subclasses

    @classmethod
    def getTypeName (cls):
        return cls.TypeName

    @classmethod
    def istype (cls, type):
        return issubclass(cls, type)

    @classmethod
    def type (cls):
        return cls

    #===========================================================================
    ### The following are used to map this object to a command.

    def path (self, scope=None):
        elements = []
        obj = self
        while obj is not scope and obj.parent:
            elements.insert(0, obj)
            last = obj
            obj  = obj.parent

        return tuple(elements)


    _shortslice = {
        None  : slice(None, -1),
        False : slice(None, 0),
        True  : slice(None, None)
    }

    def commandPath (self, child=None, scope=None, delimiter=':', short=None):
        names = [ obj.name for obj in self.path(scope) ]
        slc   = self._shortslice[short]
        names[slc] = [ _lowerCaseX.sub('', name) for name in names[slc] ]

        if child is not None:
            names.append(child)

        return delimiter.join(names)


    def getDefaults (self, scope=None):
        defaults = {}

        for element in self.path(scope):
            defaults.update(element.defaults)

        return defaults



    #===========================================================================
    ### Logging and Debugging

    def log (self, topic, message):
        publish(topic, message, level=level)

    def trace (self, message):
        self.log(TRACE, message)

    def debug (self, message):
        self.log(DEBUG, message)

    def info (self, message):
        self.log(INFO, message)

    def notice (self, message):
        self.log(NOTICE, message)

    def warning (self, message):
        self.log(WARNING, message)

    def error (self, message):
        self.log(ERROR, message)


    #===========================================================================
    ### Virtual methods

    def getInputs (self):
        return []

    def getOutputs (self):
        return []


    #===========================================================================
    ### The following are used to manage server startup/shutdown

    def addShutDownAction (self, method, args=(), kwargs={}, early=False):
        if early:
            self.shutdownHook.insert(0, (method, args, kwargs))
        else:
            self.shutdownHook.append((method, args, kwargs))



commandTypes = { None: Base }
def addCommandType (cls):
    commandTypes[cls.__name__] = cls
