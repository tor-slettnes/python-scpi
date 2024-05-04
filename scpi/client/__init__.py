#!/bin/echo "Do not invoke directly"
#===============================================================================
## @file __init__.py
## @brief SCPI client - base for SocketClient and SerialClient
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

"""SCPIClient class and associated symbol definitions.

This module provides client support for communicating with the
instrument server.


========================
CONNECTING TO THE SERVER
========================

A typical connection scenario would be:

    from scpi.client import SocketClient

    client = SocketClient()
    client.connect(("localhost", 7000), timeout=15)

By default, a new receiver thread is launched on connect() to handle
input from the server, and from there to dispatch appropriate response
actions or invoke callbacks.  To prevent this, use "threaded=False".
You then have two options:

 * You can spawn your own receiver thread, and from there invoke
   "receiveLoop()" directly.  This has the same effect as letting the
   conect() method spawn one, but may be useful if you are using a
   different threading model in your application (e.g. from the
   "multiprocessing" module, or if you are using PyQt).

   In this case, 'receiveLoop()' must be invoked AFTER 'connect()'.

 * You can omit threading altogether, in which input from the server
   will only be processed when you invoke the "receiveResponse()"
   method (directly, or indirectly via "sendReceive()"); see below.
   This means that responses to asynchronous commands as well as
   message publications will only be processed during those times.



================
SENDING COMMANDS
================

To send a single command to the server, use:

    index = client.sendCommand(<command>)

where <command> is either
  - a single string, with argument values quoted as needed, or
  - separated into a list/tuple of individual arguments, with each
    argument comprised either of a string or a 2+-element tuple
    representing an option name and option value.

The following are equivalent:

    - "COMMAND -option='some value' \"argument one\" <<<argument\ntwo>>>"
    - ("COMMAND", "-option='some value'", "argument one", "argument\ntwo")
    - [ "COMMAND", ('option', 'some value'), 'argument one', 'argument\ntwo' ]



The return value is an index, which will then be supplied as argument
to the "receiveResponse()" method, below.


===================
RECEIVING RESPONSES
===================

To receive the server response to a previously-sent command, you can choose
one of the following invocations of "receiveResponse()":

    rawresponse = scpi.receiveResponse(index, splitResponse=False)

    status, reply = scpi.receiveResponse(index, splitResponse=True)

    status, parts = scpi.receiveResponse(index, splitParts=True)

    status, outputs, keywords = scpi.receiveResponse(index, decompose=True)

where:

    rawresponse is the raw text received from the server, including
                the command index (or text) from the original command

    status      is "OK" or "NEXT", with the latter indicating that the
                command is now running asynchronously (in the background)
                (use "receiveResponse(...ignoreNext=True)" or else invoke
                "receiveResponse()" again to wait for final completion)

    reply       is the reply portion of the server response, as a single
                unparsed string

    parts       is a list of 3-element tuples corresponding to outputs
                returned by the server, each made up of
                  - An option name (or None if it is an unnamed output)
                  - An option value, with substitutions performed
                  - A "raw" string containing the original unparsed argument

    outputs     is a list of unnamed (positional) response words returned
                from the server

    keywords    is a dictionary containing any named response words from
                the server.


A convenience method, "sendReceive()", combines "sendCommand()" and
"receiveResponse()" into a single call:

   status, outputs, keywords = sendReceive(command, **options)


EXAMPLES:

   scpi.sendReceive("VERSion?", splitResponse=False)
   --> "OK 1 -InstrumentServer:Build=42 -InstrumentServer:Version=0.0.5 -ASCB=8812"

   scpi.sendReceive("VERSion?", splitResponse=True)
   --> ("OK",
        "-InstrumentServer:Build=42 -InstrumentServer:Version=0.0.5 -ASCB=8812")

   scpi.sendReceive("VERSion?", splitParts=True)
   --> ("OK",
        [ ("InstrumentServer:Build", "42", "-InstrumentServer:Build=42 "),
          ("InstrumentServer:Version", "0.0.5", "-InstrumentServer:Version=0.0.5 "),
          ("ASCB", "8812", "-ASCB=8812") ])


   scpi.sendReceive("VERSion?", decompose=True)
   --> ("OK",
        [],
        {"InstrumentServer:Version": "0.0.5", "InstrumentServer:Build": "42", "ASCB": "8812" })



=======================
SUBSCRIBING TO MESSAGES
=======================

Asynchronous events are published by the Instrument Server as
messages, organized by "Topic".  For instance, many qPCR instruments
publish various temperatures on the "Temperature" topic once per
second, and progress during a run on the "Run" topic.

To subscribe to such messages, use:
     scpi.subscribe(topic, callback, ...)

The topic may also contain wildcard characters ("?" to match any
single character and "*" to match anything):

    scpi.subscribe(r"Session-*", callback, ...)

Once a message is received from the server, the corresponding callback
is invoked -- by default, as follows:

    callback(<topic>, <text>)

where <topic> is the messsage topic supplied by the server (which may
differ from what was subscribed to in case wildcards were used, and
also by uppercase/lowercase letters).

However, several options exist to control what arguments are supplied
in the callback:

   - Use "withTimestamp=True" to include a timestamp (seconds since epoch,
     with millisecond precision):

         callback(<topic>, <message>, <timestamp>)

   - Use "cbargs=(ARG_TOPIC, ARG_TIMESTAMP, ARG_LEVEL, ARG_PARTS,
     ARG_TEXT, ARG_MESSAGE)" and "staticargs=(value1, value2, ...)"
     to get more detailed control of what arguments are included in
     the callback, and in what order.  Those specified in "cbargs"
     appear before those in "staticargs":

         subscribe(mytopic, callback, cbargs=(ARG_LEVEL, ARG_MESSAGE), staticargs=(reference,))
         --> callback(level, message, reference)

   - Use any keyword arguments to "subscribe()" to have those same
     arguments included in the callback:
         subscribe(mytopic, callback, fruit="banana")
         --> callback(mytopic, message, fruit="banana")

   - Use "decompose=True" to decompose the published message in a
     manner similar to response parsing, above; unnamed
     arguments/words from the message are appended as additional
     arguments, and named options/values are included as keyword
     arguments:
         subscribe(mytopic, callback, timestamp=True, decompose=True)
         --> callback(mytopic, timestamp, arg1, arg2, option1=value1, option2=value2...)

"""

from .symbols import *
from .errors import *
from .message import Message
from .socket_client import SocketClient
from .serial_client import SerialClient
