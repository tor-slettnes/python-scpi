#===============================================================================
## @file __init__.py
## @brief Exception class defintions
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Modules relative to install path
from ...tools.parser import parser, QUOTE_ATTRIBUTES, QUOTE_NEVER

### Standard Python modules
from sys       import exc_info
from traceback import extract_tb
from os.path   import basename
from os        import strerror
from errno     import errorcode

APPLICATION = "SAMLet"

class Exc (Exception):
    contextSeparator = "-->"
    transient = False

    def __init__ (self, *args, **kwargs):
        Exception.__init__(self)
        self.args     = args
        self.kwargs   = kwargs
        self.name     = type(self).__name__
        self.path     = []

    def __str__ (self):
        return self.name

    def __repr__ (self):
        parts = self.getContext() + [str(self)]
        return self.contextSeparator.join("  ").join(parts)

    def update (self, **kwargs):
        self.kwargs.update(kwargs)

    def getArgs (self):
        items = [ (name, value)
                  for (name, value) in list(self.kwargs.items())
                  if name[:1].isalpha() and value is not None ]
        items.sort()
        return items

    def insertContext (self, context):
        self.path.insert(0, context)

    def getContext (self):
        return self.path

    def getTraceback (self):
        return []

    def parts (self, withID=True, withArgs=True, withContext=False, withTraceback=False, 
                withText=True, multiline=True):

        parts = []
        partcount = 0

        if withID:
            parts.append((None, "[%s]"%self.name))
            partcount += 1

        if withArgs:
            parts.extend(self.getArgs())
            partcount += 1

        cparts = []
        if withContext:
            cparts.append('')
            for context in self.getContext():
                cparts.append(' '.join((self.contextSeparator, context)))

        if withTraceback:
            tparts = self.getTraceback()
            if tparts:
                if partcount:
                    cparts.append(' '.join((self.contextSeparator, 'Traceback:')))
                    cparts.extend(tparts)
                partcount += 1

        if withText:
            if partcount:
                cparts.append(' '.join((self.contextSeparator, str(self))))
            else:
                cparts.append(str(self))

        parts.append((None, (" ", "\n ")[multiline].join(cparts)))
        return parts


    def format (self, showID=True, showArgs=True, showContext=False, showTraceback=False,
                showText=True, tag=None, quoting=QUOTE_ATTRIBUTES, multiline=True):
        parts = self.parts(showID, showArgs, showContext, showTraceback, showText, multiline)
        return parser.collapseArgs(parts, tag=tag, quoting=quoting)


    def throw (self):
        raise self


class Error (Exc):
    def __init__ (self, _name=None, _text=None, *args, **kwargs):
        Exc.__init__(self, *args, **kwargs)
        self.name     = _name or type(self).__name__
        self.text     = _text or (type(self).__doc__ or "")%kwargs
        self.path     = []

    def __str__ (self):
        try:
            return " ".join(self.text.split())
        except:
            return "%s"%(self.text,)



#    def format (self, showID=True, showArgs=True, showContext=False,
#                showText=True, tag=None, quoting=QUOTE_ATTRIBUTES, multiline=True):
#        parts = []
##
#        if showID:
#            parts.append("[%s]"%self.name)
##
#        if showArgs:
#            parts.extend(parser.collapseParts(self.getArgs(), tag=tag, quoting=quoting))
##
#        if showContext:
#            for context in self.getContext():
#                if multiline:
#                    parts.append("\n")
#                parts.append(self.contextSeparator)
#                parts.append(parser.protectString(context, tag=tag, quoting=quoting))
##
#            if multiline:
#                parts.append("\n")
##
#        if showText:
#            if showID or showArgs or showContext:
#                parts.append(self.contextSeparator)
##
#            message = parser.protectString(str(self), tag=tag, quoting=QUOTE_NEVER)
#            parts.append(message)
##
#        return " ".join(parts)


