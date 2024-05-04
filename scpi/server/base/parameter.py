#===============================================================================
## @file parameter.py
## @brief SCPI parameter support
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from ..exceptions         import CommandError
from ...tools.publication import debug, info, warning
from ...tools.parser      import parser, OptionName, CookedValue

class TooFewRepeats (CommandError):
    'Parameter %(name)r requires at least %(min)d %(argtype)s values separated by %(sep)r; got %(actual)d.'

class TooManyRepeats (CommandError):
    'Parameter %(name)r requires at most %(max)d %(argtype)s values separated by %(sep)r; got %(actual)d.'

class Missing (object):
    pass


#===============================================================================
### "Parameter" class definition.

class Parameter (object):
    '''
    A parameter is a declared command input or output.

    - Input parameters are used to parse command arguments
    - Output parameters are used to format return values
    '''

    name        = None        # Parameter name.
    type        = None        # A "ParameterType()" instance, defined below.
    named       = False       # True if this is a named-only parameter
    default     = Missing     # Default value (implies optional)
    format      = None        # Format string for conversions
    range       = None        # A (min, max) tuple for value range
    repeats     = None        # A (min, max) tuple for repeat count
    split       = None        # A (sep, min, max) tuple to split argument values by token
    units       = None        # Unit description (e.g. 'milliWatts')
    description = None        # User-facing description of parameter
    hidden      = False       # Hide this parameter in command descriptions
    secret      = False       # Obfuscate the corresponding argument in published messages/logs
    form        = object      # In what form do we pass in the argument
                              # ("object" means fully parsed, basestring means raw, str means cooked)

    def __init__ (self, name, type=Missing, **attributes):
        self.name = name
        self.update(type=type, **attributes)

    def update (self, type=Missing, **attributes):
        if type is not Missing:
            self.setInitial(type)

        self.__dict__.update(attributes)
#        for attr, value in attributes.items():
#            assert hasattr(self, attr), \
#                "Cannot set parameter %r, type %r cannot set attribute %r to %r: No such attribute"%\
#                (name, type, attr, value)

