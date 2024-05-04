#===============================================================================
## @file variable_leafs.py
## @brief Commands related to variables
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from ..base.leaf import Leaf, Controlling, Observing
from ..exceptions import RunError, CommandError, ReturnValue, Break
from ...tools.dataproxy import DataProxy

## Standard Python modules
import re

### Scopes for variables
VariableScopes = ('local', 'branch', 'global')
(LOCAL, BRANCH, GLOBAL) = list(range(len(VariableScopes)))

#===============================================================================
## @class VariableLeaf
## @brief Base for specific commands below

class VariableLeaf (Leaf):
    validNameX   = re.compile(r'\w[\w\-]*$')
    delegateEstimation = True

    class InvalidVariableName (CommandError):
        'The variable name %(name)r contains invalid character(s)'

    class IncorrectType (CommandError):
        'The %(scope)s variable %(name)r is a %(actual)s, not a %(expected)s'

    class NoSuchVariable (CommandError):
        'There is no %(scope)s variable by this name: %(name)r'

    class NoNamedKeys (CommandError):
        'The %(scope)s variable %(name)r is not a dictionary.'

    class NoSuchKey (CommandError):
        'No such key exists in the %(scope)s dictionary %(name)r: %(key)r'

    class NoSuchIndex (CommandError):
        'Index is out of range for the %(scope)s variable %(name)r: %(index)s'

    def declareInputs (self):
        Leaf.declareInputs(self)
        self.setInput('scope',
                      default=None,
                      named=True,
                      description=
                      'Specifies whether the variable should be local to '
                      'the current session, valid across all sessions '
                      'as long as the instrument is running, or both valid '
                      'across client sessions and persistent through reboots.')


    def scopeName (self, scope=None):
        try:
            return VariableScopes[scope]
        except (IndexError, TypeError):
            return ', or '.join((", ".join(VariableScopes[:-1]), VariableScopes[-1]))


    def scopeData (self, localdata, branch=None):
        if branch is None:
            branch = self.parent

        return [localdata, branch.branchData, self.globalData]


    def getData (self, scope, localdata, datatype=object):
        scopedata = self.scopeData(localdata)
        if scope is not None:
            scopedata = [scopedata[scope]]

        items = {}
        for data in scopedata:
            for key, value in list(data.items()):
                if isinstance(value, datatype):
                    items.setdefault(key, value)

        return items


    def dataProxy (self, scope, localdata, identifier=None, datatype=object,
                   ignoreMissing=False, default=None, defaultScope=LOCAL, branch=None):

        proxy = DataProxy(self.scopeData(localdata, branch))
        try:
            scope, data, value = proxy.getScopeDataValue(scope, identifier)
        except KeyError:
            if ignoreMissing or default is not None:
                scope, data, value = proxy.getScopeDataValue(scope, defaultScope=defaultScope)
                value = default
            else:
                raise self.NoSuchVariable(scope=self.scopeName(scope), name=identifier)
        else:
            if identifier:
                if datatype is list and isinstance(value, str):
                    value = [value]
                elif datatype is str and isinstance(value, list) and len(value) < 2:
                    value = ' '.join(value)
                elif not isinstance(value, datatype):
                    raise self.IncorrectType(scope=self.scopeName(scope),
                                             name=identifier,
                                             expected=datatype.__name__,
                                             actual=type(value).__name__)

        return scope, data, value




class VARiable_Set (Controlling, VariableLeaf):
    '''Set a variable to a given value or add values to existing
    variable.

    A variable comprises one or more substrings, each of which may
    be referenced by an index starting with 0.

    Variables are scoped in two ways:
     * They are valid only within the command scope (branch) in which
       they were defined.

     * They may be valid within the current client session (local),
       valid across all client sessions while the instrument server is
       running (global), or both valid across client sessions and
       persistent through reboots (persistent).  This is determined
       by the "-scope" setting when the variable is first defined;
       subsequent updates to the variable retains its current scope.

Examples:
    # Set a variable within the "SYSTem" branch with a global scope:
      SYSTem:VARiable= -scope=global MyVariable "My Text"

    # Set a the local top-level variable:
      VARiable= actions "First action" "Second Action"

    # Add a new string to an existing variable
      VARiable= -extend actions "Third Action"

    # Set a variable that will be available after reboot:
      VARiable= -scope=global RunInfo "My Run Title"
    '''

    class Mismatched (RunError):
        'Missing value for key %(key)s'

    def declareInputs (self):
        VariableLeaf.declareInputs(self)
        self.setInput('string', type=bool, named=True, default=False,
                      description='Join values into a single string.')
        self.setInput('extend', type=bool, named=True, default=False,
                      description='Add positional substrings to an existing variable')
        self.setInput('values', type=str, repeats=(0, None))


    def run (self, _context, scope=VariableScopes, string=False, create=False,
             prepend=False, append=False, delimiter='', extend=False, name=str, *values):
        if not self.validNameX.match(name):
            raise self.InvalidVariableName(name=name)

        self.checkConflictingOptions(string=string, extend=extend)
        self.checkConflictingOptions(append=append, prepend=prepend, extend=extend)

        new = create or not (extend or append or prepend)

        if scope is None and new:
            scope = LOCAL

        scope, data, previous = self.dataProxy(scope, _context.data, name,
                                               datatype=list,
                                               ignoreMissing=new,
                                               default=[])

        if extend:
            result = previous+list(values)

        elif string or (len(values) == 1):
            result = ' '.join(values)
            if prepend or append:
                previous = ' '.join(previous)
                parts = ((result,previous),(previous,result))[append]
                result = delimiter.join(parts)

        elif append or prepend:
            result = list(previous)
            for index, value in enumerate(values):
                try:
                    old = previous[index]
                except IndexError:
                    result.append(value)
                else:
                    parts = ((value,old),(old,value))[append]
                    result[index] = delimiter.join(parts)
        else:
            result = list(values)

        data[name] = result


