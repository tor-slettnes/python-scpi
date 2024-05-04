#===============================================================================
## @file dataproxy.py
## @brief Helper class to set/get variables within specified scopes
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

class DataProxy (object):
    def __init__ (self, maps):
        self._maps = maps

    def getScopeDataValue (self, scope, identifier=None, defaultScope=None):
        if identifier:
            if scope is not None:
                data = self._maps[scope]
                return scope, data, data[identifier]
            else:
                for index, data in enumerate(self._maps):
                    if data is not None:
                        try:
                            return index, data, data[identifier]
                        except KeyError:
                            pass
                else:
                    raise KeyError(identifier)

        else:
            if scope is None:
                scope = defaultScope or 0
            return (scope, self._maps[scope], None)

    def getValue (self, value, key=None):
        if isinstance(value, str):
            if value:
                value = [value]
            else:
                value = []

        if key is None:
            return value
        elif isinstance(value, list):
            return value[int(key)]
        else:
            return value[key]

    def toString (self, value, delimiter=' '):
        if isinstance(value, (dict, list)):
            value = delimiter.join(value)
        return value
