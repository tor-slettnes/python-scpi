#===============================================================================
## @file scpiLeaf.py
## @brief Leaf classes: Leaf(), AsynchLeaf()
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## A leaf is the last and operative element of a command.
## There is no further delegation at this point.
##
## As such, this class is responsible for defining and parsing
## any arguments supplied, and to perform the intended operation.
##
## ==========
## INVOCATION
## ==========
##
## Leaf implementations derived from this superclass should
## normally override the 'run()' method to do the actual work.
##
## Additionally, classes may override 'prerun()' and/or 'postrun()'
## to perform preparation/cleanup tasks.  If 'prerun()' succeeds,
## the 'run()' invocation is guaranteed to be succeeded by a
## call 'postrun()', regardless of any exceptions raised from 'run()'.
## This can be used to, for instance, release any locks acquired
## during prerun.  Both 'prerun()' and 'postrun()' are invoked
## with the same parameters as run(); see below.
##
## For instance, to implement the 'LASer:POWer:SETTing' command,
## the following syntax can be used within the 'SETTing' leaf:
##
##     class SETTing (Leaf):
##         'Set the laser power output to the specified value.'
##
##         def run (self, wattage=float):
##             ...
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
## In addition, if the class name ends with '_Add', '_Remove' or '_Query',
## that portion is replaced with '+', '-', or '?', respectively, in the
## command namespace.   For instance, to create a 'HELP?' leaf, you would
## use:
##
##     class HELP_Query (Leaf):
##         ...
##
##
##
## ======================
## PARAMETER DECLARATIONS
## ======================
##
## Each leaf class takes zero or more inputs on the command line, and
## responds with zero or more outputs.  Both input and output
## parameters need to be declared.
##
##
## Implicit input parameter declarations
## -------------------------------------
##
##     Command arguments are determined implicitly from the argument
##     list of the 'run()' method.  For instance, the following Leaf
##     will accept a single argument, 'topic':
##
##         class SUBScribe (Leaf):
##             'Subscribe to a given topic'
##
##             def run (self, topic=str):
##                    ...
##
##     Optional arguments are incicated by supplying a default value
##     for the argument, using standard Python language conventions:
##
##         def run (self, wattage=0.0):
##             ...
##
##     Moreover, any default value further indicates the data type of
##     the argument.  Before the run() method is called, the supplied
##     command argument is converted to the same type as this default
##     value (in this case, a floating point number).
##
##     To indicate a data type without setting a default value (for a
##     REQUIRED argument), the initial value should be set to either:
##
##       - a 'type' object (int, float, str...), as listed in the
##         'typeMap' dictionary near the bottom of scpiParameter
##       - a tuple where the elements are enumerated words (the index
##         of the word passed as argument gets passed to the run()
##         method)
##       - a dictionary, where the keys are alternate command arguments,
##         and the values are what gets passed onto the run() method.
##
##     For example:
##
##         def run (self, wattage=float):
##             ...
##
##     In this case, the argument must be supplied to the command:
##
##         LASer:POWer:SETTing 50.0
##
##
##     Any OPTIONAL parameter that appears before a REQUIRED
##     parameter automatically becomes 'named'.  For example:
##
##         def run (self, explanation='', wattage=float):
##
##     Here, 'explanation' can only be supplied as a named argument;
##     any 'positional' (a.k.a. 'unnamed') argument will be mapped to
##     the subsequent REQUIRED parameter:
##
##         LASer:POWer:SETTing -explanation='Setting laser output' 50.0
##
##
##     If the argument list contains a variable argument (*arg), then
##     this will "swallow" all remaining arguments provided to the
##     command (an infinite repeat count).  For instance,
##     "PUBLish.run()" may look like:
##
##         def run (self, topic=str, *message):
##
##     A select set of internal arguments be passed to the "run()'
##     method in by simply including them in the argument list:
##
##         def run (self, _session, name=str, command=str):
##             ...
##
##     Here, '_session' is one of the arguments that was supplied
##     internally, whereas 'name' and 'command' are supplied in the
##     command received by the client.  Some internal arguments are
##     made available upon each invocation (see the _run() method in
##     'scpiSession.py'), others are stored as a "argument map" in
##     the "subcommands" list in the parent branch, along with a
##     reference to this leaf and its names.
##
##
## Explicit input argument declarations
## ------------------------------------
##
##     Additional attributes for arguments can be supplied by
##     invoking the 'setInput()' method.  This should normally be
##     done in the 'declareInputs()' routine, which is invoked at
##     at initialization.
##
##     Remember to call Leaf.declareInputs() first (to perform the
##     neccessary "addInput()" calls based on the arguments of the
##     run() method, as described above).
##
##         class SETTing (Leaf):
##             'Set the laser power output to the specified value'
##
##             def declareInputs (self):
##                 Leaf.declareInputs(self)
##
##                 self.setInput('wattage',
##                               type=float,
##                               named=False,
##                               range=(0.0, 50.0),
##                               units='milliWatts',
##                               description='Laser power output',
##                               repeats=None)
##
##             def run (self, wattage):
##                 ...
##
##     Note that the first argument to setInput() must be the name
##     of an existing argument to the run() method.
##
##     Arguments can be 'named' or 'unnamed' (positional).  Upon
##     invocation, a 'named' argument must be supplied in the format
##     '-name=value', as follows:
##
##         LASer:POWer:SETTing -wattage=50.0
##
##
## Output declarations
## -------------------
##
##     Return values from the command must also be declared.
##     This should normally be done in the 'declareOutputs()'
##     method, by invoking 'addOutput()'.
##     ### FIXME: Add output parameter documentation ###
##
##
## =====================
## ASYNCHRONOUS COMMANDS
## =====================
##
## There are two mix-in classes can be used to execute portions of a command
## in the background:
##   - The 'Background' mix-in class adds a 'next()' method, which is invoked
##     in a new thread once 'run()' completes.  If 'run()' returns a tuple,
##     its elements are passed in as separate input arguments to 'next()',
##     otherwise its return value is passed in as a single argument.
##
##   - The 'Asynchronous' mix-in class first invokes the 'prerun()' method
##     synchronusly (i.e. blocking), then invokes 'run()' asynchronously in
##     a new thread. 'prerun()' receives the same input arguments as 'run()'.
##
##     The 'Asynchronous' mix-in class is supplied for legacy reasons;
##     new Leaf implementations should normally use 'Background' instead.
##
## 'BackgroundLeaf' and 'AsynchLeaf' are provided as proper multiple-inherited
## subclasses  of 'Leaf' and each of the above.


