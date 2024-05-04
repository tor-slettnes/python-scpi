#===============================================================================
## @file handler_session.py
## @brief SCPI session to handle published messages
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .detached_session import DetachedSession
from .symbols import Context
from ...tools.publication import \
    subscribe, clearSubscriptions, getSubscriptionRecords

## Standard Python modules
import threading, io

class HandlerSession (DetachedSession):
    '''
    Session to handle messages
    '''

    messageThread = None

    def addMessageHandler (self, handle, mask, future, createMissing, ignoreMissing,
                           level, regex, queuesize, filters, action, scope, preempt):
        self.messageQueue = Queue(maxsize=queuesize)
        rxfilters = self.compiledFilters(filters, regex)
        subscribe(mask, level, self._messageReceiver,
                               args=(rxfilters, action, scope, preempt), regex=regex,
                               future=future, createMissing=createMissing,
                               ignoreMissing=ignoreMissing)

        name = '|'.join((threading.currentThread().name, "MessageHandler-"+handle))
        thread = self.messageThread = Thread(target=self._messageHandler,
                                             name=name,
                                             args=(self.messageQueue,),
                                             daemon=True)
        thread.start()

    def clearSubscriptions (self):
        if self.messageQueue:
            count = clearSubscriptions(self._messageReceiver)
            self.messageQueue.cancel()

    def waitForCompletion (self):
        if self.messageThread != currentThread():
            self.messageThread.join()

    def getHandlerRecord (self):
        records = getSubscriptionRecords(self._messageReceiver)
        try:
            mask, level, callback, args = records[0]
        except IndexError as e:
            pass
        else:
            rxfilters, action, scope, preempt = args
            return mask, level, rxfilters, action, scope, preempt

    def _messageReceiver (self, message, rxfilters, action, scope, preempt):
        if self.matchingMessage(message, rxfilters):
            self.messageQueue.put((message, rxfilters, action, scope))
            if preempt:
                raise StopIteration

    def _messageHandler (self, queue):
        try:
            while True:
                (message, rxfilters, action, scope) = queue.get()
                text = message.format(format=action)
                self.handleInput(io.StringIO(text), Context(self, scope, data=message))
        except Empty:
            pass

    def matchingMessage (self, message, rxfilters):
        for key, rx in list(rxfilters.items()):
            try:
                if key is None:
                    value = message.text
                else:
                    value = message[key]
            except KeyError:
                return False
            else:
                if not rx.match(value or ""):
                    return False
        else:
            return True

    def compiledFilters (self, filters, regex=False):
        result = {}
        for option, mask in list(filters.items()):
            if not regex:
                mask = fnmatch.translate(mask)

            result[option] = re.compile(mask, re.I|re.S)

        return result

