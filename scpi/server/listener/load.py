#!/usr/bin/python3
#===============================================================================
## @file load.py
## @brief Instrument Command Server & Request Handler
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base_server import BaseRequestHandler, server_types
from ..exceptions import Error
from ..sessions.init_session import InitSession
from ...tools.publication import info, warning, error, initlogging, setDefaultLogLevel
from ...tools.invocation import safe_invoke
from ...tools.settingsstore import SettingsStore

## Standard Python modules
import os, sys, signal, time, select, threading

### Private symbols
_pidfile       = None
_options       = None
_trunk         = None
_exitmodules   = []
_listeners     = {}

def runModule (scope, path):
    try:
        session = InitSession(module=path, description="init module %r"%path)
        session.handle(scope)
    except Error as e:
        commandpath = scope.commandPath()
        warning("Failed to run module %r%s: [%s] %s"%
                (path,
                 " in scope "+commandpath if commandpath else "",
                 type(e).__name__, e))


def loadModulesThread (scope, modules, description):
    start = time.time()
    for module in modules:
        safe_invoke(runModule, (scope, module), {}, "init module %r"%(module,))

    elapsed = time.time() - start
    info('%s processed in %.3f seconds'%(description, elapsed))


def loadModules (scope, modules, description):
    t = threading.Thread(target=loadModulesThread,
                         name=description,
                         args=(scope, modules, description),
                         daemon=True)
    t.start()
    return t



def createPidFile (filename, pid=None):
    global _pidfile
    if filename:
        try:
            file(filename, "w").write("%s\n"%(pid or os.getpid()))
            _pidfile = filename
        except EnvironmentError as e:
            warning('Unable to save PID file "%s": %s (errno=%s)'%
                    (e.filename, e.args[-1], e.errno))

def removePidFile (filename=None):
    global _pidfile
    if _pidfile:
        try:
            os.remove(_pidfile)
        except EnvironmentError as e:
            warning('Unable to remove PID file "%s": %s (errno=%s)'%
                    (e.filename, e.args[-1], e.errno))
        else:
            _pifile = None


def background (closeInput=True, closeOutput=True, closeError=True, pidfile=None):
    try:
        pid = os.fork()
    except (AttributeError, EnvironmentError) as e:
        warning("Cannot fork to background: [%s] %s"%(e.__class__.__name__, e))
    else:
        if pid:
            createPidFile(pidfile, pid=pid)
            sys.exit(0)
        else:
            if closeInput:
                infile  = file(os.devnull, 'r')
                os.dup2(infile.fileno(), 0)

            if closeOutput or closeError:
                outfile = file(os.devnull, 'w')

                if closeOutput:
                    os.dup2(outfile.fileno(), 1)

                if closeError:
                    os.dup2(outfile.fileno(), 2)



def shutdown (signal=None, action=None, reason=None, exit=True):
    info('Shutting down (%s)'%(reason or "signal %s"%(signal,)))

    if _exitmodules:
        loadModules(_trunk, _exitmodules, 'Shutdown modules').join()

    try:
        _trunk.shutdown()
    finally:
        removePidFile()
        if exit:
            os._exit(0)


def fatal (message):
    sys.stderr.write("%s\n"%message)
    sys.exit(2)


def addListener (name, server_type, attributes, default=False):
    try:
        listener = _listeners[name] = server_type(**attributes)
    except (TypeError, EnvironmentError, ImportError) as e:
        error('Could not create listener %r using %r: [%s] %s'%
              (name, server_type.__name__, type(e).__name__, e))
    else:
        if default:
            _listeners[None] = listener
        return listener


def removeListener (name):
    if _listeners.pop(name, None) == _listeners.get(None):
        _listeners.pop(None)

def addListeners (listeners):
    for (name, listener) in listeners.items():
        arguments = listener.copy()
        listener = arguments.pop('type', 'plain')
        default = arguments.pop('default', False)

        try:
            server_type = server_types[listener]
        except KeyError as e:
            fatal("Listener %r has unknown type %r"%(name, listener))
        else:
            info("Adding listener %r type %s with args %s, default=%s"%
                 (name, server_type.__name__, arguments, default))
            addListener(name, server_type, arguments, default=default)

def load(top=None,
         listeners=[],
         modulename='scpiTop',
         classname='Top',
         **options):
    global _trunk, _options, _exitmodules

    try:
        SIGTERM, SIGHUP, SIGSEGV = signal.SIGTERM, signal.SIGHUP, signal.SIGSEGV
    except AttributeError:
        pass
    else:
        signal.signal(SIGTERM, shutdown)
        signal.signal(SIGHUP, shutdown)
        signal.signal(SIGSEGV, shutdown)

    if top is None:
        m   = __import__(modulename)
        top = getattr(m, classname)

    if redirected := _options.output not in ("", "-"):
        try:
            output = file(_options.output, 'w')
            os.dup2(output.fileno(), 1)
            os.dup2(output.fileno(), 2)
            redirected = True
        except EnvironmentError as e:
            fatal('Unable to redirect output to %r: %s'%(e.filename, e))

    setDefaultLogLevel(_options.loglevel)

    if _options.fork:
        background(closeOutput=not redirected, pidfile=_options.pidfile)
    else:
        initlogging(_options.loglevel, _options.outputformat)
        createPidFile(_options.pidfile)

    if callable(top):
        servername = ' '.join([_f for _f in (top.__name__, _options.flavor) if _f])
        info('Starting %s server'%servername)
        start = time.time()
        top = top()
        elapsed  = time.time() - start
        info('Commands constructed in %ss'%elapsed)

    BaseRequestHandler.setTop(top)

    _trunk = top
    _exitmodules = _options.exitmodules

    if _options.preload:
        loadModules(top, _options.preload, 'Synchronous startup modules').join()

    addListeners(listeners)

    if _options.postload:
        loadModules(top, _options.postload, 'Asynchronous startup modules')


def serve ():
    try:
        while _listeners:
            try:
                candidates = [listener
                              for listener in _listeners.values()
                              if listener.is_available()]

                (inlist, _, _) = select.select(list(candidates), [], [], 2.0)

            except EnvironmentError:
                pass

            else:
                takers = 0
                for listener in inlist:
                    try:
                        listener.handle_request()
                        takers += 1
                    except EOFError as e:
                        pass

                if not takers:
                    time.sleep(1.0)

    except KeyboardInterrupt:
        shutdown(reason="Keyboard Interrupt")

    except SystemExit:
        shutdown(reason="System Exit")

    except Exception as e:
        shutdown(reason="Exception: [%s] %s"%(type(e).__name__, e))


def runServer(*args, **kwwargs):
    load(*args, **kwwargs)
    serve()


def setStartupOptions (options):
    global _options
    _options = options


def getStartupOption (name, default=Exception):
    try:
        return getattr(_options, name)
    except AttributeError:
        if default is Exception:
            raise
        return default

def getStartupOptions ():
    return [ name for name in dir(_options) if name.isalpha() ]

def getTrunk ():
    return _trunk