## Modules relative to install path
from .base import Base, addCommandType
from .parameter import Parameter, Missing, Bool, Enum, ArgTuple
from ..exceptions import NextReply, Error, CommandError, RunError, SessionControl
from ..sessions.symbols import AccessLevels, SYNC, ASYNC, \
    GUEST, OBSERVER, CONTROLLER, ADMINISTRATOR, FULL
from ...tools.parser import parser
from ...tools.publication import warning, debug, info

## Standard Python modues
from inspect import getfullargspec
from threading import Lock, currentThread
from io import StringIO

SYNCHRONOUS, ASYNCHRONOUS = ("synchronous", "asynchronous")

#===============================================================================
## Access definitions.
##
## These are mix-in classes that cause a command to become more or
## less 'restricted', i.e. requiring higher or lower levels of access.
## Unless overridden in subclasses, a default "Leaf" requires OBSERVER
## access.

class Public (object):
    requiredAccess = GUEST

class Observing (object):
    requiredAccess = OBSERVER

class Controlling (object):
    requiredAccess = CONTROLLER

class Administrative (object):
    requiredAccess = ADMINISTRATOR

class Restricted (object):
    requiredAccess = FULL


class Leaf (Base):
    asynchronous       = False
    requiredAccess     = None
    inputList          = None
    outputList         = None
    hooks              = {}
    TypeName           = 'leaf'

    __slots__ = ()

    class NoFurtherDelegation (CommandError):
        '%(command)s <-- This command does not have any subcommands'

    def __init__ (self, *args, **kwargs):
        Base.__init__(self, *args, **kwargs)
        Leaf.init(self, *args, **kwargs)
        if self.requiredAccess is None:
            self.requiredAccess = self.defaultAccess()

    def init (self, *args, **kwargs):
        self.declareInputs()
        self.declareOutputs()
        self.debugTopic      = self.parent.debugTopic


    #===========================================================================
    ## Methods to create and access input parameter definitions

    def declareInputs (self):
        self.startInputs()
        self.addImplicitParameters(self.run)

    def startInputs (self):
        self.clearInputs()
        self.addDefaultInputs()

    def clearInputs (self):
        self.inputList   = []
        self.inputMap    = {}
        self.varParam    = None
        self.varOptParam = None

    def addDefaultInputs (self):
        pass

    def getDefaultInputs (self):
        return [ p for p in list(self.inputMap.values()) if not p in self.inputList ]

    def addImplicitParameters (self, runmethod):
        ### Get a list of arguments expected by the run() method.
        spec = getfullargspec(runmethod)
        optionalList = []

        for index in range(1-len(spec.args), 0):
            argname = spec.args[index]
            pname = argname.rstrip("_")
            param = self.addInput(pname,
                                  type = spec.annotations.get(argname, Missing))

            try:
                initial = spec.defaults[index]
            except (IndexError, TypeError):
                pass
            else:
                param.setInitial(initial)

            if param.default is Missing:
                while optionalList:
                    ### If this is a required argument, preceding
                    ### optional arguments automatically become 'named'
                    self.setInput(optionalList.pop(), named=True)
            else:
                ### If this is an optional argument, add it to a list
                ### of optional positional arguments that may later
                ### need to be converted to 'named'.
                optionalList.append(pname)

        for argname in spec.kwonlyargs:
            pname = argname.rstrip("_")
            param = self.addInput(pname,
                                  type = spec.annotations.get(argname, Missing),
                                  named = True)
            param.setInitial(spec.kwonlydefaults.get(argname, Missing))

        if spec.varargs:
            while optionalList:
                ### Treat "variable" arguments as positional, so preceding
                ### optional arguments automatically become 'named'
                self.setInput(optionalList.pop(), named=True)

            self.varParam = self.addInput(spec.varargs, type=str, repeats=(None, None))

        if spec.varkw:
            self.varOptParam = self.addInput(fVarKW, type=str, named=True, repeats=(None, None))


    def addInput (self, name, **propmap):
        param = self.createInput(name, **propmap)
        self.inputList.append(param)
        return param

    def insertInput (self, index, name, **propmap):
        param = self.createInput(name, **propmap)
        self.inputList.insert(index, param)
        return param

    def createInput (self, name, **propmap):
        basename = name and name.lower().strip('$')
        try:
            param = self.inputMap[basename]
        except KeyError:
            param = self.inputMap[basename] = Parameter(name, **propmap)
        else:
            param.update(**propmap)

        return param

    def removeInput (self, name, **propmap):
        basename = name.lower().strip('$')
        param    = self.inputMap.pop(basename)
        idx      = self.inputList.index(param)
        del self.inputList[idx]
        return idx

    def setInput (self, name, **propmap):
        self.getInput(name).update(**propmap)

    def setOptionalInput (self, name, **propmap):
        param = self.getInput(name, ignoreMissing=True)
        if param:
            param.update(**propmap)

    def getInput (self, name, ignoreMissing=False):
        basename = name.lower().strip('$')
        try:
            return self.inputMap[basename]
        except KeyError:
            if not ignoreMissing:
                raise

    def hasInput (self, name):
        basename = name.lower().strip('$')
        return basename in self.inputMap

    def getAllInputs (self):
        return self.inputList

    def getInputs (self):
        return [p for p in self.getAllInputs() if p.type]

    def getInputNames (self):
        return [p.name for p in self.getInputs()]


    #===========================================================================
    ### Methods to create and access output parameter definitions

    def declareOutputs (self):
        self.startOutputs()

    def startOutputs (self):
        self.clearOutputs()

    def clearOutputs (self):
        self.outputList = []
        self.outputMap  = {}


    def addOutput (self, name, **propmap):
        return self.insertOutput(len(self.outputList), name, **propmap)

    def insertOutput (self, index, name, **propmap):
        basename = name.lower().strip('$')
        param    = Parameter(name, **propmap)
        self.outputList.insert(index, param)
        self.outputMap[basename] = param
        return param

    def setOutput (self, name, **propmap):
        self.getOutput(name).update(**propmap)

    def getOutput (self, name, ignoreMissing=False):
        basename = name.lower().strip('$')
        try:
            return self.outputMap[basename]
        except KeyError:
            if not ignoreMissing:
                raise

    def getOutputs (self):
        return self.outputList

    def getOutputNames (self):
        return [p.name for p in self.getOutputs()]

    def removeOutput (self, name, ignoreMissing=False):
        basename = name.lower().strip('$')
        try:
            param    = self.outputMap.pop(basename)
            idx      = self.outputList.index(param)
        except (KeyError, ValueError) as e:
            if not ignoreMissing:
                raise
        else:
            del self.outputList[idx]
        return idx



    #===========================================================================
    ### Methods to process commands

    def _locate (self, elements, path, defaults):
        raise self.NoFurtherDelegation(command=self.commandPath('', scope=path[0]))


    def invoke (self, _session, _parts, **options):
        _session.checkAccess(self.requiredAccess)
        args, kwargs, argmap = self.parseInputs(_parts, _session=_session, **options)

        self.prerun(*args, **kwargs)
        try:
            result = self.execute(args, kwargs, argmap)

        except NextReply as e:
            raise NextReply(self, self.invokeNext, (args, kwargs) + e.args, {})

        except Exception:
            self.postrun(*args, **kwargs)
            raise

        else:
            self.postrun(*args, **kwargs)
            #currentThread().check()
            return result


    def execute (self, args, kwargs, argmap):
        return self.run(*args, **kwargs)


    def invokeNext (self,  commandArgs, commandOpts, leaf, method, nextArgs, nextOpts):
        try:
            reply = method(*nextArgs, **nextOpts)
            #currentThread().check()
            return reply

        finally:
            self.postrun(*commandArgs, **commandOpts)


    def prerun (self, *args, **kwargs):
        pass

    def run (self):
        raise NotImplemented('%s needs a run() method'%self.__class__.__name__)

    def postrun (self, *args, **kwargs):
        pass


    #===========================================================================
    ### Methods to handle command arguments

    class TooFewRepeats (CommandError):
        'Input parameter %(arg)r requires at least %(min)d %(argtype)s values; got %(actual)d.'

    class TooManyRepeats (CommandError):
        'Input parameter %(arg)r requires at most %(max)d %(argtype)s values; got %(actual)d.'

    class MissingArgument (CommandError):
        'The required argument %(arg)r is missing'

    def parseInputs (self, parts, externalOnly=False, args=(), **options):
        argmap = self.mapParts(parts, **options)
        args   = list(args)
        kwargs = {}

        if externalOnly:
            params = self.getInputs()
        else:
            params = self.getAllInputs()

        for param in params:
            if not param.repeats:
                args.append(argmap.get(param.name, param.default))

            elif not param.named:
                rmin, rmax = param.repeatRange()
                arg = argmap.get(param.name, [])

                if not arg and rmin is not None and rmin > 0:
                    args.append(Missing)

                elif rmin is not None and len(arg) < rmin:
                    raise self.TooFewRepeats(arg=param.name,
                                             argtype=param.type.description,
                                             min=rmin,
                                             actual=len(arg))

                elif rmax is not None and len(arg) > rmax:
                    raise self.TooManyRepeats(arg=param.name,
                                              argtype=param.type.description,
                                              max=rmax,
                                              actual=len(arg))
                else:
                    args.extend(arg)

            elif param.name in argmap:
                kwargs.update(argmap[param.name])


        if Missing in args:
            param = params[args.index(Missing)]
            e = self.MissingArgument(arg=param.name.strip('$'))
            assert param.type, 'In %s, command %s: %s'%(self.__class__.__name__, self.commandPath(), e)
            raise e
        return args, kwargs, argmap



    class ExtraArgument (CommandError):
        'Extra argument at end of command: %(arg)r'

    class NoSuchCommandOption (CommandError):
        'The command %(command)r takes no such option: %(option)r'


    def mapParts (self, parts, **defaults):
        posparams = [ p for p in self.getAllInputs()
                      if p.type and not p.named and not p.repeats and not p.name in defaults ]
        skipNamed = False

        mapped = defaults
        copies = {}

        for part in parts:
            option, value = part[:2]

            if option and not skipNamed:
                ### Supplied with an option name.  Map to the matching
                ### parameter; if it is a positional parameter, remove
                ### that from the list of expected positional parameters.
                try:
                    param = self.getInput(option)
                    if not param.repeats:
                        try:
                            posparams.remove(param)
                        except ValueError:
                            pass

                except KeyError:
                    if self.varOptParam:
                        param = self.varOptParam

                    elif self.varParam and isinstance(self.varParam.type, ArgTuple):
                        ### The last positional parameter repeats, and takes raw (uncooked)
                        ### inputs.  Map the option to the variable argument.
                        param = self.varParam

                    else:
                        raise self.NoSuchCommandOption(command=self.commandPath(), option=option)

            else:
                if posparams:
                    ### No option name; map to the next non-repeating positional parameter, if any.
                    param = posparams.pop(0)

                elif self.varParam:
                    ### There are no positional parameters left, but a repeating one.  Use that.
                    param = self.varParam

                    ### If this parameter repeats and takes raw (uncooked)
                    ### values, we pass in all arguments from this point
                    ### forward as variable arguments, rather than as options.
                    skipNamed = isinstance(self.varParam.type, ArgTuple)

                else:
                    raise self.ExtraArgument(arg=value)

            value = self.convertArg(param, part)

            if not param.repeats:
                mapped[param.name] = value

            elif param.named:
                try:
                    valuemap = copies[param.name]
                except KeyError:
                    try:
                        valuemap = copies[param.name] = defaults[param.name].copy()
                    except (KeyError, AttributeError):
                        valuemap = copies[param.name] = {}

                    mapped[param.name] = valuemap

                valuemap[option] = value

            else:
                try:
                    valuelist = copies[param.name]
                except KeyError:
                    try:
                        valuelist = copies[param.name] = defaults[param.name][:]
                    except (KeyError, TypeError):
                        valuelist = copies[param.name] = []

                    mapped[param.name] = valuelist

                valuelist.append(value)

        return mapped


    class InvalidArgument (CommandError):
        'In %(command)s argument %(arg)r: Expected %(expected)s, not %(provided)r'

    def convertArg (self, param, part):
        try:
            option, cooked, raw = part
        except ValueError as e:
            option, cooked = part
            raw = parser.collapsePart(part, tag=None)

        if param.form is str:
            option = None
            value  = raw

        elif param.form in (None, str):
            value = cooked

        elif param.form in (object, tuple):
            try:
                value = param.fromString(cooked)
                param.validate(value)
            except (ValueError, TypeError) as e:
                expected = param.type.formalDescription(range=param.range,
                                                        format=param.format)
                raise self.InvalidArgument(command=self.commandPath(),
                                           arg=param.name,
                                           expected=expected,
                                           provided=cooked or "")

        else:
            assert False, \
                'Unsupported part attribute in %s parameter %r: %r'%\
                (self.__class__.__name__, param.name, param.form)

        if param.form is tuple or isinstance(param.type, ArgTuple):
            return option, value, raw
        else:
            return value


    def formatOutputs (self, outputs, alwaysNamed=False, raw=False):
        arglist = []
        argmap  = {}

        if outputs is not None:
            if isinstance(outputs, tuple):
                arglist = list(outputs)
            elif isinstance(outputs, dict):
                argmap = dict(outputs)
                arglist = argmap.pop('*', [])
            else:
                arglist = [ outputs ]

        return self.extractParts(arglist, argmap, self.getOutputs(), alwaysNamed=alwaysNamed, raw=raw)


    def extractParts (self, arglist, argmap, params, partial=False, alwaysNamed=False, raw=False, addMissing=False):
        parts         = []

        for param in params:
            if argmap and not arglist:
                if param.repeats and isinstance(param.type, ArgTuple):
                    arglist = list(argmap.items())
                    argmap.clear()

                elif param.name in argmap:
                    arglist = [argmap.pop(param.name)]

                else:
                    arglist = []

            repeatMin, repeatMax = param.repeatRange()

            default = (param.default, None)[addMissing and param.default is Missing]

            if len(arglist) < (repeatMin or 0) and default is Missing:
                warning('Declared output %r is missing in %s reply'%
                        (param.name, self.__class__.__name__))


            for repeat in range(repeatMax or len(arglist)):
                if param.named or alwaysNamed or (param.form is tuple):
                    name = param.name
                else:
                    name = None

                try:
                    value = arglist.pop(0)

                except IndexError:
                    if partial or (repeat >= repeatMin):
                        break

                    value = default

                else:
                    if value is None and (alwaysNamed or not param.name):
                        value = default

                if isinstance(param.type, ArgTuple):
                    n, v = value[:2]
                    if n is not None:
                        name = n

                    if v is not None:
                        value = param.toString((n, v))
                    else:
                        value = None

                elif not raw and (value is not None):
                    try:
                        value = param.toString(value)
                    except ValueError as e:
                        raise Error('Command %r returned invalid value %r for %r: %s'%
                                    (self.commandPath(), value, param.name, e[0]))

                if value is not None:
                    parts.append((name, value))

        for arg in arglist:
            warning('Undeclared output in %s: %r'%
                    (self.__class__.__name__, arg))
            if raw:
                parts.append((None, arg))
            else:
                parts.append((None, str(arg)))

        return parts



    #===========================================================================
    ### Methods to provide documentation for this command

    def getSyntax (self, margin, columns, defaults=None):
        syntax       = [ '%*s%s'%(margin, '', self.name) ]
        stxmargin    = len(syntax[0]) + 1

        inputParams  = self.getDefaultInputs() + self.getInputs()
        outputParams = self.getOutputs()