#            setattr(self, attr, value)


    def setInitial (self, initial):
        if initial is None:
            self.default = None

        elif initial is Missing:
            self.type = None

        elif isinstance(initial, tuple):
            self.type = Enum(*initial)

        elif isinstance(initial, dict):
            initial = initial.copy()
            self.default = initial.pop(None, self.default)
            self.type    = Lookup(**initial)

        elif isinstance(initial, ParameterType):
            self.type = initial

        elif type(initial) in typeMap:
            self.type    = typeMap[type(initial)]
            self.default = initial

        elif initial in typeMap:
            self.type    = typeMap[initial]

        else:
            raise TypeError('Unknown type %s for parameter %s'%(initial, self.name))


    def toString (self, value, formal=False):
        if self.secret:
            return '*'

        elif self.split:
            sep, repeatMin, repeatMax = self.splits()
            if not isinstance(value, (tuple, list)):
                #warning("Parameter %s.toString(): value %r is not a tuple or list, cannot be joined with %r"%
                #        (self.name, value, sep))
                value = (value,)

            string = sep.join([self.type.toString(v, formal=formal, format=self.format)
                               for v in value ])

            if repeatMin is not None and len(value) < repeatMin:
                raise TooFewRepeats(name=self.name, argtype=self.typeDescription(),
                                    sep=sep, min=repeatMin, actual=len(value), value=string)

            if repeatMax is not None and len(value) > repeatMax:
                raise TooManyRepeats(name=self.name, argtype=self.typeDescription(),
                                     sep=sep, max=repeatMax, actual=len(value), value=string)

        else:
            string = self.type.toString(value, formal=formal, format=self.format)

        return string


    def fromString (self, value):
        if self.split:
            sep, repeatMin, repeatMax = self.splits()
            if value:
                words = value.split(sep)
            else:
                words = []

            if repeatMin is not None and len(words) < repeatMin:
                raise TooFewRepeats(name=self.name, argtype=self.typeDescription(),
                                    sep=sep, min=repeatMin, actual=len(words), value=value)

            if repeatMax is not None and len(words) > repeatMax:
                raise TooManyRepeats(name=self.name, argtype=self.typeDescription(),
                                     sep=sep, max=repeatMax, actual=len(words), value=value)

            return [ self.type.fromString(word) for word in words ]

        else:
            return self.type.fromString(value)



    def typeDescription (self, formal=False, default=None):
        if formal:
            desc = self.type.formalDescription(range=self.range,
                                               format=self.format)

            if self.split:
                sep, repeatMin, repeatMax = self.splits()
                desc = "%ss separated by %r"%(desc, sep)
                if repeatMin is repeatMax is None:
                    desc = 'any number of %s'%(desc,)
                elif repeatMax is None:
                    desc = '%d or more %s'%(repeatMin, desc)
                elif repeatMin is None:
                    desc = 'up to %d %s'%(repeatMax, desc)
                elif repeatMin == repeatMax:
                    desc = '%d %s'%(repeatMin, desc)
                else:
                    desc = '%d to %d %s'%(repeatMin, repeatMax, desc)

            if self.repeats:
                repeatMin, repeatMax = self.repeatRange()
                if self.split:
                    desc = 'groups of %s'%(desc,)

                if repeatMin is repeatMax is None:
                    desc = 'any number of %ss'%(desc,)
                elif repeatMax is None:
                    desc = "%d or more %ss"%(repeatMin, desc)
                elif repeatMin is None:
                    desc = "up to %d %ss"%(repeatMax, desc)
                elif repeatMin == repeatMax:
                    desc = "exactly %s %ss"%(repeatMin, desc)
                else:
                    desc = "%d to %d %ss"%(repeatMin, repeatMax, desc)

            if self.units:
                if self.repeats:
                    article = ''
                else:
                    article = (' a', ' an')[desc[:1] in 'aeiou']

                desc = '%s as%s %s'%(self.units, article, desc)

            if not (default or self.default) in (None, Missing, ()):
                desc += " [default=%s]"%self.type.toString(default or self.default,
                                                           formal=True)

        else:
            desc = self.type.description

        return desc


    def validate (self, value):
        return self.type.validate(value, self.range, self.format)


    def splits (self):
        if self.split is None:
            return None, None, None
        elif isinstance(self.split, tuple):
            return self.split
        elif isinstance(self.split, str):
            return self.split, None, None
        else:
            assert False, "Parameter %r has invalid split attribute: %r"%(self.name, self.split)

    def repeatRange (self):
        if self.repeats is None:
            return (1, 1)
        elif isinstance(self.repeats, tuple):
            return self.repeats
        else:
            return (self.repeats, self.repeats)


    def propertyList (self):
        if self.default in (None, Missing):
            default = ''
        else:
            default = self.toString(self.default, formal=True)

        return [('Name',        self.name),
                ('Type',        self.typeDescription(formal=True)),
                ('Named',       str(self.named)),
                ('Required',    str(self.default is Missing)),
                ('Default',     default),
                ('Range',       str(self.range or '')),
                ('Description', self.description or '')]



#===============================================================================
### Parameter Type abstract superclass
##

class ParameterType (object):
    'generic'

    __slots__ = ('range', 'format', 'description', 'form')

    def __init__ (self, range=None, format=None, desc=None):
        self.range       = range
        self.format      = format or "%s"
        self.description = desc or self.__class__.__doc__


    def formalDescription (self, range, format):
        low, high = range or (None, None)

        if low is not None and high is not None:
            return "%s between %s and %s"%\
                   (self.description,
                    self.toString(low, formal=True, format=format),
                    self.toString(high, formal=True, format=format))

        elif low is not None:
            return "%s %s or higher"%(self.description,
                                      self.toString(low, formal=True, format=format))

        elif high is not None:
            return "%s up to %s"%(self.description,
                                  self.toString(high, formal=True, format=format))

        else:
            return self.description


    def validate (self, value, range, format):
        pass

    def fromString (self, string):
        return string or ''

    def toString (self, value, format, formal):
        if format or formal:
            return (format or self.format or "%s")%(value,)
        elif value is None:
            return ''
        else:
            return str(value)


class Bool (ParameterType):
    'boolean'
    __slots__ = ()

    def fromString (self, string):
        if not string:
            return True
        else:
            return boolean(string)

    def toString (self, value, format=None, formal=False):
        if format or formal:
            return (format or self.format or "%s")%bool(value)
        elif isinstance(value, str):
            return value
        else:
            return str(bool(value))


