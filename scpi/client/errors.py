#!/bin/echo "Do not invoke directly"
#===============================================================================
## @file __init__.py
## @brief SCPI client - base for SocketClient and SerialClient
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

import re

class SCPIError (Exception):

    def __init__ (self, message, *args, **kwargs):
        Exception.__init__(self, message)
        self.message     = message
        self.args        = args
        self.attributes  = kwargs

    def __str__ (self):
        return str(self.message)

    def __repr__ (self):
        return str(self.message)


class SCPICommunicationError (SCPIError):
    pass

class SCPITimeout (SCPIError):
    pass

class SCPISubscribeError (SCPIError):
    pass

class SCPIInvocationError (SCPIError):
    pass

class SCPIAlreadyConnected (SCPIError):
    pass

class SCPIDisconnected (SCPIError):
    pass


class SCPIErrorResponse (SCPIError):
    _errorCodeX = re.compile(r"^\[([\w\.]+)\]$")

    def __init__ (self, text, parts):
        SCPIError.__init__(self, text)

        attributes = {}
        code       = None
        message    = None

        for option, value, raw in parts:
            if raw.startswith("-->"):
                message = []

            elif message is not None:
                message.append(raw)

            elif option:
                attributes[option] = value

            elif self._errorCodeX.match(value):
                code = value[1:-1]

            else:
                message = [ raw ]

        self.text = text
        self.code = code
        self.attributes = attributes
        self.message = "".join(message)


    def __repr__(self):
        return self.text.strip()


class SCPIUnknownResponse (SCPIError):
    pass