#        errors       = self.getErrors()


        for param in inputParams:
            if not param.hidden:
                self.wrapText(syntax, self.argSyntax(param, defaults=defaults),
                              stxmargin, columns)

        if outputParams:
            syntax.append('')
            syntax.append('Reply:')
            syntax.append('')
            for param in outputParams:
                self.wrapText(syntax, self.argSyntax(param, defaults=defaults), margin, columns)


        lengths      = [len(param.name) for param in inputParams + outputParams]
        descmargin   = max(lengths or [0])
        descmargin  += margin + 5
        margins      = (margin, descmargin)

        if inputParams:
            inputs = self.paramDesc('Inputs:',  margins, columns, inputParams)
            syntax.extend(inputs)

        if outputParams:
            outputs = self.paramDesc('Outputs:', margins, columns, outputParams)
            syntax.extend(outputs)

#        if errors:
#            syntax.append('')
#            syntax.append('Errors:')
#            syntax.append('')
#            names = [ '[%s]'%eid for eid in errors ]
#            self.wrapText(syntax, ' '.join(names), margin, columns)

        return syntax



    def argSyntax (self, param, name=None, defaults=None):
        if name is None:
            name = param.name

        if defaults is None:
            defaults = self.defaults

        named   = param.named or (name in defaults)
        default = defaults.get(name, param.default)

        if named and isinstance(param.type, Bool) and default is False:
            argsyntax = '-%s'%(name,)

        elif named and param.repeats:
            argsyntax = '-<%s>=<value> ...'%(name,)
            default   = {}

        elif named:
            argsyntax = '-%s=<%s>'%(name, name)

        elif param.repeats:
            argsyntax  = '<%s> ...'%(name,)
            rmin, rmax = param.repeatRange()
            if not rmin:
                default = ()

        else:
            argsyntax = '<%s>'%(name,)


        if default is not Missing:
            argsyntax = '[%s]'%argsyntax


        return argsyntax



    def paramDesc (self, header, margins, columns, params, defaults={}):
        lines    = [ ]
        padding  = ''.ljust(margins[0])
        between  = (margins[1] - margins[0] - 3)

        for param in params:
            if not param.hidden:
                lines.append("%s%-*s ="%(padding, between, "<%s>"%param.name))

                self.wrapText(lines,
                              param.typeDescription(formal=True,
                                                    default=defaults.get(param.name)),
                              margins[1],
                              columns)

                if param.description:
                    lines.append('')
                    self.wrapText(lines, param.description, margins[1], columns)

        if lines:
            lines.insert(0, '')
            lines.insert(1, header)

        return lines


    def getProperties (self):
        props = Base.getProperties(self)
        props.append(('Asynchronous', repr(self.asynchronous)))
        props.append(('RequiredAccess', AccessLevels[self.requiredAccess]))

        return props



    def wrapText (self, lines, string, margin, columns):
        for word in string.split():
            if (columns and
                (len(lines[-1] + word) >= columns) and
                (len(lines[-1]) > margin)):
                lines.append('')

            lines[-1] = "%s %s"%(lines[-1].ljust(margin-1), word)