class VARiable_Clear (Controlling, VariableLeaf):
    '''Remove the indexed item from a variable, or if no index is specified, remove the variable itself.
    Indices start at 0. A negative index counts items from the end of the variable.'''

    def declareInputs (self):
        VariableLeaf.declareInputs(self)
        self.setInput('ignoreMissing', default=True,
                      description='Do not raise an error if the variable '
                      'does not exist or the index is out of range.')
        self.setInput('index', type=int, default=None)

    def run (self, _context, scope=VariableScopes, ignoreMissing=True, name=str, index=int):
        if not self.validNameX.match(name):
            raise self.InvalidVariableName(name=name)

        scope, data, value = self.dataProxy(scope, _context.data, name, ignoreMissing=ignoreMissing, datatype=list, default=[])

        if index is None:
            data.pop(name, None)
        else:
            try:
                del value[index]
            except IndexError:
                if not ignoreMissing:
                    raise self.NoSuchIndex(scope=self.scopeName(scope), name=name, index=index)
            else:
                data.update()


class VARiable_Query (Observing, VariableLeaf):
    '''
    Return the contents of the given variable.
    '''

    def declareInputs (self):
        VariableLeaf.declareInputs(self)
        self.setInput('default', type=str, default=None, named=True,
                      description='Return this value if variable does not exist')
        self.setInput('ignoreMissing', default=False,
                      description=
                      'Do not return an error if the variable does not exist')
        self.setInput('length', type=bool, default=False, named=True,
                      description='Return the length, rather than the contents, of the variable')
        self.setInput('exists', type=bool, default=False, named=True,
                      description='Return a boolean indicator (True or False) of whether the variable exists')
        self.setInput('indices', type=int, repeats=(0, None))

    def declareOutputs (self):
        VariableLeaf.declareOutputs(self)
        self.addOutput('value', type=str, repeats=(0, None),
                       description='The contents of the requested variable')


    def run (self, _context, scope=VariableScopes, default=None, ignoreMissing=False, length=False, exists=False, name=str, *indices):
        if not self.validNameX.match(name):
            raise self.InvalidVariableName(name=name)

        if exists or length or (default is not None):
            ignoreMissing = True

        scope, data, value = self.dataProxy(scope, _context.data, name, datatype=list, ignoreMissing=ignoreMissing, default=[])
        found = bool(value)

        if found and indices:
            outputs = []
            items   = 0
            for index in indices:
                try:
                    outputs.append(value[index])
                    items += 1
                except IndexError:
                    found = False
                    if ignoreMissing:
                        outputs.append(default)
                    else:
                        raise self.NoSuchIndex(scope=self.scopeName(scope), name=name, index=index)
            value = outputs
        else:
            items = len(value)

        if exists:
            return found
        elif length:
            return items
        else:
            return tuple(value) or default


class VARiable_Exists (Observing, VariableLeaf):
    '''
    Return True if the specified variable exists, False otherwise
    '''

    def declareInputs (self):
        VariableLeaf.declareInputs(self)
        self.setInput('nonEmpty', type=bool, named=True, default=False,
                      description='Require the contents of the variable to be non-empty')
        self.setInput('index', type=int, default=None)

    def declareOutputs (self):
        Leaf.declareOutputs(self)
        self.addOutput('exists', type=bool)


    def run (self, _context, scope=VariableScopes, nonEmpty=False, name=str, index=int):
        if not self.validNameX.match(name):
            return False

        try:
            scope, data, value = self.dataProxy(scope, _context.data, name, datatype=list)
        except self.NoSuchVariable:
            return False
        else:
            if index is None:
                value = ''.join(value)
            else:
                try:
                    value = value[index]
                except IndexError:
                    return False

            return bool(value or not nonEmpty)


class VARiable_Enumerate (Observing, VariableLeaf):
    '''
    Return an alphabetical list of variables in the specified scope
    (local, global, persistent), or in all scopes if not specified.
    '''

    def declareOutputs (self):
        VariableLeaf.declareOutputs(self)
        self.addOutput('name', type=str, repeats=(0, None))

    def run (self, _context, scope=VariableScopes):
        return tuple(sorted(self.getData(scope, _context.data, (list, str))))


#===============================================================================
### Commands: ADDValue

class ADDValue (VariableLeaf):
    '''
    Add to the value of the given variable.

    This produces an error if the variable does not exist, or its
    value cannot be converted to a numeric value.
    '''

    class NonNumericalValue (RunError):
        'Variable contains non-numeric value %(value)r'

    def declareInputs (self):
        VariableLeaf.declareInputs(self)
        self.setInput('create',
                      description=
                      'If the variable does not exist, create it rather than '
                      'returning an error.')

        self.setInput('default',
                      type=float,
                      named=True,
                      default="0",
                      description='Default value if missing')


    def run (self, _context, create=False, scope=VariableScopes, default=0.0, name=str, value=float):
        if not self.validNameX.match(name):
            raise self.InvalidVariableName(name=name)

        scope, data, current = self.dataProxy(scope, _context.data, name, datatype=str, ignoreMissing=create, default=default)
        try:
            if "." in current:
                value = float(current) + value
            else:
                value = int(current) + value

        except ValueError:
            raise self.NonNumericalValue(name=name, value=value)

        data[name] = "%g"%(value,)
