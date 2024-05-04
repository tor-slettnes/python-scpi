#!/usr/bin/python3 -B
#===============================================================================
## @file server.py
## @brief Launch SCPI Server
#===============================================================================

### Modules relative to install path
from .listener.load import runServer, getStartupOption, setStartupOptions
from .sessions.module_session import setModulePath
from ..tools.settingsstore import SettingsStore
from ..client import SocketClient

### Standard Python modules
import sys, os, os.path, argparse, platform, glob

_baseFolders = []
_subtrees    = []

try:
    from os import fork
    gotFork = True
except ImportError:
    gotFork = False


def setBaseFolders (*folders):
    _baseFolders[:] = folders

def setFlavor (flavor):
    _subtrees[:] = [_f for _f in (os.path.join('flavors', flavor), ".") if _f]


def getPathList (path):
    if path is None:
        return []
    if isinstance(path, str):
        return [d for d in path.split(os.pathsep) if d]
    elif isinstance(path, (list, tuple)):
        return path
    else:
        assert False, "Invalid invocation getPathList(path=%r); path must be a string, list, tuple, or None"%(path,)


def getPathVariable (name):
    return [d for d in os.getenv(name, "").split(os.pathsep) if d]


def buildPath (pathlist, initial, *subfolders):
    launchdir = os.path.dirname(sys.argv[0])

    if initial:
        for folder in initial:
            fullpath = os.path.abspath(os.path.join(launchdir, folder))
            if not fullpath in pathlist:
                pathlist.append(fullpath)

    for basefolder in [_f for _f in _baseFolders if _f]:
        for subtree in _subtrees:
            for subfolder in subfolders:
                fullmask = os.path.abspath(os.path.join(launchdir, basefolder, subtree, subfolder))
                for fullpath in glob.glob(fullmask):
                    if os.path.isdir(fullpath) and not fullpath in pathlist:
                        pathlist.append(fullpath)


def extendPath (path):
    buildPath(path, None, "server", "tools")


def interface (address, defhost="", defport=7000):
    try:
        host, port = address.split(':')
    except ValueError:
        try:
            port = int(address)
        except ValueError:
            host = address
            port = defport
        else:
            host = defhost
    else:
        try:
            port = int(port)
        except ValueError:
            fatal('Invalid port number: %r'%(port,))

    return (host, port)

def buildOptions (parser, **defaults):
    TRACE, DEBUG, INFO, NOTICE, WARNING = list(range(5))

    # parser.set_usage('%prog [options] [module [class]]')

    parser.add_argument(
        '--shutdown',
        dest='shutdown', default=False, action='store_const', const=True,
        help='Shut down a running server.')

    parser.add_argument(
        '-b', '--bind', '-p', '--port',
        dest='bindplain', nargs=1, default=None,
        help='Listen for incoming plain socket connections on the specified network '
        'interface (specified by name or IP address) & port number.')# [%default].')

    parser.add_argument(
        '--fork',
        dest='fork', default=False, action='store_const', const=True,
        help='Fork off and run in background')

    parser.add_argument(
        '--pid-file', '--pidfile',
        dest='pidfile', nargs=1,
        help='Store the process ID of the server in the specified file')

    parser.add_argument(
        '-t', '--telnet', '--telnet-interface',
        dest='bindtelnet', nargs=1, default=None,
        help='Listen for incoming telnet connections on the specified network '
        'interface (specified by name or IP address) & port number.')# [%default].')

    parser.add_argument(
        '-n', '--no-debug', '--normal',
        dest='loglevel', action='store_const', const=INFO, default=INFO,
        help='Normal verbosity; messages are logged at "INFO" level or above.')

    parser.add_argument(
        '-d', '--debug',
        dest='loglevel', action='store_const', const=DEBUG, default=INFO,
        help='More verbose log output')

    parser.add_argument(
        '--trace',
        dest='loglevel', action='store_const', const=TRACE, default=INFO,
        help='Ridiculously verbose log output')

    parser.add_argument(
        '-o', '--output',
        dest='output', nargs=1, default="-",
        help='Redirect output to the specified file/device [(standard output)]')

    parser.add_argument(
        '--output-format',
        dest='outputformat', nargs=1, default="$localtime$ $topic:20$ [$level:1$]: $message$",
        help='Message logging format')

    parser.add_argument(
        '-q', '--quiet',
        dest='loglevel', action='store_const', const=NOTICE, default=INFO,
        help='More quiet log output (just notices, warnings and errors)')

    parser.add_argument(
        '-l', '--load',
        dest='preload', action='append',
        help=('Preload (run) the specified module file at startup, prior to '
              'listening for client connections.  This option may be repeated '
              'to sequentially load more than one module.'))

    parser.add_argument(
        '-a', '--load-asynchronously',
        dest='postload', action='append',
        help=('Load (run) the specified module file at startup, after listening '
              'for client connections.   This option may be repeated to '
              'sequentially load more than one module.'))

    parser.add_argument(
        '-e', '--exit-module',
        dest='exitmodules', action='append',
        help=('Run the specified module at shutdown.  This option may be repeated '
              'to sequentially run more than one module.'))

    parser.set_defaults(**defaults)
    return parser