class ComponentError (Error):
    def __init__ (self, _component, _id, _text, *args, **kwargs):
        Error.__init__(self, "%s.%s"%(_component, _id), _text, *args, **kwargs)


class RunError (Error):
    name = None
    def __init__ (self, _name=None, _text=None, *args, **kwargs):
        Error.__init__(
            self,
            "%s.Core.%s"%(APPLICATION,  _name or self.name or self.__class__.__name__),
            _text,
            *args,
            **kwargs)

class CommandError (RunError):
    pass

class UserError (Error):
    def __init__ (self, _id, _text, *args, **kwargs):
        Error.__init__(
            self,
            _id if "." in _id else ("%s.%s"%(APPLICATION, _id)),
            _text,
            *args,
            **kwargs)

    def __str__ (self):
        return self.text

class EnvError (Error, EnvironmentError):
    def __init__ (self, _exception, location=None, **kwargs):
        self.original = _exception
        self.errno    = _exception.errno
        self.strerror = (_exception.strerror
                         or (_exception.errno and strerror(_exception.errno))
                         or "Unknown error")
        self.filename = _exception.filename
        self.args     = (self.errno, self.strerror)
        self.location = location

        errcode   = errorcode.get(self.errno, 'Generic')
        Error.__init__(
            self,
            ".".join((APPLICATION, type(_exception).__name__, errcode)),
            self.strerror,
            errno=self.errno,
            location=self.location,
            filename=self.filename,
            **kwargs)

    def __str__ (self):
        path = self.location or self.filename

        if path:
            return ': '.join((Error.__str__(self), path))
        else:
            return Error.__str__(self)


class InternalError (Error):
    def __init__ (self, _exception, _excinfo, _invocation=None, *args, **kwargs):
        args = _exception.args + args
        self.original   = _exception
        self.excinfo    = _excinfo or exc_info()
        self.invocation = _invocation

        Error.__init__(
            self,
            "%s.Internal.%s"%(APPLICATION, type(_exception).__name__),
            "%s: %s"%(type(_exception).__name__, _exception),
            *args,
            **kwargs)


    def getArgs (self):
        e_type, e_name, e_tb = self.excinfo
        args = Exc.getArgs(self)
        filename, lineno, functionname, text = extract_tb(e_tb)[-1]
        args += [('filename', basename(filename)),
                 ('line', lineno),
                 ('method', functionname)]
        return args

    def getTraceback (self):
        e_type, e_name, e_tb = self.excinfo
        return [ "In %s, method %s(), line %d: %s"%(filename, method, lineno, text)
                 for filename, lineno, method, text in extract_tb(e_tb) ]


    def throw (self):
        e_type, e_name, e_tb = self.excinfo
        raise self.with_traceback(e_tb)


class ExternalError (RunError):
    def __init__ (self, _exception, _text=None, *args, **kwargs):
        self.original = _exception
        args = _exception.args + args

        Error.__init__(self,
                       type(_exception).__name__,
                       _text or str(_exception) or type(_exception).__name__,
                       *args, **kwargs)



### Session Control Exceptions

class SessionControl (Exc): pass

class Break (SessionControl): pass
class ReturnValue (SessionControl): pass
class ReturnCall (SessionControl): pass

class NextControl (SessionControl):  
    def __init__ (self, leaf, method=None, args=(), kwargs={}):
        SessionControl.__init__(self, leaf, method, args, kwargs)
        self.leaf = leaf
        self.method = method
        self.methodArgs = args
        self.methodKwargs = kwargs

class NextReply (NextControl): pass
class NextCommand (NextControl): pass


def scpiException (_exception, _excinfo=None, _invocation=None, *args, **kwargs):
    if _exception is None:
        return None

    elif isinstance(_exception, EnvironmentError):
        return EnvError(_exception)

    elif isinstance(_exception, Exc):
        return _exception

    else:
        return InternalError(_exception, _excinfo, _invocation, *args, **kwargs)
