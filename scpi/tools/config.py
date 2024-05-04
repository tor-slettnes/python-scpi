#===============================================================================
## @file config.py
## @brief Configuration file support
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Standard Python modules
from configparser import ConfigParser, NoSectionError, NoOptionError, ParsingError, \
    Error as ConfigError, DEFAULTSECT, _UNSET
from threading import Lock
from logging import debug, info, warning
from os.path import join, isdir, dirname, exists
from os import getenv, pathsep, sep, makedirs, system, rename, remove, fsync, spawnl, P_WAIT
from re import compile as rxcomp
from shutil import move

_configpath = [ d for d in getenv("CONFIGPATH", ".").split(pathsep) if d ]

def setConfigPath (path):
    global _configpath
    _configpath = path

def getConfigPath ():
    return _configpath


class ReadOnly (ConfigError):
    """This configuration object is read-only; cannot modify."""

class NoFilename (ConfigError):
    """No filename given, cannot save configuration object."""


class Config (ConfigParser):
    #configLock = Lock()

    OPTCRE = rxcomp(
        r'(?P<option>[^:=#\s][^:=#]*)'      # very permissive!
        r'\s*(?:'                           # any number of space/tab,
        r'(?P<vi>[:=]?)\s*'                 # optionally followed by
                                            # separator (either : or
                                            # =), followed by any #
                                            # space/tab
        r'(?P<value>.*))$'                  # everything up to eol
        )

    def __init__ (self, files=None, mustExist=False, readOnly=False, literal=False, casePreserving=True, autoLoad=True):
        ConfigParser.__init__(self)

        if casePreserving:
            self.optionxform = str

        if files is None:
            files = []
        elif not isinstance(files, (tuple, list)):
            files = [files]

        self.configFiles    = files
        self.readOnly       = readOnly
        self.literal        = literal
        self.processed      = set()
        self.configLock     = Lock()
        if autoLoad:
            self.load(mustExist=mustExist)


    def load (self, mustExist=False, close=True):
        for cf in self.configFiles:
            try:
                self.read(cf, mustExist, processIncludes=False, close=close)
            except ParsingError as e:
                if hasattr(cf, 'name'):
                    cf = cf.name
                warning('In configuration file %r: %s'%(cf, e))

        self._processIncludes()


    def read (self, configfile, mustExist=False, processIncludes=True, close=True):
        error = None
        found = False

        if isinstance(configfile, str):
            filename = configfile

            if not '.' in filename:
                filename += '.ini'

            if sep in filename or not getConfigPath():
                candidates = [ filename ]
            else:
                candidates = [ join(directory, filename) for directory in getConfigPath() ]

            found = False
            for candidate in candidates:
                try:
                    configfile = open(candidate)
                except IOError as e:
                    error = e
                else:
                    found = True
                    break

            else:
                if mustExist:
                    raise error

        else:
            filename = configfile.name
            found = True

        if found:
            self.readfp(configfile, filename, processIncludes)
            if close:
                configfile.close()

        return found


    def readfp (self, fp, filename=None, processIncludes=True):
        with self.configLock:
            ConfigParser.readfp(self, fp, filename=filename)
            if processIncludes:
                self._processIncludes()


    def _processIncludes (self):
        for section in self.sections():
            if not section in self.processed:
                self._processSection(section)


    def _processSection (self, section):
        for option, value in list(self._sections[section].items()):
            if option.startswith("@") and (value.startswith('#') or not value):
                subsection = option[1:].strip()

                del self._sections[section][option]

                if not subsection in self._sections:
                    raise NoSectionError(subsection)

                if not subsection in self.processed:
                    self._processSection(subsection)

                for option, value in list(self._sections[subsection].items()):
                    self._sections[section].setdefault(option, value)

        self.processed.add(section)


    def set (self, section, key, value,
             mustHaveSection=False, mustHaveOption=False, literal=None, save=False):

        if self.readOnly:
            raise ReadOnly()

        if not self.has_section(section):
            if mustHaveSection:
                raise NoSectionError(section)

            self.add_section(section)

        section = self.findSection(section, mustExist=mustHaveOption)
        key     = self.findOption(section, key, mustExist=mustHaveOption)

        if (literal, self.literal)[literal is None]:
            transform = repr
        else:
            transform = str

        ConfigParser.set(self, section, key, transform(value))

        if save:
            self.save()


    def setliteral (self, section, key, value,
                    mustHaveSection=False, mustHaveOption=False, save=False):
        self.set(section, key, value, mustHaveSection, mustHaveOption, True, save)


    def keys (self):
        return self.sections()


    def findSection (self, section, mustExist=False):
        caseMap = dict([ (s.lower(), s) for s in self.sections() ])
        try:
            return caseMap[section.lower()]
        except KeyError:
            if mustExist:
                raise NoSectionError(section)
            else:
                return section

    def findOption (self, section, option, mustExist=False):
        caseMap = dict([ (o.lower(), o) for o in self.options(section, mustExist=mustExist) ])
        try:
            return caseMap[option.lower()]
        except KeyError:
            if mustExist:
                raise NoOptionError(option, section)
            else:
                return option


    def has_section (self, section, caseSensitive=False):
        if not caseSensitive:
            section = self.findSection(section)
        return section in self.sections()


    def options (self, section, mustExist=False, caseSensitive=False):
        if not caseSensitive:
            section = self.findSection(section)

        try:
            return ConfigParser.options(self, section)

        except NoSectionError:
            if mustExist:
                raise
            else:
                return []


    def has_option (self, section, option, caseSensitive=False):
        if not caseSensitive:
            section = self.findSection(section)
            option  = self.findOption(section, option)

        return option in self.options(section, caseSensitive=True)



    def get (self, section, key, default=Exception, literal=None,
             valuetype=None, exc_args={}, vars={}, caseSensitive=False,
             *, raw=False, fallback=_UNSET):

        try:
#            if vars:
#                info("%s.get(%r, %r, default=%r, literal=%r, valuetype=%r, vars=%r)"%
#                     (self.__class__.__name__, section, key, default, literal, valuetype, vars))

            if not caseSensitive:
                section = self.findSection(section)
                key     = self.findOption(section, key)


            rawvalue = ConfigParser.get(self, section, key,
                                        raw=raw, vars=vars, fallback=fallback)

        except (NoSectionError, NoOptionError) as e:
            if default is Exception:
                raise
            elif (isinstance(default, Exception) or
                  (isinstance(default, type(Exception)) and issubclass(default, Exception))):
                raise default(**exc_args)
            else:
                return default

        else:
            return self.parseValue(rawvalue, literal, valuetype, section, key, vars)



    def getliteral (self, section, key, valuetype, default=Exception, exc_args={}, vars={}, caseSensitive=False):
        return self.get(section, key, default, literal=True, valuetype=valuetype,
                        vars=vars, exc_args={}, caseSensitive=caseSensitive)


    def parseValue (self, rawvalue, literal, valuetype, section, option, vars):
        ### Workaround for ConfigParser() issue, where 'readfp()' initially
        ### stores values as lists, and only if parsing succeeds converts them
        ### to strings.
        if isinstance(rawvalue, list):
            rawvalue = '\n'.join(rawvalue)

        if literal is None:
            literal = self.literal

        if literal:
            try:
                value = eval(rawvalue, None, vars)

            except Exception as e:
                warning("Config(configFiles=%r, section=%r, processed=%r (%r), rawvalue=%r)"%
                        (self.configFiles, section, section in self.processed, self.processed, rawvalue))

                raise ParsingError('Invalid syntax in section [%s], locals=%s: %s = %s: %s'%
                                   (section, vars, option, rawvalue, e))

            if valuetype is float:
                valuetype = (float, int)

            elif valuetype is bool:
                valuetype = (bool, int, float)

            if valuetype is not None and not isinstance(value, valuetype):
                if not isinstance(valuetype, tuple):
                    valuetype = (valuetype,)
                expected = [ t.__name__ for t in valuetype ]

                raise ParsingError('Incorrect value type in section [%s]: %s = %s, expected %s'%
                                   (section, option, rawvalue, ','.join(expected)))

        elif rawvalue:
            commentpos = rawvalue.find('#')
            if (commentpos > 0) and rawvalue[commentpos-1].isspace():
                value = rawvalue[:commentpos].rstrip()
            else:
                value = rawvalue

        else:
            value = ''

        return value

    def __delitem__ (self, section):
        if not ConfigParser.remove_section(self, section):
            raise KeyError(section)


    def __getitem__ (self, section):
        try:
            return dict(self.items(section))
        except NoSectionError as e:
            raise KeyError(e.args)


    def __setitem__ (self, section, options):
        if self.readOnly:
            raise ReadOnly()

        if isinstance(options, (list, tuple)):
            options = dict(options)

        assert isinstance(options, dict), \
               'Cannot assign non-dictionary value to section [%s]: %s'%\
               (section, repr(options))

        self.remove_section(section)

        for (key, value) in list(options.items()):
            self.set(section, key, value)

#        if self.configFiles:
#            self.save()


    def remove_option (self, section, key, save=False, caseSensitive=False):
        try:
            if not caseSensitive:
                section = self.findSection(section)
                option = self.findOption(section, key)

            ConfigParser.remove_option(self, section, key)
        except (NoSectionError, NoOptionError):
            return False
        else:
            if not self.options(section):
                self.remove_section(section)

            if save:
                self.save()
            return True


    def remove_section (self, section, exception=None, save=False, caseSensitive=False):
        try:
            if not caseSensitive:
                section = self.findSection(section)

            ConfigParser.remove_section(self, section)
        except NoSectionError:
            if exception:
                raise exception
            else:
                return False
        else:
            if save:
                self.save()
            return True


    def items (self, section, mustExist=False, literal=None, valuetype=None, vars={}, caseSensitive=False):
        if not caseSensitive:
            section = self.findSection(section)

        try:
            items = ConfigParser.items(self, section)
        except NoSectionError:
            if mustExist:
                raise
            return []
        else:
            return [(option, self.parseValue(value, literal, valuetype, section, option, vars))
                    for (option, value) in items]


    def write (self, fileobj):
        if self.readOnly:
            raise ReadOnly()

        ConfigParser.write(self, fileobj)



    def save (self, filename=None, usetemp=True):
        if self.readOnly:
            raise ReadOnly()

        if not filename:
            for candidate in self.configFiles:
                if isinstance(candidate, str):
                    filename = candidate

        if not filename:
            raise NoFilename()

        if not '.' in filename:
            filename += '.ini'

        if not sep in filename:
            configDir = _configpath[0]
            if not isdir(configDir):
                makedirs(configDir)
            filename  = join(configDir, filename)
        else:
            configDir = dirname(filename)


        with self.configLock:
            if usetemp:
                tempname = filename + ".tmp"
                fp = open(tempname, "w")
            else:
                fp = open(filename, "w")

            with fp:
                self.write(fp)
                fp.flush()
                fsync(fp.fileno())

            if usetemp:
                rename(tempname, filename)


