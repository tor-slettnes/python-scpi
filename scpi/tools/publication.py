#===============================================================================
## @file publication.py
## @brief General purpose pub/sub support
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Modules relative to install path
from .parser import parser, QUOTE_ATTRIBUTES, QUOTE_NEVER
from .timeformat import Time

### Standard Python modules
from logging import getLogger, Handler
from threading import currentThread

import re
import fnmatch
import sys

class SubscriptionError (Exception):
    pass

class NoSuchTopic (SubscriptionError):
    def __init__ (self, topic, *args, **kwargs):
        Exception.__init__(self,
                           'No such message topic exists: "%s"'%(topic,),
                           *args, **kwargs)
        self.topic = topic

class RegExError (SubscriptionError):
    pass



LogLevels = ('Trace', 'Debug', 'Info', 'Notice', 'Warning', 'Error')
(TRACE, DEBUG, INFO, NOTICE, WARNING, ERROR) = list(range(len(LogLevels)))

MinSubscriptionLevel = len(LogLevels)
DefaultLogLevel      = DEBUG


FormatSpecs = {
    "timestamp"   : lambda msg: "%.3f"%(msg.timestamp,),

    "utc"         : lambda msg: Time(msg.timestamp).format("%F %T%.3", local=False),
    "utcdate"     : lambda msg: Time(msg.timestamp).format("%F", local=False),
    "utctime"     : lambda msg: Time(msg.timestamp).format("%T%.3", local=False),

    "utcyear"     : lambda msg: Time(msg.timestamp).format("%Y", local=False),
    "utcmonth"    : lambda msg: Time(msg.timestamp).format("%m", local=False),
    "utcday"      : lambda msg: Time(msg.timestamp).format("%d", local=False),
    "utchour"     : lambda msg: Time(msg.timestamp).format("%H", local=False),
    "utcminute"   : lambda msg: Time(msg.timestamp).format("%M", local=False),
    "utcsecond"   : lambda msg: Time(msg.timestamp).format("%S", local=False),

    "local"       : lambda msg: Time(msg.timestamp).format("%F %T%.3", local=True),
    "localdate"   : lambda msg: Time(msg.timestamp).format("%F", local=True),
    "localtime"   : lambda msg: Time(msg.timestamp).format("%T%.3", local=True),

    "localyear"   : lambda msg: Time(msg.timestamp).format("%Y", local=True),
    "localmonth"  : lambda msg: Time(msg.timestamp).format("%m", local=True),
    "localday"    : lambda msg: Time(msg.timestamp).format("%d", local=True),
    "localhour"   : lambda msg: Time(msg.timestamp).format("%H", local=True),
    "localminute" : lambda msg: Time(msg.timestamp).format("%M", local=True),
    "localsecond" : lambda msg: Time(msg.timestamp).format("%S", local=True),

    "ms"          : lambda msg: Time(msg.timestamp).format("%.3"),
    "tzname"      : lambda msg: Time(msg.timestamp).format("%Z"),
    "tzoffset"    : lambda msg: Time(msg.timestamp).format("%z"),
    "timezone"    : lambda msg: Time(msg.timestamp).format("%z"),

    "level"       : lambda msg: LogLevels[msg.level],
    "level#"      : lambda msg: str(level),

    "thread"      : lambda msg: currentThread().name,

    "topic"       : lambda msg: msg.topic,
    "message"     : lambda msg: msg.message,
    "text"        : lambda msg: msg.text,
    "args"        : lambda msg: msg.args,
    "kwargs"      : lambda msg: msg.kwargs,
    None          : lambda msg: "{invalid}"
    }