addCommandType(Leaf)


#===============================================================================
## 'Asynchronous' class definition.
##
## This is a mix-in class that can be used in asynchronous 'Leaf'
## classes (and subclasses, like 'Macro').  Once the command is
## invoked and any arguments are parsed, a 'NEXT' reply is issued
## back to the client, and the 'run()' method is invoked in a
## separate thread.  This allows further commands to be processed
## while this command is running.
##
## For instance, to create the asynchronous leaf 'COMMand', use:
##
##     class COMMand (Asynchronous, Leaf):
##         ...
##

class Asynchronous (object):
    asynchronous = True
    SYNCHRONOUS  = 'synchronous'

    def addDefaultInputs (self):
        Leaf.addDefaultInputs(self)
        self.createInput(self.SYNCHRONOUS, type=bool, named=True, default=False)

    def execute (self, args, kwargs, argmap):
        #currentThread().check()

        if argmap.get(self.SYNCHRONOUS, False):
            return self.run(*args, **kwargs)
        else:
            raise NextReply(self, self.run, args, kwargs)



#===============================================================================
## 'AsynchLeaf' class definition, shorthand for Asynchronous, Leaf.

class AsynchLeaf (Asynchronous, Leaf):
    pass




#===============================================================================
## 'Background' class definition.
##
## This is a mix-in class that can be used in asynchronous 'Leaf' classes (and
## subclasses, like 'Macro').  This modifies behavior of a leaf as follows:
##   - Once the 'run()' method completes a NEXT reply is sent back to the client
##   - The `next()` method is invoked in a separate thread, using the return
##     values from `run()` as inputs.
##
## This allows further commands to be processed while this command is running.
##
## For instance, to create the asynchronous leaf 'COMMand', use:
##
##     class COMMand (Asynchronous, Leaf):
##         ...
##
##         def run(self, input1 = str, input2 = int):
##             ...
##             return (nextArg1, nextArg2)
##
##         def next(self, nextArg1, nextArg2):
##             ...
##             return (outputArg1, outputArg2...)