class Int (ParameterType):
    'integer'

    __slots__ = ()

    def fromString (self, string):
        return integer(string)

    def validate (self, value, range, format):
        if value is not None:
            low, high = range or self.range or (None, None)
            if low is not None and value < low:
                raise ValueError('value must be %s or higher'%
                                 self.toString(low, formal=true, format=format))

            if high is not None and value > high:
                raise ValueError('value must be no higher than %s'%
                                 self.toString(high, formal=true, format=format))


class Real (Int):
    'real number'

    __slots__ = ()

    def fromString (self, string):
        return real(string)


class String (ParameterType):
    'string'

    def fromString (self, string):
        return string or ''

    def toString (self, value, formal, format="%s"):
        if format or formal:
            return (format or self.format or "%s")%(value,)
        elif value is None:
            return ''
        else:
            return "%s"%(value,)


class List (ParameterType):
    'list'

    __slots__ = ()

    def __init__ (self, format='%s\n', *args, **kwargs):
        ParameterType.__init__(self, format=format, *args, **kwargs)

    def fromString (self, string):
        lines = (string or '').splitlines()
        if lines and not lines[0]:
            lines.pop(0)
        return lines


    def toString (self, value, format, formal):
        assert isinstance(value, (list, tuple)), \
               'Value %r is not a valid list'%(value, )

        if format or formal:
            lines = [((format or self.format or "%s\n")%(item,)) for item in value]
        else:
            lines = [ "%s\n"%item for item in value ]

        return ''.join(lines)



class Lookup (ParameterType):
    'lookup'


    def __init__ (self, **dictionary):
        ParameterType.__init__(self)

#        assert len(dictionary) >= 2, \
#               'Maps must have at least 2 elements: %r'%(dictionary, )

        self.dictionary = {}
        for key, value in dictionary.items():
            lookupkey = key and key.lower().strip("+")
            self.dictionary[lookupkey] = value, key


    def formalDescription (self, range=None, format=None):
        values   = list(self.dictionary.values())
        try:
            values.sort()
        except TypeError:
            pass

        keys = [ self.toString(v, formal=False) for (v,k) in values ]
        if keys:
            return '|'.join(keys).join('{}')
        else:
            return '(None)'


    def fromString (self, string):
        try:
            return self.dictionary[(string or '').lower()][0]
        except (KeyError, AttributeError):
            raise ValueError('Expected %s, not "%s"'%(self.formalDescription(), string))


    def toString (self, value, format=None, formal=False):
        key = value
        for v, k in self.dictionary.values():
            if k and (v == value):
                key = k.strip('+')
                if k.startswith('+'):
                    break

        return formal and repr(key) or key



class Enum (Lookup):
    'enumeration'

    __slots__ = ()

    def __init__ (self, *elements):
        dictionary = {}
        for index, string in enumerate(elements):
            dictionary[string] = index

        Lookup.__init__(self, **dictionary)



class ArgTuple (ParameterType):
    'command element'

    def __init__ (self, **options):
        ParameterType.__init__(self, **options)


    def toString (self, value, format, formal):
        if isinstance(value, tuple):
            value = value[CookedValue]

        return (format or self.format or "%s")%(value,)

    def fromString (self, string):
        return string or ''



typeMap = {
    int        : Int(),
    abs        : Int(format='%u',   range=(0, None), desc='unsigned integer'),
    hex        : Int(format='0x%X', range=(0, None), desc='hexadecimal number'),
    float      : Real(),
    bool       : Bool(),
    str        : String(),
    list       : List(),
    tuple      : ArgTuple(),
    object     : ParameterType()
    }



def autoType (string):
    if not string:
        return None

    try:
        return integer(string)
    except ValueError:
        try:
            return real(string)
        except ValueError:
            try:
                return boolean(string)
            except ValueError:
                pass

    return string


def boolean (string):
    if isinstance(string, (int, float)):
        return bool(string)
    elif string.lower() in ("yes", "true", "on"):
        return True
    elif string.lower() in ("no", "false", "off"):
        return False
    else:
        try:
            return bool(int(string, 0))
        except ValueError:
            try:
                return bool(float(string))
            except ValueError:
                raise ValueError("could not convert string to boolean: %r"%(string,))


def integer (string):
    try:
        return int(string)
    except (ValueError, TypeError) as e:
        try:
            return int(string, 0)
        except (ValueError, TypeError):
            raise ValueError(e)


def real (string):
    return float(string)
