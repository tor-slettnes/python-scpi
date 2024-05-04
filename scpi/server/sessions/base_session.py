#===============================================================================
## @file base_session.py
## @brief Base SCPI session
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Modules relative to install path
from .symbols import Context, T_AUTH, AccessLevels, \
    GUEST, OBSERVER, CONTROLLER, ADMINISTRATOR, FULL, \
    SYNC, ASYNC, RAISE, PASSTHROUGH

from ..base.parameter import boolean, integer, real
from ..exceptions import scpiException, \
    Exc, Error, RunError, CommandError, InternalError, ExternalError, \
    SessionControl, NextControl, NextReply, NextCommand, Break, ReturnValue, ReturnCall

from ...tools.settingsstore import SettingsStore
from ...tools.dataproxy import DataProxy
from ...tools.publication import addTopic, deleteTopic, publish, info, \
    TRACE, DEBUG, INFO, NOTICE, WARNING
from ...tools.parser import CommandParser, ParseError, CookedValue, \
    QUOTE_NEVER, QUOTE_AUTO


### Standard Python modules
import weakref
import sys
import re
import random
import io
import threading
import hmac
import base64

try:
    from hashlib import md5
except ImportError:
    import md5


#===============================================================================
### BaseSession class definition.
##
### An instance of this class is created for each external and
### internal client session.  It is an abstract parent class for
### InitSession, ClientSession, and NestedSession.