def initPythonPath ():
    extendPath(sys.path)
    return sys.path

def initLoadPath ():
    path = getPathVariable("LD_LIBRARY_PATH")
    extendPath(path)
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(path)
    return path

def initConfigPath (configpath=None):
    path    = []
    initial = getPathList(configpath) or getPathVariable("CONFIGPATH")
    buildPath(path, initial, "config")
    return path

def initModulePath (modulepath=None):
    path    = []
    initial = getPathList(modulepath) or getPathVariable("MODULEPATH")
    buildPath(path, initial, os.sep.join(("Subsystems", "*", "*")), "methods")
    return path

def initialize (baseFolders=(".",), configpath=None, modulepath=None, **defaults):
    parser = argparse.ArgumentParser()
    buildOptions(parser, configpath=configpath, modulepath=modulepath, **defaults)
    args = parser.parse_args()

    setBaseFolders(*baseFolders)
    setFlavor(args.flavor)

    initPythonPath()
    initLoadPath()

    configpath = initConfigPath(args.configpath)
    modulepath = initModulePath(args.modulepath)

    SettingsStore.search_path = configpath
    setModulePath(modulepath)
    setStartupOptions(args)


def shutdownServer (host='127.0.0.1', port=7000):
    scpi = SocketClient(serveraddr=(host, port))

    try:
        scpi.connect()
        scpi.sendReceive("ACCess Administrator", timeout=5)
        scpi.sendCommand("SHUTDOWN")
        exit(0)

    except Exception as e:
        sys.stderr.write("Failed to shut down server at %s, port %d: %s\n"%(host, port, e))
        exit(-1)


def serverStatus (host='127.0.0.1', port=7000):
    scpi = SocketClient(serveraddr=(host, port))
    try:
        scpi.connect()
    except Exception as e:
        print("instrumentserver is stopped")
        return 2

    try:
        scpi.sendReceive("ACCess OBSERVER", timeout=5)
        ok, version = scpi.sendReceive("SYSTem:VERsion?", timeout=5)
        ok, build = scpi.sendReceive("SYSTem:BUILD?", timeout=5)
        ok, pid = scpi.sendReceive("SYSTem:PID?", timeout=5)
        ok, flavor = scpi.sendReceive("SYSTem:FLAVor?", timeout=5)

        print(("instrumentserver %s build %s is running, flavor=%s, pid=%s"%
              (version, build, flavor, pid)))
        return 0
    except Exception as e:
        print("instrumentserver is stale")
        return 2


def getListeners() -> dict:
    listeners = SettingsStore("listeners.json")

    if addr := getStartupOption('bindplain'):
        host, port = interface(addr)
        listeners.setdefault('plain', {}).update(
            address=host,
            port=port,
            handler='plain')

    if addr := getStartupOption('bindtelnet'):
        host, port = interface(addr)
        listeners.setdefault('telnet', {}).update(
            address=host,
            port=port,
            handler='telnet')

    return listeners

def printVersionInfo (option):
    c = SettingsStore("version.json")
    string = c.get("server", {}).get(option, "-")
    print(string)

def run(top=None, **options):
    runServer(top, getListeners(), **options)

