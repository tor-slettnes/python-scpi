#===============================================================================
## @file populated_branch.py
## @brief Branch with a full set of 'standard' commands/leaves
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

from ..base.branch import Branch

class PopulatedBranch (Branch):
    from .common_leafs import \
        Common_IDentNtification_Query, Common_ReSeT

    from .help_leafs import \
         HELP, HELP_Query, _Enumerate, _List, _Query, _Exists

    from .access_leafs import \
        ACCess, ACCess_Query

    from .variable_leafs import \
        VARiable_Set, VARiable_Clear, VARiable_Query, VARiable_Enumerate, VARiable_Exists, \
        ADDValue

    from .macro_leafs import \
        MACRo_Add, MACRo_Remove, MACRo_Query, MACRo_Enumerate

    from .return_leafs import \
        NEXT, BREak, RETurn
