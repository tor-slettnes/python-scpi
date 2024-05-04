#!/bin/echo "Do not invoke directly"
#===============================================================================
## @file symbols.py
## @brief SCPI client - holds a message published from the server
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

import logging

### Response and input types from the SCPI server
RESPONSE_TYPES = \
    (OK, NEXT, ERROR, MESSAGE, READY) = \
    ("OK", "NEXT", "ERRor", "MESSage", "READy")

### Access Levels
ACCESS_LEVELS = \
    (ACCESS_GUEST, ACCESS_OBSERVER, ACCESS_CONTROLLER, ACCESS_ADMINISTRATOR, ACCESS_FULL) = \
    ("Guest", "Observer", "Controller", "Administrator", "Full")

### Subscription levels
SUBSCRIPTION_LEVELS = ("trace", "debug", "info", "notice", "warning", "error")
LOGGING_LEVELS =  (0, logging.DEBUG, logging.INFO, logging.INFO, logging.WARNING, logging.ERROR)
(LEVEL_TRACE, LEVEL_DEBUG, LEVEL_INFO, LEVEL_NOTICE, LEVEL_WARNING, LEVEL_ERROR) = \
    list(range(len(SUBSCRIPTION_LEVELS)))

### Available arguments in decomposed message callback
MESSAGE_ARGS = \
    (ARG_TOPIC, ARG_TIMESTAMP, ARG_LEVEL, ARG_PARTS, ARG_KWARGS, ARG_TEXT, ARG_MESSAGE, ARG_RAW) = \
    ("topic", "timestamp", "level", "parts", "kwargs", "text", "message", "raw")
