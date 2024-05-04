#===============================================================================
## @file macro.py
## @brief Macro support
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base import Base, addCommandType
from .leaf import Leaf, Asynchronous, Singleton, \
    Controlling, Observing, Public, FULL, CommandWrapper
from .parameter import Missing, ArgTuple, autoType
from .dynamic_base import Dynamic, DynamicCommandLeaf
from ..exceptions import CommandError, RunError
from ..sessions.macro_session import MacroSession
from ..sessions.symbols import AccessLevels, \
    OBSERVER, CONTROLLER, SYNC, ASYNC, RAISE
from ...tools.parser import parser, CookedValue, \
    QUOTE_NEVER, QUOTE_ALWAYS, QUOTE_AUTO
from ...tools.publication import warning, info, debug


class Macro (Dynamic, CommandWrapper, Leaf):
    'This is an undocumented macro.'

    class RepeatSuffixBeforeLast (CommandError):
        "Macro argument %(arg)r cannot come after repeated %(type)s argument %(previous)r"

    class MissingArgumentName (CommandError):
        'Missing argument name'

    TypeName = 'macro'
    requiredAccess = FULL

    def __init__ (self, *args, **kwargs):
        Leaf.__init__(self, *args, **kwargs)


    def declareInputs (self):
        self.startInputs()
        self.addInput('_session')
        self.addInput('_context')
        self.addInput('_command')


    def declareMacroInputs (self):
        optionals = []
        repeated  = [None, None]
        repeatSuffix = {"*":(0, None), "+":(1, None)}

        for arg in self.arguments:
            try:
                name, value = arg.split('=', 1)
                default = (name, value, arg)
            except ValueError:
                name, default = arg, Missing

            suffix = name[-1:]
            try:
                repeats = repeatSuffix[suffix]
            except KeyError:
                repeats = None
                named   = False
                if not name.strip("$@"):
                    raise self.MissingArgumentName()
            else:
                named = (name[-2:] == suffix*2)
                if not name[:1] in ("$@"):
                    name = name.rstrip(suffix)

            if repeats or default is Missing:
                ### If this is a required argument, all prior
                ### optional arguments automatically become 'named'
                while optionals:
                    self.setInput(optionals.pop(), named=True)

            else:
                ### Keep track of this optional argument, in case we later
                ### need to convert it to a 'named' argument as well.
                optionals.append(name)


            #form = (str, basestring)[name.startswith('@')]
            if repeated[named]:
                raise self.RepeatSuffixBeforeLast(arg=name, previous=repeated[named].name,
                                                  type=('positional', 'named')[named])

            argtype = (tuple,str)[named]
            param = self.addInput(name, type=argtype, form=None, named=named, default=default, repeats=repeats)
            if repeats:
                repeated[named] = param

        self.varParam, self.varOptParam = repeated



    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('reply', type=tuple, repeats=(0, None))

    def substituteArgs (self, args, kwargs, text=None):
        if text is None:
            text = self.text or ""

        variables = {}
        varindex  = None

        for index, param in enumerate(self.getInputs()):

            if not param.repeats:
                name, value, raw = args[index]

                if name is not None and value is None:
                    value = str(True)

            else:
                if varindex is None:
                    varindex = index

                if param.name[0] == '@':
                    value = parser.collapseArgs(args[varindex:], tag='argument')

                elif param.name[0] == '$':
                    value = ' '.join([ value for (opt, value, raw) in args[varindex:] ])

                elif param.named:
                    ## Named variable inputs
                    value = dict([(k,v) for (k,v,r) in args[varindex:] if k])
                    value.update(kwargs)

                elif self.varOptParam:
                    ## Positional variable inputs, in a macro that also takes named variable inputs
                    value = [v for (k,v,r) in args[varindex:] if not k]

                else:
                    ## Since this macro does not take named variable inputs, pass on the arguments
                    ## including initial option name ("[-option[=]][value]").
                    value = parser.collapseParts(args[varindex:], tag=None, quoting=QUOTE_NEVER)

            if param.name[0] in '$@':
                text = text.replace(param.name, value)
            else:
                variables[param.name] = value

        return text, variables

    def run (self, _session, _context, _command, *args, **kwargs):
        text, parameters = self.substituteArgs(args, kwargs)
        return self.runMacro(_session, _context, _command,
                             text=text,
                             scope=self.parent,
                             parameters=parameters)


    def runMacro (self, _session, _context, _command, text, scope, parameters):
        session = MacroSession(input=text, parent=_session, access=self.access, 
                               description='macro %r'%_command)
        context = _context.clone(data=parameters, scope=scope)
        return session.handleInput(text, context, nextReply=self.onNext)

    def getSyntax (self, margin, columns, defaults=None):
        syntax      = Base.getSyntax(self, margin, columns, defaults=defaults)
        stxmargin   = len(syntax[-1]) + 1

        for param in self.getInputs():
            self.wrapText(syntax,
                          self.argSyntax(param, param.name.strip('$@+*'), defaults=defaults),
                          stxmargin,
                          columns)

        return syntax


    def argSyntax (self, param, name=None, defaults=None):
        if name is None:
            name = param.name

        if defaults is None:
            defaults = self.defaults

        named   = param.named or (name in self.defaults)
        default = defaults.get(name, param.default)

        if not default in (None, Missing):
            if isinstance(param.type, ArgTuple):
                default = default[CookedValue]

            if default:
                default = parser.protectString(default, tag='', quoting=QUOTE_AUTO)

        if named:
            if not default or default is Missing:
                value = name.join("<>")
            else:
                value = default

            if param.repeats:
                argsyntax = "-<%s>=%s"%(name, value)
            else:
                argsyntax = "-%s=%s"%(name, value)

        else:
            if not default or default is Missing:
                argsyntax = name.join("<>")
            else:
                argsyntax = "<%s=%s>"%(name, default)

        if param.repeats:
            rmin, rmax = param.repeatRange()
            if not rmin:
                default = None

        if default is not Missing:
            argsyntax = '[%s]'%(argsyntax,)

        if param.repeats:
            argsyntax += " ..."

        return argsyntax


    def getProperties (self):
        props = Leaf.getProperties(self)
        props.append(('Access',       AccessLevels[self.access]))
        props.append(('ModifyAccess', AccessLevels[self.modifyAccess]))
        return props


    def formatOutputs (self, outputs, alwaysNamed=False, raw=False):
        return outputs


class InlineMacro (Macro):
    def runMacro (self, _session, _context, _command, text, scope, parameters):
        _context.data.update(parameters)
        return _session.runBlock(text, _context, nextReply=self.onNext, catchReturn=True)


addCommandType(Macro)
