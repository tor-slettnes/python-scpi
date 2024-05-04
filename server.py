#!/usr/bin/python3 -B
#===============================================================================
## @file server.py
## @brief Launch SCPI Server
#===============================================================================

import sys, os, os.path, argparse, platform, glob

### Instrument Flavor, used to initialize behavior.
flavor       = os.getenv("FLAVOR", "simulator")

### Search path for local (instrument-specific) configuration files
configpath   = os.getenv("CONFIGPATH",
                          [ "/etc/picarro/scpi/config", ])

### Search path for local (instrument-specific) SCPI modules
modulepath   = os.getenv("MODULEPATH",
                          [ "/etc/picarro/scpi/modules" ])


### SCPI modules to load at startup, before accepting client connections.
preload      = [ "init", "instrument" ]

### SCPI modules to load at startup, once server is running.
postload     = [ "start" ]

### SCPI modules to load before shutdown.
exitmodules  = [ "stop" ]


if __name__ == '__main__':
    import scpi.server
    scpi.server.initialize(flavor=flavor,
                           configpath=configpath,
                           modulepath=modulepath,
                           preload=preload,
                           postload=postload,
                           exitmodules=exitmodules)

    import scpi.server.commands
    scpi.server.run(scpi.server.commands.Top)
