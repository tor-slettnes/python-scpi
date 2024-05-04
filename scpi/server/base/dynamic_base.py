#===============================================================================
## @file dynamic_base.py
## @brief Create and delete macros
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

## Modules relative to install path
from .base                import Base, suffixRevMap
from .leaf                import Leaf, Controlling, Observing
from ..exceptions         import Error, CommandError
from ...tools.publication import warning, info, debug, trace

## Standard Python modules
import re

class Dynamic (object):
    TypeName = 'dynamic command'

    @classmethod
    def getTypeName (cls):
        return cls.TypeName



class DynamicCommandBase (object):
    validNameX  = re.compile(r'(?:[A-Za-z_][\w\-]*)?[%s]?$'%(''.join([re.escape(c) for c in suffixRevMap])))
    _dynamicCommandType = Dynamic

    class InvalidCommandName (CommandError):
        'The name %(name)r contains invalid character(s)'

    class IncorrectType (CommandError):
        '%(foundName)r is a(n) %(foundType)s, not a(n) %(searchType)s'

    class NoUpperCaseLetters (CommandError):
        'The name %(name)r has no uppercase letters, as required for the short form'

    class DuplicateName (CommandError):
        'The name %(name)r is already mapped to the %(type)s %(command)r'

    class DuplicateShortName (CommandError):
        'The short form of name %(name)r is %(shortname)r, which is already mapped to the %(type)s %(command)r'


    def findDynamicCommand (self, name,
                            anyType=False,
                            searchType=None,
                            allowMissing=False,
                            allowExisting=True,
                            allowShortConflict=None,
                            parent=None,
                            incarnate=False):

        if anyType:
            searchType = Base
        elif searchType is None:
            searchType = self._dynamicCommandType

        if not parent:
            parent = self

        if allowShortConflict is None:
            allowShortConflict = allowExisting

        obj = parent.getChild(name, allowMissing=allowMissing, incarnate=incarnate)
        if obj:
            if not allowExisting:
                othername = parent.getPrimaryChildName(name)
                raise self.DuplicateName(name=name,
                                         command=parent.commandPath(othername),
                                         type=obj.getTypeName())

            if not obj.istype(searchType):
                raise self.IncorrectType(foundType=obj.getTypeName(),
                                         searchType=searchType.getTypeName(),
                                         searchName=name,
                                         foundName=parent.commandPath(name, short=False))


        elif not allowShortConflict:
            shortname = parent.alternateNames(name)[-1]
            obj = parent.getChild(shortname, allowMissing=allowMissing, incarnate=incarnate)

            if obj:
                othername = parent.getPrimaryChildName(shortname)
                raise self.DuplicateShortName(name=name,
                                              shortname=shortname,
                                              command=parent.commandPath(othername),
                                              type=obj.getTypeName())


        return obj


    def findModifiableCommand (self, session, name, anyType=False, searchType=Dynamic,
                               allowMissing=False,
                               allowExisting=True,
                               allowShortConflict=None,
                               parent=None):


        obj = self.findDynamicCommand(name, anyType, searchType,
                                      allowMissing, allowExisting, allowShortConflict, parent)

        if session and obj:
            session.checkAccess(obj.modifyAccess)
        return obj


    def newclass (self, name, classlist, slots=(), **classdict):
        if not (name and self.validNameX.match(name)):
            raise self.InvalidCommandName(name=name)

        for cls in classlist:
            doc = cls.__doc__
            if doc:
                break
        else:
            doc = None

        classdict['__doc__'] = doc

        try:
            return type(name, classlist, classdict)
        except Exception as e:
            self.info('Unable to create class %r from classes %s: [%s] %s'%
                      (name, ",".join([ c.__name__ for c in classlist ]), e.__class__.__name__, e))
            raise


    def incarnate (self, name, cls, parent=None, *args, **kwargs):
        if not (name and self.validNameX.match(name)):
            raise self.InvalidCommandName(name=name)

        if isinstance(cls, (tuple, list)):
            cls = self.newclass(name, cls)

        return cls(name=name, parent=parent or self, *args, **kwargs)


    def addinstance (self, session, name, obj,
                     replaceExisting=False,
                     modifyAccess=None,
                     requiredAccess=None,
                     hidden=None,
                     singleton=False,
                     parent=None):


        if not self.validNameX.match(name):
            raise self.InvalidCommandName(name=name)

        if not parent:
            parent = self

        self.findModifiableCommand(session, name,
                                   allowMissing=True,
                                   allowExisting=replaceExisting,
                                   parent=parent)

        if not modifyAccess in range(session.getAccessLevel()):
            modifyAccess = session.getAccessLevel()

        if (requiredAccess is not None):
            currentAccess = session.getAccessLevel()
            if requiredAccess <= currentAccess:
                obj.requiredAccess = requiredAccess

        obj.modifyAccess  = modifyAccess
        obj.singleton     = singleton
        if hidden is None:
            obj.hidden = name.startswith("_")
        else:
            obj.hidden = hidden

        return parent.addChild(obj, name)


    def delinstance (self, session, name, ignoreMissing=False, parent=None, commandType=None):
        obj = self.findModifiableCommand(session, name,
                                         searchType=commandType,
                                         allowMissing=ignoreMissing,
                                         parent=parent)

        if obj:
            trace('Deleting %s %r'%(obj.getTypeName(), obj.commandPath()))
            (parent or self).delChild(obj)

        return obj


    def getinstances (self, commandType=None, parent=None, all=False):
        if commandType is None:
            commandType = self._dynamicCommandType

        if parent is None:
            parent = self

        return set([ child
                     for (child, names) in list(parent.children.values())
                     if issubclass(child.__class__, commandType) and (all or not child.hidden) ])

    def listinstances (self, commandType=None, parent=None, all=False):
        return sorted([child.name for child in self.getinstances(commandType, parent, all)])

    def addChildClasses (self, session, children, replaceExisting=False, commandType=None, parent=None):
        childmap   = {}
        dupes      = []

        if parent is None:
            parent = self

        for child in children:
            obj, names, defaults = child
            for name in names:
                lowername = name.lower()
                childmap[lowername] = child

        intersect  = set(childmap) & (set(self.children) | set(self.childclasses))

        for name in intersect:
            try:
                dupe = self.findModifiableCommand(session, name,
                                                  allowMissing=True,
                                                  allowExisting=replaceExisting,
                                                  searchType=commandType,
                                                  parent=parent)
            except Error as e:
                if replaceExisting or True:
                    obj, names, defaults = childmap[name]
                    warning("While adding %s %r: [%s] %s. Proceeding anyway -- for now!"%
                            (obj.getTypeName(), names[0], e.name, str(e)))
                else:
                    raise

            else:
                dupes.append(dupe)

        self.childclasses.update(childmap)



class DynamicCommandLeaf (DynamicCommandBase, Leaf):
    pass