class Background (object):
    asynchronous = True
    SYNCHRONOUS  = 'synchronous'

    def addDefaultInputs (self):
        Leaf.addDefaultInputs(self)
        self.createInput(self.SYNCHRONOUS, type=bool, named=True, default=False)

    def execute (self, args, kwargs, argmap):
        nextargs = self.run(*args, **kwargs)
        if nextargs is not None:
            if not isinstance(nextargs, tuple):
                nextargs = (nextargs,)

            #currentThread().check()
            if argmap.get(self.SYNCHRONOUS, False):
                return self.next(*nextargs)
            else:
                raise NextReply(self, self.__next__, nextargs, {})

    def next (self, *args):
        pass



#===============================================================================
## 'AsynchLeaf' class definition, shorthand for Asynchronous, Leaf.

class BackgroundLeaf (Background, Leaf):
    pass




#===============================================================================
## 'Singleton' mix-in class for commands where only one instance may
## be running at any given time.

class Singleton (object):
    class SingletonRunning (RunError):
        'Only one instance of %(command)r may be running at any given time'

    def __new__ (self, *args, **kwargs):
        self._runLock = Lock()
        return object.__new__(self, *args, **kwargs)

    def prerun (self, *args, **kwargs):
        if not self._runLock.acquire(0):
            raise self.SingletonRunning(command=self.commandPath())

    def postrun (self, *args, **kwargs):
        self._runLock.release()



#===============================================================================
## 'CommandWrapper' class for commands that run subcommmand streams


class CommandWrapper (object):
    '''Mix-in for commands that run subcommand streams'''

    def substitute (self, command, **substitutions):
        for k, v in substitutions.items():
            command = command.replace(k.join("$$"), str(v))
        return command


    def commandStream (self, command, **substitutions):
        '''
        Returns a StringIO() file object from a command block
        with substitutions.
        '''

        if isinstance(command, (list, tuple)):
            command = ' '.join(command)

        for k, v in substitutions.items():
            command = command.replace(k.join("$$"), str(v))
        return StringIO(command)