class BaseSession (CommandParser):
    '''
    Abstract superclass for SCPI sessions
    '''

    class InsufficientAccess (RunError):
        'This operation requires %(requiredAccess)s access or higher; current level is %(currentAccess)s'

    class AccessLevelExceeded (RunError):
        'This level exceeds your access limit (%(accessLimit)s)'

    class InvalidAccessLevel (CommandError):
        'Access level %(accessLevel)r does not exist'

    class IncorrectSessionType (RunError):
        'Top-level session is a %(found)s, expeted a %(expected)s'


    class ParseError (CommandError):
        def __init__ (self, expression, pos, reason, subexpression, exception):
            CommandError.__init__(self, None, reason, expression=subexpression)
            self.expression = expression
            self.pos        = pos
            self.reason     = reason
            self.exception  = exception
            if subexpression:
                self.insertContext(subexpression)
            self.insertContext(expression.strip())

        def __str__ (self):
            if self.exception:
                return str(self.exception)
            else:
                return str(self.reason)

        def format (self, *args, **kwargs):
            if self.exception:
                return self.exception.format(*args, **kwargs)
            else:
                return CommandError.format(self, *args, **kwargs)

    class PythonError (CommandError):
        def __init__ (self, name, text, **argmap):
            CommandError.__init__(self, name, text, **argmap)

    class VariableSyntax (CommandError):
        '%(expression)s <-- Invalid variable syntax'

    accessinfo    = None
    accessLevel   = None
    accessLimit   = None
    authLimit     = None
    exclusive     = None
    stealthAccess = False
    challenge     = None
    authdata      = None
    instances     = []
    sessionIndex  = 0
    mutex         = threading.Lock()

    def __init__ (self, instream, description, id_prefix=None):
        self.instream       = instream
        self.description    = description
        self.variables      = {}
        self.jobs           = []

        with self.mutex:
            self.sessionid  = self.nextSessionID(id_prefix)
            self.setRole(None)

            if self.accessinfo is None:
                BaseSession.accessinfo   = SettingsStore('access.json')

            if self.authdata is None:
                BaseSession.authdata     = SettingsStore('authentication.json')

            self.addInstance()

    @classmethod
    def nextSessionID (cls, prefix):
        if prefix == None:
            prefix = cls.__name__[0]

        cls.sessionIndex += 1
        return prefix+str(cls.sessionIndex)

    def setRole (self, role):
        self.role       = role
        self.debugTopic = "-".join([_f for _f in ("Session", role, self.sessionid) if _f])

    @classmethod
    def getInstances (cls, instanceClass):
        return [ s() for s in cls.instances if isinstance(s(), instanceClass) ]

    def addInstance (self):
        self.instances[:] = [ s for s in self.instances if s() is not None ] + [weakref.ref(self)]

    def top (self, cls=None):
        session = self
        while session.parent:
            session = session.parent
        if cls and not isinstance(session, cls):
            raise self.IncorrectSessionType(expected=cls.__name__, found=type(session).__name__)
        return session


    #===========================================================================
    ### Methods to support command and variable expansions
    ### (used in "CommandParser()")

    def _getInputArgument (self, arg, context):
        self.checkAccess(OBSERVER)
        try:
            index = int(arg, 0)
        except ValueError:
            index = 0

        if index:
            try:
                return context.outputs[index-1][CookedValue]
            except (IndexError, TypeError, AttributeError):
                return
        else:
            if arg == '0':
                sep, tag, quoting = ' ', None, QUOTE_NEVER
            elif arg == '@':
                sep, tag, quoting = ' ', 'arg', QUOTE_AUTO
            else:
                sep, tag, quoting = arg, 'arg', QUOTE_AUTO

            return self.collapseArgs(context.outputs, tag=tag, quoting=quoting, separator=sep)

    def _getCommandOutput (self, command, context):
        commandtext, index, command, args = self.expandParts(command, context)

        if command:
            subcontext = context.clone(invocation=None)
            subcontext = self.runParts(subcontext, command, args, nextReply=SYNC, catchReturn=True)
            return self.collapseArgs(subcontext.outputs, tag=None, quoting=QUOTE_NEVER)


    _vx = re.compile(r'^(#)?\s*(?:(\d+|@)|(\w[\w-]*)\s*(?:\[(\w*)\])?)\s*'
                     r'(?:/(/?)([^/]+)(?:/(.*))?|'
                     r':((?:\s+[\+\-]|\s*)?\d+)\s*:?\s*([+-]?\d*)\s*:?\s*([+-]?\d*)\s*|'
                     r':([+-])(.*)|'
                     r'\?([+-])(.*)?|'
                     r'(\?)([^:]*):?(.*)'
                     r')?$')

    def _getVariable (self, name, context):
        self.checkAccess(OBSERVER)
        portion   = None
        handling  = None
        search    = None

        match = self._vx.match(name)
        if not match:
            raise self.VariableSyntax(expression=name.strip())

        (hashmark, argindex, key, subkey,
         isregex, search, replace,
         offset, length, step,
         check, alternate,
         vassert, vtext,
         ifelse, iftext, elsetext) = match.groups()

        proxy = DataProxy((context.data,
                           context.scope.branchData,
                           context.scope.globalData))

        if argindex:
            value = self._getInputArgument(argindex, context)

        else:
            try:
                varscope, data, value = proxy.getScopeDataValue(None, key)
                value = proxy.getValue(value, subkey)
            except (KeyError, TypeError, IndexError):
                value = ''

        if search:
            string = proxy.toString(value)
            if isregex:
                value = re.sub(search, replace or '', string)
            else:
                value = string.replace(search, replace or '')

        elif offset:
            start, end, step = int(offset), None, None
            if length:
                end = start + int(length)
            if step:
                step = int(step)

            value = value[start:end:step]

        if hashmark is not None:
            value = len(value)
        else:
            value = proxy.toString(value)

        if vassert:
            value = ("", vtext)[boolean(value) == (vassert == '+')]

        elif ifelse:
            value = (elsetext, iftext)[boolean(value)]

        elif alternate and (bool(value) == (check == '+')):
            value = alternate


        return value


    def _getEvaluationResult (self, expression, context,
                              assignments=None, imports=("math", "re")):
        '''
        Evaluate "expression" natively in Python, and return the result.
        '''
        localmap = { 'session':self,
                     'scope':context.scope, 'find':context.scope.find,
                     'BOOL':boolean, 'INT':integer, 'REAL':real }

        self.checkAccess(ADMINISTRATOR)

        try:
            for modulename in imports:
                m = __import__(modulename)
                localmap.update(m.__dict__)

            varscopes = (context.scope.globalData,
                         context.scope.branchData,
                         context.data,
                         assignments)

            for idx, varscope in enumerate(varscopes):
                localmap.update(list((varscope or {}).items()))

            return eval(expression, globals(), localmap)

        except Exc:
            raise

        except Exception as e:
            raise self.PythonError(type(e).__name__,
                                   str(e).strip(),
                                   expression=expression.strip())


    #===========================================================================
    ### Parse client input

    def expandParts (self, instream, context):
        text, parts = self.expandArgs(instream, context=context)
        args = list(parts)
        index = None

        try:
            option, command, rawtext = args.pop(0)

            if not option and command[:1].isdigit():
                index = command
                option, command, rawtext = args.pop(0)

        except IndexError as e:
            return text, index, None, None

        else:
            if option:
                command = self.collapsePart((option, command), raw=True)

            return text, index, command.strip(), args


    def getCommand (self, instream, context):
        try:
            return self.expandParts(instream, context=context)
        except ParseError as e:
            raise self.ParseError(e.expression, e.pos, e.reason, e.subexpression, scpiException(e.exception, e.exc_info))


    #===========================================================================
    ### Handle client input

    def handle (self, scope, invocation=None, localdata=None, **kwargs):
        context = Context(self, scope, invocation=invocation, data=localdata)
        cleanupargs = self.setup(context)
        try:
            if not context.exception:
                return self.handleInput(self.instream, context, **kwargs)
        finally:
            self.cleanup(context, *cleanupargs)

    def setup (self, context):
        #addTopic(self.debugTopic)
        return ()

    def cleanup (self, context):
        if BaseSession.exclusive == self:
            BaseSession.exclusive = None

        deleteTopic(self.debugTopic, ignoreMissing=True)

    def close (self):
        ### Prevent further reads from the input stream
        self.instream.close()

    def handleExceptions (self, context, func, args=(), argmap={}, notify=info, asynchronous=False):
        job   = context, threading.currentThread(), func, args, argmap, asynchronous

        self.addJob(job)
        try:
            func(*args, **argmap)

        except NextReply as e:
            self.startThread(context, e.leaf, e.method, e.methodArgs, e.methodKwargs, notify)

        except (Break, ReturnValue) as e:
            pass

        except Exception as e:
            exception = scpiException(e, sys.exc_info(), (func, args, argmap))
            if context.text:
                exception.insertContext(context.text.strip())

            self.logException(exception, context.text)
        finally:
            self.finishJob(job)

    def handleInput (self, instream, context):
        raise NotImplemented

    #===========================================================================
    ### The following are used to invoke commands

    def runBlock (self, input, context, nextReply=ASYNC, nextCommand=ASYNC, catchReturn=False, where=None):
        if isinstance(input, str):
            instream = io.StringIO(input)
        elif isinstance(input, (list, tuple)):
            instream = io.StringIO(' '.join(input))
        elif hasattr(input, 'seek'):
            instream = input
            instream.seek(0)
        else:
            assert False, \
                "Session %s runBlock() received unsupported data type %s in input %s"%\
                (self.description, type(input).__name__, input)

        return self.runStream(instream, context,
                              nextReply=nextReply,
                              nextCommand=nextCommand,
                              catchReturn=catchReturn,
                              where=where)

    def runStream (self, instream, context,
                   nextReply=ASYNC, nextCommand=ASYNC,
                   catchReturn=False, seek=None, where=None):

        assert not isinstance(instream, (str, list, tuple))

        while True:
            try:
                text, index, command, args = self.getCommand(instream, context)
                if command is None:
                    continue
            except EOFError:
                return ()
            except Exc as e:
                context.update(response=None, exception=e)
                raise
            else:
                context.update(text=text, index=index)

            try:
                context = self.runParts(context, command, args, nextReply=nextReply, catchReturn=False)

            except Break as e:
                if catchReturn:
                    return
                else:
                    raise

            except ReturnValue as e:
                if catchReturn:
                    return e.args
                else:
                    raise

            except NextControl as e:
                if isinstance(e, NextCommand) and not e.method:
                    e.method       = self.runStream
                    e.methodArgs   = (instream, context)
                    e.methodKwargs = dict(nextReply=ASYNC, nextCommand=SYNC, catchReturn=False)

                asyncArgs = (instream, context, e.method, e.methodArgs, e.methodKwargs)
                action    = (nextReply, nextCommand)[isinstance(e, NextCommand)]

                if action == PASSTHROUGH:
                    raise

                elif action == RAISE:
                    raise NextReply(e.leaf, self.runAsynchronousStream, asyncArgs, {})

                elif action == SYNC:
                    if e.method:
                        context.response = e.method(*e.methodArgs, **e.methodKwargs)

                elif action == ASYNC:
                    self.startThread(context, e.leaf, self.runAsynchronousStream, asyncArgs, {})
                    break

                else:
                    assert False, \
                       'Session.runStream() invoked with invalid "nextCommand" action %s in command: %s'\
                       %(nextCommand, text)

            except Error as e:
                text = self.extractContext(instream)
                e.insertContext(text.strip())
                if where:
                    e.insertContext(where)
                e.throw()



    def runAsynchronousStream (self, instream, context, method, args, kwargs):
        if method:
            method(*args, **kwargs)
        return self.runStream(instream, context, nextReply=ASYNC, nextCommand=SYNC, catchReturn=True)


    def runParts (self, context, command, args, scope=None, nextReply=ASYNC, catchReturn=False):
        try:
            context = self._run(context, command, args, scope)

        except NextReply as e:
            leaf, method, args, argmap = e.args

            if nextReply in (RAISE, PASSTHROUGH):
                raise
            elif nextReply == SYNC:
                context.response = method(*args, **argmap)
            elif nextReply == ASYNC:
                self.startThread(context, leaf, method, args, argmap)

        except Break as e:
            if not catchReturn:
                raise

        except ReturnValue as e:
            if not catchReturn:
                raise

        except ReturnCall as e:
            leaf, method, args, argmap = e.args
            outstream = io.StringIO()
            method(outstream, *args, **argmap)
            outstream.seek(0)
            text = outstream.read()
            context.leaf    = None
            context.outputs = [(None, text, text)]

        except Error as e:
            parts = [command]
            parts.extend(args)
            cmd = self.collapseArgs(parts)
            e.insertContext(cmd)
            raise

        return context


    def _run (self, context, command, args, scope=None):
        #assert context or scope, \
        #"Neither context nor scope was provided while running command %r with parts %s"%(command, args)

        if not scope:
            scope = context.scope
