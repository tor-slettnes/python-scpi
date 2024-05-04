#!/bin/echo "Do not invoke directly"
#===============================================================================
## @file message.py
## @brief SCPI client - holds a message published from the server
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from .symbols import LEVEL_DEBUG
from ..tools.parser import CommandParser, QUOTE_ATTRIBUTES

class Message (CommandParser):
    def __init__ (self, topic, parts, timestamp=None, level=LEVEL_DEBUG, quoting=QUOTE_ATTRIBUTES):
        self.topic     = topic or ''
        self.timestamp = timestamp
        self.level     = level
        self.quoting   = quoting
        self.parts     = parts

    @property
    def text(self):
        try:
            return self._text
        except AttributeError:
            self._text = ' '.join([_f for _f in self.args if _f])
            return self._text

    @property
    def message(self):
        try:
            return self._message
        except AttributeError:
            self._message = self.collapseArgs(self.parts, tag='message', quoting=self.quoting)
            return self._message

    @property
    def args(self):
        try:
            return self._args
        except AttributeError:
            self._args = [ part[1] for part in self.parts if not part[0] ]
            return self._args

    @property
    def kwargs(self):
        try:
            return self._kwargs
        except AttributeError:
            self._kwargs = dict([part[:2] for part in self.parts if part[0]])
            return self._kwargs

    @property
    def raw(self):
        try:
            return self._raw
        except AttributeError:
            parts = [str(value)
                     for value in (MESSAGE, self.topic, self.timestamp, self.level)
                     if value]
            parts.extend(self.parts)
            self._raw = self.collapseArgs(parts, tag='message', quoting=self.quoting)
            return self._raw