class Message (dict):
    defaultFormat = "$topic$ $timestamp$ $message$"

    _formatExp           = re.compile(r'(\$([a-z#]*)(:([+-]?\d+)?)?\$)')
    #_formatExp           = re.compile(r'(\$\{([a-z#]*)(:([+-]?\d+)?)?\})')


    def __init__ (self, topic, content, timestamp=None, level=None, quoting=None, literaltag='message'):
        self.topic     = topic or ''

        if timestamp is None:
            timestamp = Time().timestamp
        self.timestamp = timestamp

        if level is None:
            level = getLevel(self.topic, ignoreMissing=True)
        self.level      = level

        self.quoting    = (quoting, QUOTE_ATTRIBUTES)[quoting is None]
        self.literaltag = literaltag

        if isinstance(content, str):
            self.parts = [ (None, content) ]
            self._text = content
        elif isinstance(content, (list, tuple)):
            self.parts = [ ((None, part), part)[isinstance(part, (tuple, list))]
                            for part in content ]
        elif isinstance(content, dict):
            self.parts = list(content.items())

        else:
            self.parts = []

    @property
    def text (self):
        try:
            return self._text
        except AttributeError:
            self._text = ' '.join([_f for _f in self.args if _f])
            return self._text

    @property
    def message (self):
        try:
            return self._message
        except AttributeError:
            self._message = parser.collapseArgs(self.parts, tag=self.literaltag, quoting=self.quoting)
            return self._message

    @property
    def args (self):
        try:
            return self._args
        except AttributeError:
            self._args = [ part[1] for part in self.parts if not part[0] ]
            return self._args

    @property
    def kwargs (self):
        try:
            return self._kwargs
        except AttributeError:
            self._kwargs = dict([part[:2] for part in self.parts if part[0]])
            return self._kwargs


    def __getitem__ (self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            try:
                return self.kwargs[key]
            except KeyError:
                return FormatSpecs[key](self)

#    def __setitem__ (self, key, value):
#        self.kwargs[key] = value

#    def pop (self, key, *default):
#        return self.kwargs.pop(key, *default)

    def format (self, format=defaultFormat):
        text  = format
        match = self._formatExp.search(format)
        parts = []
        end   = 0

        while match:
            whole, token, suffix, just = match.groups()
            parts.append(format[end:match.start(1)])
            method = FormatSpecs.get(token, FormatSpecs[None])
            value = method(self)

            if just:
                just  = int(just)
                value = "%*s"%(just, value[:abs(just)])

            parts.append(value)
            end   = match.end(1)
            match = self._formatExp.search(format, end)

        parts.append(format[end:])
        return ''.join(parts)


ALL = '*'

_subscriptions       = {}
_delayedMessages     = []
_futureFilters       = []
_wildcardMagic       = re.compile('[*?[]')

def addTopic (topic, level=DEBUG):
    t = topic.lower()

    try:
        (oldTopic, oldLevel, subscribers) = _subscriptions[t]
    except KeyError:
        subscribers = []

        ### Add subscribers from existing 'future' records.
        ### (The future has arrived)
        for rx, records in _futureFilters:
            if rx.match(topic):
                subscribers.extend(records)

    _subscriptions[t] = record = (topic, level, subscribers)
    return record


def deleteTopic (topic, ignoreMissing=False):
    try:
        del _subscriptions[topic.lower()]
    except KeyError:
        if not ignoreMissing:
            raise NoSuchTopic(topic)


def _getRecords (pattern, level, sort=True, regex=False):
    records = list(_subscriptions.items())
    if sort:
        records.sort()

    rx = _compile(pattern, regex)

    return [record
            for topic, record in records
            if (record[1] >= level) and rx.match(topic)]


def getTopics (mask='*', level=0, regex=False):
    return [ topic for topic, level, subscriptions in _getRecords(mask, level, regex) ]


def topicExists (topic):
    return topic.lower() in _subscriptions


def getLevel (topic, ignoreMissing=False, default=DEBUG):
    try:
        topic, level, subscribers = _subscriptions[topic.lower()]
    except KeyError:
        if not ignoreMissing:
            raise NoSuchTopic(topic)
        return default
    else:
        return level

def getSubscribers (topic, level=None, ignoreMissing=False, createMissing=False):
    t = topic.lower()

    try:
        topic, defaultLevel, subscribers = _subscriptions[t]

    except KeyError:
        if createMissing:
            topic, defaultLevel, subscribers = addTopic(topic, (level, DEBUG)[level is None])

        elif ignoreMissing:
            defaultlevel = DEBUG
            subscribers  = []

        else:
            raise NoSuchTopic(topic)


    if level is None:
        level = defaultLevel

    records = [ (cb, args)
                for mask, cutoff, cb, args in subscribers[:]
                if cutoff <= level ]

    return topic, level, records


def publish(topic,
            content,
            timestamp=None,
            level=None,
            quoting=QUOTE_ATTRIBUTES,
            literaltag='message',
            trigger=None,
            createMissing=True):

    if level is None or level >= MinSubscriptionLevel:
        message = Message(topic, content, timestamp, level, quoting, literaltag)
        publishMessage(message, trigger, createMissing)


def publishMessage(
        message,
        trigger=None,
        createMissing=True):

    if message.level >= MinSubscriptionLevel:
        topic, level, subscribers = \
            getSubscribers(message.topic, message.level, createMissing=createMissing)

        if trigger:
            _delayedMessages.append((trigger.lower(), message, subscribers))
        else:
            _publishMessage(message, subscribers)

def _publishMessage (message, subscribers):
    try:
        for callback, args in subscribers:
            callback(message, *args)
    except StopIteration:
        pass


def publishPending (trigger=None):
    remaining = []
    trigger   = (trigger or '').lower()

    count = 0
    for t, m in _delayedMessages:
        if trigger in ('', t):
            _publishMessage(*m)
            count += 1
        else:
            remaining.append((t, m))

    _delayedMessages[:] = remaining
    return count


def getTriggers ():
    return [ trigger for trigger, message in _delayedMessages ]


def getPending (trigger=None):
    if trigger is None:
        return _delayedMessages

    else:
        trigger = trigger.lower()
        return [ rec for t, rec in _delayedMessages if t == trigger ]

def addRecord (records, record, position=None):
    if position is None:
        records.append(record)
    else:
        records.insert(position, record)

def subscribe (mask, level, callback, args=(), ignoreMissing=False, createMissing=False, future=None, regex=False):
    #print("%s: START subscribe(mask=%r, level=%r, callback=%r, args=%r, ignoreMissing=%r, future=%r, regex=%r)"%
    #      (time(), mask, level, callback, args, ignoreMissing, future, regex))
    rx     = _compile(mask, regex)
    record = (mask, level, callback, args)

    unsubscribe(mask, callback, args, regex)
    iswildcard = regex or (_wildcardMagic.search(mask) is not None)

    if future is None:
        future = iswildcard

    count = 0
    for name, subscriptiondata in list(_subscriptions.items()):
        if rx.match(name):
            t, l, subscribers = subscriptiondata
            subscribers.append(record)
            count += 1

    if not count:
        if createMissing and not iswildcard:
            t, l, subscribers = addTopic(name)
            subscribers.append(record)
            count += 1
        elif not future and not ignoreMissing:
            raise NoSuchTopic(mask)

    if count:
        global MinSubscriptionLevel
        if level < MinSubscriptionLevel:
            MinSubscriptionLevel = level

    if future:
        for x, records in _futureFilters:
            if x == rx:
                records.append(record)
                break
        else:
            _futureFilters.append((rx, [record]))

    return count


def unsubscribe (mask, callback, args=None, regex=False):
    rx    = _compile(mask, regex)
    count = 0
    lists = []

    for topic, level, subscribers in list(_subscriptions.values()):
        if rx.match(topic):
            lists.append(subscribers)

    for rx2, records in _futureFilters:
        if rx2.pattern == rx.pattern:
            lists.append(records)

    return _removeSubscriptions(lists, callback, args)


def clearSubscriptions (callback):
    lists = [ subscribers for t, l, subscribers in list(_subscriptions.values()) ]
    lists.extend([record for (rx, record) in _futureFilters])

    return _removeSubscriptions(lists, callback)


def _removeSubscriptions (lists, callback, args=None):
    count = 0
    for records in lists:
        for entry in _callbackEntries(records, callback, args):
            try:
                records.remove(entry)
            except ValueError:
                pass
            else:
                count += 1

    ### Prune empty records from future subscription map
    filters = [(rx, records) for (rx, records) in _futureFilters if records]
    _futureFilters[:] = filters
    return count


def getSubscriptionMasks (callback):
    masks = []
    for rx, records in _futureFilters:
        for mask, level, cb, cbargs in _callbackEntries(records, callback):
            masks.append(mask)

    return masks


def getSubscribedTopics (callback):
    topics = []
    for key, record in sorted(_subscriptions.items()):
        topic, defaultLevel, subscribers = record
        if len(_callbackEntries(subscribers, callback)) > 0:
            topics.append(topic)

    return topics


def getSubscriptionRecords (callback, future=None):
    subscriptions = []
    if future is not True:
        for rx, records in _futureFilters:
            subscriptions.extend(_callbackEntries(records, callback))

    if future is not False:
        for topic, level, subs in list(_subscriptions.values()):
            subscriptions.extend(_callbackEntries(subs, callback))

    return subscriptions


def _callbackEntries (records, callback, args=None):
    return [r for r in records[:] if _matchingCallback(r, callback, args)]


def _matchingCallback (record, callback, args=None):
    mask, level, cb, cbargs = record
    return (cb == callback) and (args in (cbargs, None))


def log (text, level):
    publish(LogLevels[level], text, level=level, literaltag=None)

def trace (text):
    log(text, TRACE)

def debug (text):
    log(text, DEBUG)

def info (text):
    log(text, INFO)

def notice (text):
    log(text, NOTICE)

def warning (text):
    log(text, WARNING)

def error (text):
    log(text, ERROR)


def _compile (pattern, regex=False):
    try:
        if regex:
            return re.compile(pattern, re.I)
        else:
            return re.compile(fnmatch.translate(pattern), re.I)
    except Exception as e:
        raise RegExError(e)


def _printmessage (message, format):
    sys.stdout.write(message.format(format)+'\n')
    sys.stdout.flush()


def setDefaultLogLevel (level):
    global DefaultLogLevel
    DefaultLogLevel = level

def getDefaultLogLevel (level):
    return DefaultLogLevel

def initlogging (level, format):
    subscribe('*', level, _printmessage, (format,), future=True)


class MessageHandler (Handler):
    def handle (self, record):
        topic = record.levelname
        timestamp = record.created
        publish(record.levelname.capitalize(),  ### Debug, Info, Warning, Error
                record.getMessage().strip(),
                timestamp=record.created)


def startLogCapture ():
    handler = MessageHandler()

    logger = getLogger()
    logger.setLevel(0)
    logger.addHandler(handler)


for level, topic in enumerate(LogLevels):
    addTopic(topic, level=level)

startLogCapture()