#        elif not context:
#            context = Context(self, scope)

        path, opts = scope.locate(command)

        try:
            branch, leaf = path[-2:]
        except ValueError:
            branch, leaf = scope, path[-1]

        iname, iargs = context.invocation
        method = getattr(leaf, iname)

        opts.update(_session=self,
                    _context=context,
                    _scope=scope,
                    _command=command,
                    _parts=args,
                    _branch=branch,
                    _callpath=path)

        response = outputs = exception = None
        try:
            response = method(*iargs, **opts)

        except ReturnValue as e:
            exception = e
            outputs   = e.args

        except Exc as e:
            exception = e

        except Exception as e:
            exception = scpiException(e, sys.exc_info(), (method, iargs, opts))

        finally:
            context.leaf      = leaf
            context.invoked   = method, iargs, opts
            context.response  = response
            context.outputs   = outputs
            context.exception = exception
            if exception:
                exception.throw()

        return context


    def _next (self, context, method, args, kwargs):
        context.response = method(*args, **kwargs)
        return context

    #===========================================================================
    ### Asynchronous execution

    def startThread (self, context, leaf, method, args, argmap, notify=info):
        basename    = leaf and leaf.commandPath(short=True) or method.__name__
        name        = ">".join((threading.currentThread().name, basename))
        #nextcontext = context.clone()
        nextcontext = context
        nextargs    = (nextcontext, method, args, argmap)
        handleargs  = (nextcontext, self._next, nextargs, {}, notify, True)

        thread = threading.Thread(target=self.handleExceptions,
                                  name=name,
                                  args=handleargs,
                                  daemon=True)
        self.trace("Starting thread %r in %s"%(thread.name, self.description))
        thread.setDaemon(True)
        thread.start()
        return thread

    def extractContext (self, instream, nlines=8):
        position = instream.tell()
        instream.seek(0)
        lines   = []
        readpos = 0
        for line in instream:
            lines.append(line)
            readpos += len(line)
            if readpos >= position:
                break

        if len(lines) > nlines:
            lines[nlines//2:len(lines) - nlines//2] = [" ...\n"]

        return ''.join(lines)



    #===========================================================================
    ### Command output processing

    #def formatOutputs (self, response, alwaysNamed=False, raw=False):
    #    try:
    #        leaf, outputs = response
    #    except TypeError:
    #        outputs = ()
    #    else:
    #        if leaf:
    #            outputs = leaf.formatOutputs(outputs, alwaysNamed=alwaysNamed, raw=raw)
    ##
    #    return outputs



    #===========================================================================
    ### Job control/watch support

    def addJob (self, job):
        self.jobs.append(job)

    def finishJob (self, job):
        try:
            self.jobs.remove(job)
        except ValueError:
            pass

    #===========================================================================
    ### Debug method

    def publish (self, topic, message, level, quoting=QUOTE_NEVER, literaltag=None):
        publish(topic, message, level=level, quoting=quoting, literaltag=literaltag)

    def trace (self, message):
        self.publish(self.debugTopic, message, level=TRACE)

    def debug (self, message):
        self.publish(self.debugTopic, message, level=DEBUG)

    def info (self, message):
        self.publish(self.debugTopic, message, level=INFO)

    def notice (self, message):
        self.publish(self.debugTopic, message, level=NOTICE)

    def warning (self, message):
        self.publish(self.debugTopic, message, level=WARNING)

    def logException (self, exc, circumstance=None):
        if isinstance(exc, SessionControl):
            intro     = "Session control:"
            logmethod = self.debug
            parts     = exc.parts(withContext=False)

        elif isinstance(exc, InternalError):
            intro     = "Internal error:"
            logmethod = self.notice
            parts     = exc.parts(withContext=True, withTraceback=True)

        elif isinstance(exc, Error):
            intro     = "Error:"
            logmethod = (self.info, self.debug)[exc.transient]
            parts     = exc.parts(withContext=not exc.transient)

        else:
            intro     = 'Exception:'
            logmethod = self.info
            parts     = exc.parts(withContext=True)

        message = [intro]
        if circumstance:
           message.append(circumstance.strip())
        message.extend(parts)
        logmethod(message)


    #===========================================================================
    ### Access control and authentication

    def checkAccessByName (self, requiredAccessName):
        self.checkAccess(self.accessLevelIndex(requiredAccessName, CONTROLLER))

    def checkAccess (self, requiredAccess):
        if self.accessLevel < requiredAccess:
            raise self.InsufficientAccess(requiredAccess=self.getLevelName(requiredAccess),
                                          currentAccess=self.getLevelName(self.accessLevel))

    def setAccessLevel (self, level, exclusive=False, stealth=False):
        if level > self.accessLimit:
            raise self.AccessLevelExceeded(accessLimit=self.getLevelName(self.accessLimit))

        self.accessLevel   = level
        self.stealthAccess = stealth

        if exclusive and not stealth:
            BaseSession.exclusive = self
        elif BaseSession.exclusive == self:
            BaseSession.exclusive = None

    def getStealthFlag (self):
        return self.stealthAccess

    def getExclusiveFlag (self):
        return False

    def getAccessLevel (self):
        return self.accessLevel

    def getAccessLimit (self):
        return self.accessLimit

    def getLevelName (self, index=None):
        return AccessLevels[index or self.accessLevel]

    def accessLevelIndex (self, name, *default):
        try:
            return list(AccessLevels).index(name and name.capitalize())
        except ValueError:
            if not default:
                raise self.InvalidAccessLevel(accessLevel=name)
            else:
                return default[0]

    def generateChallenge (self):
        self.challenge = "%032x"%(random.randint(0, 2**128-1),)
        return self.challenge

    def getChallenge (self):
        return self.challenge


    def isValidAuthentication (self, hexdigest, secret):
        if self.challenge:
            key = hmac.new(secret, self.challenge, md5).hexdigest()
            return (key.lower() == hexdigest.lower())


    def authenticatedLevel (self, spec, key, current, limit):
        try:
            level = self.accessLevelIndex(spec[key])
        except KeyError:
            level = current

        if limit is not None and level > limit:
            level = limit

        return level


    def authenticate (self, response):
        for profile, spec in list(self.authdata.items()):
            try:
                secrets = [base64.b64decode(secret) for secret in spec['secrets'].split()]
            except (TypeError, KeyError):
                pass
            else:
                for secret in secrets:
                    if self.isValidAuthentication(response, secret):
                        return self.authorize(profile, spec)


    def authorize (self, profile, spec):
        limit = self.authenticatedLevel(spec, 'limit', self.accessLimit, self.authLimit)
        level = self.authenticatedLevel(spec, 'level', self.accessLevel, limit)

        oldsession = self.sessionid
        self.setRole(profile)

        self.notify(DEBUG, T_AUTH,
                    role=self.role,
                    session=self.sessionid,
                    accessLevel=AccessLevels[level],
                    accessLimit=AccessLevels[limit],
                    oldLimit=AccessLevels[self.accessLimit])

        self.accessLevel, self.accessLimit = level, limit
        return (profile, level, limit, spec.get('preexec'), spec.get('postexec'))


    def addAuthProfile (self, name, spec, save=False):
        self.authdata[name] = spec
        if save:
            self.authconfig[name] = spec
            self.authconfig.save()

    def removeAuthProfile (self, name, save=False):
        del self.authdata[name]
        if save:
            self.authconfig.remove_section(name, save=True)

    def clearAuthPRofiles (self, save=False):
        self.authdata.clear()
        if save:
            for section in self.authconfig.sections():
                self.authconfig.remove_section(section)


    #===========================================================================
    ### PUBLish/SUBScribe support

    def subscribe (self, *args, **kwargs):
        raise NotImplementedError()

    def unsubscribe (self, *args, **kwargs):
        raise NotImplementedError()

    def clearSubscriptions (self, *args, **kwargs):
        raise NotImplementedError()

    def getSubscriptions (self, *args, **kwargs):
        raise NotImplementedError()

