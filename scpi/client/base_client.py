#!/bin/echo "Do not invoke directly"
#===============================================================================
## @file base_client.py
## @brief SCPI client - base for SocketClient and SerialClient
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Modules relative to install folder
from .symbols import *
from .errors import \
    SCPIDisconnected, SCPICommunicationError, SCPITimeout, \
    SCPIErrorResponse, SCPIInvocationError, SCPISubscribeError

from ..tools.invocation import safe_invoke
from ..tools.parser import CommandParser, ParseError, QUOTE_ATTRIBUTES

### Standard Python modules
import fnmatch
import re
import time
import threading
import queue

#===============================================================================
## @class BaseClient
## @brief Base for `SocketClient` and `SerialClient`, below.

class BaseClient (CommandParser):
    multiLineX      = re.compile(r'<(\w+(?:\.[^>]*)?)>')
    serveraddr      = None

    (LOG_SEND, LOG_RECEIVE, LOG_CONNECT, LOG_HANDSHAKE,
     LOG_PROTOCOL, LOG_MESSAGE, LOG_CB, LOG_CB_EXC) = \
        (LEVEL_TRACE, LEVEL_TRACE, LEVEL_INFO, LEVEL_INFO,
         LEVEL_NOTICE, LEVEL_TRACE, LEVEL_TRACE, LEVEL_WARNING)


    def __init__(self,
                 use_index=True,            # <index> COMMand Args...
                 check_partial_reply=False, # ERRor <partial-command> <-- ...
                 autoconnect=True,          # Automatically (re)connect to server on demand
                 logger=None):              # Callback method for logging: callback(level, message)

        self.autoconnect     = autoconnect
        self.pending         = {}
        self.serverinfo      = {}
        self.log             = logger or self.defaultLogger
        self.receiveThread   = None
        self.is_receiving    = False
        self.is_connected    = False
        self.callbackThread  = None
        self.callbackQueue   = None
        self.isReady         = threading.Event()
        self.commandLock     = threading.RLock()
        self.commandIndex    = 0
        self.use_index       = use_index
        self.partial_reply   = check_partial_reply
        self.instream        = None
        self.outstream       = None

        ### Subscription support
        self.subscriptions   = {}
        self.connecthooks    = []
        self.disconnecthooks = []

    def on_connect(self):
        self.runHooks(self.connecthooks)

    def on_disconnect(self):
        self.is_connected = False
        exception = SCPIDisconnected("Lost Connection to Server")

        for command, responseQueue in self.pending.values():
            responseQueue.put((exception, None, None))

        if self.callbackQueue is not None:
            self.callbackQueue.put(None)

        self.runHooks(self.disconnecthooks)

    def addConnectHook(self, callback, *args, **kwargs):
        self.connecthooks.append((callback, args, kwargs))

    def addDisconnectHook(self, callback, *args, **kwargs):
        self.disconnecthooks.append((callback, args, kwargs))

    def runHooks(self, hooks):
        for callback, args, kwargs in hooks:
            self.safeInvoke(callback, args, kwargs)

    def waitReady(self, timeout=None):
        self.isReady.wait(timeout)

    def defaultLogger(self, level, message):
        logging.log(LOGGING_LEVELS[level], message)


    def writeline(self, text):
        if self.outstream:
            data = text.encode() if isinstance(text, str) else text
            self.outstream.write(data + b'\r\n')
        else:
            raise SCPIDisconnected('Not connected')



    ####################################################################
    ### The following methods receive input from the instrument in a
    ### separate thread

    def startReceiveThread(self):
        if not self.receiveThread:
            self.receiveThread = threading.Thread(target=self.receiveLoop,
                                                  name="receiveThread",
                                                  daemon=True)
            self.receiveThread.start()


    def stopReceiveThread(self, wait=False):
        if (t := self.receiveThread) and t.is_alive():
            self.receiveThread = None
            if wait:
                t.join()


    def receiveLoop(self):
        "Runs in a separate thread to receive input from the instrument"

        assert self.is_connected, "You must connect() before you can invoke receiveLoop()"

        self.log(self.LOG_HANDSHAKE, 'Starting SCPI client receive thread')
        self.is_receiving = True

        while self.receiveThread and self._receive():
            self.isReady.set()

        self.is_receiving = False
        self.receiveThread = None
        self.log(self.LOG_HANDSHAKE, 'Ending SCPI client receive thread')



    def _receive (self):
        try:
            text, parts = self.expandArgs(self.instream)

        except ParseError as e:
            self._processParseError(e)
            return True

        except EOFError as e:
            self.on_disconnect()
            return False

        else:
            if parts:
                self._processParts(text, parts)
            return True


    def _processParts(self, text, parts):
        "Handle input received from instrument"

        option, status, raw = parts.pop(0)

        if status in (OK, NEXT, ERROR):
            return self._processResponse(status, text, parts)

        elif status == MESSAGE:
            return self._processMessage(text, parts)

        elif status == READY:
            return self._processReady(text, parts)

        else:
            self.log(self.LOG_PROTOCOL,
                     'Invalid status word "%s" received from SCPI server: "%s"'%
                     (status, text.strip()))


    def _processParseError(self, e):
        self.log(self.LOG_PROTOCOL, "Failed to parse server output: %s"%(e,))

    def _processReady(self, text, parts):
        "Handle initial READy prompt from IS"

        for option, value, raw in parts:
            self.serverinfo[option] = value


    def _processResponse(self, status, text, parts):
        "Handle a response to a prior command, add to response queue"

        try:
            option, idx, header    = parts.pop(0)
            idx                    = int(idx)
            command, responseQueue = self.pending[idx]


        except KeyError:
            self.log(self.LOG_PROTOCOL,
                     "Received %s response to unknown command index %d: %s"%
                     (status, idx, text.strip()))
            responseQueue = None


        except IndexError:
            self.log(self.LOG_PROTOCOL,
                     'Command index missing in response from SCPI server: "%s"'%
                     (text.strip()))
            responseQueue = None


        except ValueError:
            for (command, responseQueue) in list(self.pending.values()):
                echo  = header
                part  = 0
                while part < len(parts) and (command.strip()+' ').startswith(echo.strip()+' '):
                    option, value, raw = parts[part]
                    echo += raw
                    part += 1

                if (echo.strip()+' ').startswith(command.strip()+' '):
                    del parts[:part-1]
                    break

                elif command.startswith(header) and self.partial_reply:
                    break

            else:
                self.log(self.LOG_PROTOCOL,
                         'Received response to unknown command: "%s"'%(text.strip()))
                responseQueue = None

        if responseQueue:
            response = (status, text, parts)
            responseQueue.put(response)
            return response


    _timeStampX = re.compile(r'^\d+\.\d+$')

    def _processMessage(self, text, parts):
        "Handle a message publication; invoke any subscriber callback methods"

        try:
            option, topic, raw = parts.pop(0)

            option, word, raw = parts[0]
            if self._timeStampX.match(word):
                timestamp = float(word)
                parts.pop(0)
            else:
                timestamp = None

            try:
                option, level, raw = parts[0]
                level = SUBSCRIPTION_LEVELS.index(level.lower())
                parts.pop(0)
            except ValueError as e:
                level = None

        except IndexError:
            self.log(LOG_PROTOCOL,
                     "Missing elements in published message: %r, parts=%s"%
                     (text.strip(), parts))

        else:
            message   = Message(topic, parts, timestamp, level)
            matches   = 0
            callbacks = 0

            for rx, hasformat, records in self.subscriptions.values():
                if rx.match(topic):
                    matches += 1

                    for record in records:
                        callbacks += 1
                        callback, cbargs, staticargs, staticopts, decompose = record

                        args = list(staticargs) + [getattr(message, a) for a in cbargs]
                        opts = dict(staticopts)

                        if decompose:
                            args.extend(message.args)
                            opts.update(message.kwargs)

                        self.log(self.LOG_CB, self.invocation(callback, args, opts))
                        self._callback((callback, args, opts))


            if matches or callbacks:
                self.log(self.LOG_CB,
                         "Found %d subscriber matches "
                         "and dispatched %d callbacks for message topic %r"%
                         (matches, callbacks, message.topic))


    def _callback(self, record):
        if self.callbackThread is None:
            self.callbackQueue  = queue.Queue()
            self.callbackThread = threading.Thread(
                target=self._callbackLoop,
                name="callbackThread",
                daemon=True)
            self.callbackThread.start()

        self.callbackQueue.put(record)


    def _callbackLoop (self):
        while self.is_connected:
            record = self.callbackQueue.get()
            if record:
                safe_invoke(*record)

        self.callbackThread = None
        self.callbackQueue  = None


    ####################################################################
    ### The following methods can be invoked to send commands to and
    ### receive responses or other input from the instrument.

    def send_command(self, command):
        "Send a command to the SCPI server"

        if isinstance(command, (list, tuple)):
            command = self.collapseArgs(command)

        elif isinstance(command, str):
            command = command.rstrip('\r\n')

        else:
            raise TypeError("Invalid command, must be a string, a list of strings, "
                            "or a list of 2-3 string tuples: %r"%(command,))

        with self.commandLock:
            if not self.is_connected:
                raise SCPIDisconnected("Not connected to server")

            self.commandIndex += 1
            self.pending[self.commandIndex] = (command, queue.Queue())

            if self.use_index:
                command = "%s %s"%(self.commandIndex, command)

            try:
                self.log(self.LOG_SEND, self._indent(command, "SEND: ", "send: "))
                self.writeline(command)
            except EnvironmentError as e:
                self.on_disconnect()
                raise SCPICommunicationError(str(e), *e.args)

            return self.commandIndex

    def _indent(self, text, prefix="    ", infix=None):
        infix = "\n" + (prefix, infix)[infix is not None]
        return prefix + infix.join(text.splitlines())


    def _get_response(self, commandIndex, timeout=None, ignoreNext=False):
        try:
            (command, responseQueue) = self.pending[commandIndex]
        except KeyError:
            raise SCPIInvocationError('No such pending command index: %r'%(commandIndex,))

        start = time.time()
        self.log(self.LOG_RECEIVE,
                 "WAIT: %s -timeout=%s -ignoreNext=%s"%
                 (commandIndex, timeout, ignoreNext))

        while timeout is None or time.time() < start+timeout:
            while not self.is_receiving and responseQueue.empty():
                if not self._receive():
                    return

            try:
                status, text, parts = responseQueue.get(True, timeout)

            except queue.Empty:
                pass

            else:
                if isinstance(status, Exception):
                    raise status

                if status != NEXT:
                    del self.pending[commandIndex]

                if status != NEXT or not ignoreNext:
                    return status, text, parts

        else:
            del self.pending[commandIndex]
            raise SCPITimeout("Timeout waiting for SCPI response after %.1fs"%
                              (time.time()-start))



    def receive_response(self, commandIndex,
                         splitResponse=True,
                         splitParts=False,
                         decompose=False,
                         ignoreNext=False,
                         ignoreError=False,
                         timeout=None):
        "Wait for a response to a previously sent command"

        status, text, parts = self._get_response(commandIndex, timeout, ignoreNext)

        if status[:3] == "ERR" and not ignoreError:
            raise SCPIErrorResponse(text, parts)

        elif splitParts:
            return status, parts

        elif decompose:
            args, opts, string = self.decomposeParts(parts)
            return status, args, opts

        elif splitResponse:
            return status, "".join([ raw for opt, arg, raw in parts ]).strip()

        else:
            return text


    def send_receive(self, command,
                     splitResponse=True,
                     splitParts=False,
                     decompose=False,
                     ignoreNext=False,
                     ignoreError=False,
                     timeout=None):

        idx = self.send_command(command)
        return self.receive_response(
            idx,
            splitResponse,
            splitParts,
            decompose,
            ignoreNext,
            ignoreError,
            timeout)

    def profile(self, command, count=1, ignoreNext=False, timeout=None):
        start = time.time()
        for n in range(count):
            self.sendReceive(command, True, ignoreNext, timeout)
        return (time.time() - start) / count


    def decomposeParts(self, parts):
        args, opts, strings = [], {}, []

        for opt, value, raw in parts:
            if opt:
                opts[opt] = value
            else:
                args.append(value)

            strings.append(raw)

        return args, opts, "".join(strings).strip()


    ####################################################################
    ### The following methods provide subscription/callback

    _formatWithLevel = "$topic$ $timestamp$ $level$ $message$"


    def subscribe(self, topic, callback, sendSubscribeCommand=False,
                   regex=False, future=None, level=None, cbargs=None,
                   withTimestamp=False, withLevel=False, withFormat=None,
                   splitParts=False, decompose=False,
                   staticargs=(), first=False, **staticopts):

        """Subscribe to a topic, and register a callback method"""
        assert callable(callback), \
               'The supplied callback handler is not callable'

        if not cbargs:
            cbargs = (ARG_TOPIC,)

            if splitParts:
                cbargs += (ARG_PARTS,)

            elif not decompose:
                cbargs += (ARG_MESSAGE,)

            if withTimestamp:
                cbargs += (ARG_TIMESTAMP,)

            if withLevel:
                cbargs += (ARG_LEVEL,)
                if withFormat is None:
                    withFormat = True

        else:
            for a in cbargs:
                if not a in MESSAGE_ARGS:
                    raise SCPIInvocationError("Invalid callback argument %r in "
                                              "message subscription on topic %r, callback %s()"%
                                              (a, topic, callback.__name__))

        if regex:
            rx = re.compile(topic, re.I)
        else:
            rx = re.compile(fnmatch.translate(topic), re.I)

        record = (callback, cbargs, staticargs, staticopts, decompose)

        try:
            rx, hasFormat, records = self.subscriptions[topic.lower()]

            if hasFormat or not withFormat:
                sendSubscribeCommand = False
                withFormat = hasFormat

            if first:
                records.insert(0, record)
            else:
                records.append(record)

        except KeyError:
            records = [record]

        self.subscriptions[topic.lower()] = rx, withFormat, records

        if sendSubscribeCommand:
            parts     = ["SUBScribe"]
            if future is not None:
                parts.append(('future', future))
            if level is not None:
                parts.append(('level', SUBSCRIPTION_LEVELS[level]))
            if regex:
                parts.append(('regex', True))

            if withFormat:
                parts.append(('format', self._formatWithLevel))
            else:
                parts.append(('timestamp', True))

            parts.append(topic)
            self.sendReceive(parts)


    def unsubscribe(self, topic, callback, ignoreMissing=False, sendUnsubscribeCommand=True):
        """Subscribe to a topic, and register a callback method"""

        foundTopic    = False
        callbacks     = 0

        ### First, look through our own subscription records, and remove
        ### any matching references to callback

        for (candidate, subscription) in list(self.subscriptions.items()):
            if candidate == topic.lower():
                rx, hasFormat, records = subscription
                for record in records[::-1]:
                    cb = record[0]
                    if cb == callback:
                        records.remove(record)
                        callbacks += 1

                if records:
                    foundTopic = True

                elif self.isConnected and sendUnsubscribeCommand:
                    self.sendReceive(("UNSubscribe", "-ignoreMissing", topic))
                    del self.subscriptions[candidate]


        ### If no matches were found, try unsubscribing anyway; we may have
        ### been subscribed to a "wildcard" topic (e.g. "Session-*") and now
        ### are unsubscribing from a more specific one (e.g. "Session-1")

        if sendUnsubscribeCommand and callbacks == 0:
            if foundTopic:
                if not ignoreMissing:
                    raise SCPISubscribeError("Callback %r not is not registered for topic subscription %r"%
                                             (callback.__name__, topic))
            else:
                try:
                    self.sendReceive(("UNSubscribe", topic))
                except SCPIErrorResponse:
                    if not ignoreMissing:
                        raise

        return callbacks


    def publish(self, topic, message, raw=True):
        topic = self.protectString(topic)

        if isinstance(message, list):
            message = self.collapseArgs(message)

        elif isinstance(message, dict):
            message = self.collapseArgs(list(message.items()))

        elif isinstance(message, str):
            message = self.protectString(message)

        return self.sendReceive('PUBLish %s %s'%(topic, message))


    def getSubscriptions(self, callback, *args, **kwargs):
        subscriptions = []
        for rx, hasformat, records in self.subscriptions.values():
            for record in records:
                cb, cbargs, staticargs, staticopts, decompose = record
                if ((cb == callback) and
                    (not args or args==staticargs) and
                    (not kwargs or kwargs==staticopts)):
                    subscriptions.append(rx.pattern)
        return subscriptions

