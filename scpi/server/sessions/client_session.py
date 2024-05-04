#===============================================================================
## @file client_session.py
## @brief SCPI session for connected clients
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base_session import BaseSession
from .symbols import Triggers, AccessLevels, GUEST
from ..exceptions import scpiException, \
     Exc, Error, RunError, InternalError, ExternalError, \
     NextReply, NextCommand, Break, ReturnValue, ReturnCall

from ...tools.parser import parser
from ...tools.publication import debug, info, DEBUG, \
    subscribe, unsubscribe, clearSubscriptions, \
    getSubscriptionMasks, getSubscribedTopics

## Standard Python modules
import sys, threading


### Response words
statuswords = READY, OK, NEXT, WARNING, ERROR, MESSAGE = \
              "READy", "OK", "NEXT", "WARNing", "ERRor", "MESSage"


class ClientSession (BaseSession):
    '''
    Handle client connections
    '''
    class ExclusiveAccessGiven (RunError):
        '''Exclusive %(level)s access is already given to %(client)s'''

    class AccessGiven (RunError):
        '''%(level)s access is already given to %(client)s'''

    def __init__ (self, instream, outstream, **argmap):
        BaseSession.__init__(self, instream, **argmap)
        self.outstream  = outstream
        self.parent     = None

        self.authLimit   = self.interfaceLimit('authLimits')
        self.accessLimit = self.interfaceLimit('accessLimits')
        self.accessLevel = min(self.interfaceLimit('defaultAccess'),
                               self.nonExclusiveLimit())

    def cleanup (self, context, *cleanupargs):
        self.clearSubscriptions()
        return BaseSession.cleanup(self, context, *cleanupargs)

    def handleInput (self, instream, context):
        while True:
            reply = exception = None
            try:
                commandtext, index, command, args = self.getCommand(instream, context)
                if command is None:
                    continue

            except EOFError:
                break

            except self.ParseError as e:
                self.respondError(e.expression[:e.pos].rstrip(), e)

            else:
                self.debug('C: %s'%commandtext.rstrip().replace('\n', '\nc: '))
                context.update(text=commandtext, index=index)
                runargs = (context, command, args)
                self.handleExceptions(context, self._run, runargs, {}, debug)


    def handleExceptions (self, context, func, args=(), argmap={}, notify=info, asynchronous=False):
        echo  = context.index or context.text.strip()
        job   = context, threading.currentThread(), func, args, argmap, asynchronous

        self.addJob(job)
        try:
            func(*args, **argmap)
            self.respondOK(echo, context.getOutputs(alwaysNamed=False))

        except NextCommand as e:
            # Nested NextCommand exceptions are caught in runStream();
            # we only see this when invoked directly in ClientSession.
            self.respondOK(echo)

        except NextReply as e:
            if not asynchronous:
                self.respondNext(echo)
            self.startThread(context, e.leaf, e.method, e.methodArgs, e.methodKwargs, notify)

        except Break as e:
            self.respondOK(echo)

        except ReturnValue as e:
            self.respondOK(echo, e.args)

        except ReturnCall as e:
            # Nested ReturnCall exceptions are caught in runParts();
            # we only see this when invoked directly in ClientSession.
            leaf, method, args, argmap = e.args
            self.respondOKWithCallback(echo, method, args, argmap)

        except Exc as e:
            self.logException(e, context.text.strip())
            self.respondError(echo, e)

        except Exception as e:
            exception = scpiException(e, sys.exc_info(), (func, args, argmap))
            self.logException(exception, context.text.strip())
            self.respondError(echo, exception)

        finally:
            self.finishJob(job)



    #===========================================================================
    ### Responses to client

    def respondOK (self, echo, parts=()):
        words = [OK, echo]
        if parts:
            words.extend(parser.collapseParts(parts, tag='reply'))
        output = ' '.join(words) + '\n'
        self.sendOutput(output)

    def respondOKWithCallback (self, echo, function, args, argmap):
        output = ' '.join((OK, echo))
        self.sendOutput(output, function, args, argmap)

    def respondNext (self, echo):
        output = ' '.join((NEXT, echo)) + '\n'
        self.sendOutput(output)

    def respondError (self, echo, error):
        response = error.format()
        output = ' '.join((ERROR, echo, error.format())) + '\n'
        self.sendOutput(output)

    def processMessage (self, message, messageFormat, includeSession):
        if includeSession or message.topic != self.debugTopic:
            text = message.format(messageFormat)
            self.sendMessage(text)


    #===========================================================================
    ### Notification support

    def notify (self, _notifyLevel, _trigger, *items, **properties):
        parts = [Triggers[_trigger]]
        parts.extend([_f for _f in items if _f])
        parts.extend([(k,v) for (k,v) in list(properties.items()) if v])
        self.publish(self.debugTopic, parts, level=_notifyLevel, literaltag=None)

    #===========================================================================
    ### Client input/output

    def sendReady (self, *items, **properties):
        items = [READY] + list(items) + list(properties.items())
        text  = parser.collapseArgs(items, tag=None)
        self.sendOutput(text+"\n")

    def sendMessage (self, *text):
        output = ' '.join((MESSAGE,) + text) + '\n'
        self.send(output)

    def sendOutput (self, text, *callback):
        self.send(text.replace('\n', '\r\n'), callback)
        self.debug("S: "+text.rstrip().replace("\n", "\ns: "))

    def send (self, text, callback=None):
        try:
            if callback:
                prefix   = '%s <quote.output>\n'%(text,)
                postfix  = '</quote.output>\n'
                function, args, argmap = callback
                self.outstream.write(prefix.encode())
                try:
                    function(self.outstream, *args, **argmap)
                except Exception as e:
                    self.outstream.write(postfix.encode())
                    error   = InternalError(e, sys.exc_info(), (function.__name__, args, argmap))
                    message = error.format(showContext=True)
                    self.warning("Exception in output callback: %s"%(message,))
                else:
                    self.outstream.write(postfix.encode())
            else:
                self.outstream.write(text.encode())

        except EnvironmentError as e: # includes socket.error
            error   = ExternalError(e)
            message = error.format(showContext=True)
            self.warning("Failed to send output to %s: %s"%(self.description, message))
            self.close()

    #===========================================================================
    ### PUBLish/SUBScribe support

    def subscribe (self, topic, level, messageFormat, future,
                   createMissing, ignoreMissing, regex, includeSession):

        subscribe(topic, level, self.processMessage,
                  args=(messageFormat, includeSession),
                  future=future,
                  createMissing=createMissing,
                  ignoreMissing=ignoreMissing,
                  regex=regex)

    def unsubscribe (self, topic):
        return unsubscribe(topic, self.processMessage)

    def clearSubscriptions (self):
        clearSubscriptions(self.processMessage)

    def getSubscriptions (self, future=False):
        if future:
            return getSubscriptionMasks(self.processMessage)
        else:
            return getSubscribedTopics(self.processMessage)

    #===========================================================================
    ### Access Control

    def interfaceLimit (self, limittype):
        raise NotImplementedError("ClientSession subclass %s must implement interfaceLimit()"%
                                  (type(self).__name__,))

    def nonExclusiveLimit (self):
        if BaseSession.exclusive in (self, None):
            return self.accessLimit
        else:
            return min(self.accessLimit, max(GUEST, BaseSession.exclusive.accessLevel-1))

    def setAccessLevel (self, level, exclusive=False, stealth=False):
        if (not stealth and
            not BaseSession.exclusive in (self, None) and
            (exclusive or (level >= BaseSession.exclusive.accessLevel))):
            raise self.ExclusiveAccessGiven(level=BaseSession.exclusive.getLevelName().lower(),
                                            client=BaseSession.exclusive.description)

        elif exclusive:
            for othersession in self.getInstances(ClientSession):
                if (othersession != self) and \
                   (othersession.accessLevel >= level) and \
                   (not othersession.stealthAccess):
                    raise self.AccessGiven(level=othersession.getLevelName(),
                                           client=othersession.description)

        BaseSession.setAccessLevel(self, level, exclusive, stealth)

        self.notify(DEBUG, T_ACCESS,
                    session=self.sessionid,
                    level=AccessLevels[self.accessLevel],
                    stealth=str(stealth),
                    exclusive=str(BaseSession.exclusive is self))

    def getExclusiveFlag (self):
        return BaseSession.exclusive == self
