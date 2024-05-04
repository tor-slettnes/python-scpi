#===============================================================================
## @file scpiIdentificationLeaf.py
## @brief Commands related to variables
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from ..base.leaf import Leaf, Observing, Controlling
import logging

class Common_IDentNtification_Query (Observing, Leaf):
    '''Return identification string for this server.'''

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('identification', type=str,
                       description='Identification string')

    def run (self):
        return ("Picarro,Boxer,SN65000,1.0.2",)

class Common_ReSeT (Controlling, Leaf):
    '''Reset the device'''

    def run (self):
        raise NotImplementedError("*RST command is not yet implemented")
