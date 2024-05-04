#===============================================================================
## @file parser.py
## @brief Superclass for input parsers
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

### Standard Python modules
import re, math, sys, time, socket

#===============================================================================
### ParseError exception class
### Raised if there was a problem parsing the text.
#===============================================================================


class ParseError (Exception):
    def __init__ (self, expression, pos, reason, subexpression=None, exception=None, exc_info=None, parts=None):
        self.expression    = expression
        self.pos           = pos
        self.reason        = reason
        self.subexpression = subexpression
        self.exception     = exception
        self.exc_info      = exc_info
        self.parts         = parts


    def __str__ (self):
        return '%s <-- %s'%(self.expression[:self.pos].rstrip(), self.reason)



#===============================================================================
### CommandParser class
### Used to parse command line input.
#===============================================================================

TOKENS = (SPACE, BACKSLASH, SUBEXPRESSION, SUB_NESTED, SUB_END, HIDDEN, HIDDEN_END,
          ARGUMENT, OPTION, EQUALSIGN, SINGLEQUOTE, DOUBLEQUOTE,
          LITERAL, LITERALXML) = \
         ('space', 'backslash', 'subexpression', 'sub_nested', 'sub_end', 'hidden', 'hidden_end',
          'argument', 'option', 'equalsign', 'singlequote', 'doublequote',
          'literal', 'literalxml')


_unescaped  = r'(?<!\\)(?:\\\\)*'

_tokens     = {
    SPACE         : r'(?:^|\s+)\#.*|\s+',
    BACKSLASH     : r'\\',
    SUBEXPRESSION : r'\$[\{\[\(]',
    SUB_NESTED    : r'[\{\[\(]',
    SUB_END       : r'[\}\]\)]',
    HIDDEN        : r'\$\<',
    HIDDEN_END    : r'\>',
    ARGUMENT      : r'\$(\d+|[@,/])',
    OPTION        : r'(?:^|(?<=\s))\-(?=[a-zA-Z\.\:\_])',
    EQUALSIGN     : r'\=',
    SINGLEQUOTE   : r"\'",
    DOUBLEQUOTE   : r'\"',
    LITERAL       : r'<<<|>>>',
    LITERALXML    : r'</?\w[\w\.]*>' }


_endTokens = {
    '${' : '}',
    '$[' : ']',
    '$(' : ')',
    '$<' : '>',
    '{'  : '}',
    '['  : ']',
    '('  : ')',
    '<'  : '>'}


_processing = {
    '$(' : '_getCommandOutput',
    '${' : '_getVariable',
    '$[' : '_getEvaluationResult' }


_literalXmlX  = re.compile(r'\<(/?)\s*(\w[\w\.]*)\>')
_literalX     = re.compile(r'(\<|\>)\1\1()')
_eolX         = re.compile(r'\s*(?:\n|$)')

#_protectTags  = re.compile(r'(?P<binary>[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F])|'
#                           r'(?P<quote>(\n(?=.)))')

_protectTags  = re.compile(r'(?P<binary>[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F])|'
                           r'(?P<quote>(\n))')

_protectEscapes = re.compile(r'[\x00-\x20\x7F-\xA0\$\(\)\<\>\[\]\{\}\'\"\\]|^$')

PartFields = (OptionName, CookedValue, RawValue) = list(range(3))

QuoteStyle = ("Never", "Always", "Auto", "Attributes")
(QUOTE_NEVER, QUOTE_ALWAYS, QUOTE_AUTO, QUOTE_ATTRIBUTES) = list(range(len(QuoteStyle)))

def _tokenSearch (*tokens):
    groups = [r'(?P<%s>%s)'%(t, _tokens[t]) for t in tokens]
    return re.compile("|".join(groups))
#    return re.compile("%s%s"%(_unescaped, '|'.join(groups)))


class CommandParser (object):

    __slots__ = ()  ### Optimize storage for subclasses
    expand = True

    class Option (Exception): pass      # Raised if the argument is "named"

    #===========================================================================
    ### "Public" methods


    def expandArgs (self, input, **argmap):
        '''
        Parse the supplied text into a tuple of individual arguments.
        Various substitutions are performed.  ### FIXME: DOC TBD. ###
        '''

        if isinstance(input, str):
            text, instream = input, None
        elif input:
            text, instream = self.readLine(input), input
        else:
            text, instream = "", None

        parts   = []
        last    = 0

        try:
            option, value, text, pos = self.getArg(text, 0, instream, **argmap)

            while (option, value) != (None, None):
                parts.append((option, value, text[last:pos]))
                last = pos
                option, value, text, pos = self.getArg(text, pos, instream, **argmap)

        except ParseError as e:
            e.parts = parts
            raise

        return text, parts


    def expandValue (self, rawtext, **argmap):
        option, value, text, pos = self.getArg(rawtext, 0, **argmap)
        return value


    _argX = _tokenSearch(LITERAL, LITERALXML, SPACE,
                         BACKSLASH, SUBEXPRESSION, SUB_NESTED, SUB_END,
                         HIDDEN, ARGUMENT,
                         OPTION, SINGLEQUOTE, DOUBLEQUOTE)


    def getArg (self, text, pos, instream=None, **argmap):
        '''
        Obtain one argument starting at position "pos" in the supplied
        text string.  A two-element tuple is returned:
         - If the argument is of the form "-option=value", the first
           element is "option", and the second is "value".

         - If the argument is of the form "-option", the first
           element is "option", and the second is None.

         - Otherwise, the first element is None, and the second
           is the argument.
        '''

        try:
            arg, text, pos, endtoken = \
                 self._expandText(text, pos, instream, self._argX,
                                  argmap=argmap,
                                  skip=(SPACE, ),
                                  end=(SPACE, ))
            return None, arg, text, pos


        except self.Option as e:
            return e.args


    def collapsePart (self, part, tag='', quoting=QUOTE_AUTO, raw=False):
        if isinstance(part, (tuple, list)):
            opt, value = part[:2]
        else:
            opt, value = None, part

        if raw:
            tag, quoting = None, QUOTE_NEVER

        if opt and value is not None:
            q = (quoting, QUOTE_AUTO)[quoting==QUOTE_ATTRIBUTES]
            item = "-"+self.toString(opt)+"="+self.protectString(value, tag, q)
        elif opt:
            item = "-"+self.toString(opt)
        else:
            q = (quoting, QUOTE_NEVER)[quoting==QUOTE_ATTRIBUTES]
            item = self.protectString(value, tag, q)

        return item


    def collapseParts (self, parts=[], tag='', quoting=QUOTE_AUTO):
        return [self.collapsePart(part, tag, quoting) for part in parts]

    def collapseArgs (self, parts=[], tag='', quoting=QUOTE_AUTO, separator=' '):
        return separator.join(self.collapseParts(parts, tag, quoting))

    #def reconstruct (self, parts, tag='', quoting=QUOTE_AUTO):
    #    strings = []
    #    delim = ''
    #    for part in parts:
    #        strings.append(delim)
    #        if isinstance(part, (tuple, list)):
    #            try:
    #                opt, cooked, raw = part
    #                strings.append(raw)
    #                delim = ''
    #            except ValueError:
    #                strings.append(self.collapsePart(part, tag, quoting))
    #                delim = ' '
    ##
    #    return ''.join(strings)


    #===========================================================================
    ### Processing of whitespace

    def _process_space (self, start, text, pos, instream, argmap):
        return None, text, pos


    #===========================================================================
    ### Processing of the equal sign

    def _process_equalsign (self, start, text, pos, instream, argmap):
        return None, text, pos


    #===========================================================================
    ### Processing of the backslash ('\') character

    def _process_backslash (self, start, text, pos, instream, argmap):
        eolMatch = _eolX.match(text, pos)
        if eolMatch:
            pos = eolMatch.end()

            if len(text) == pos:
                try:
                    text += self.readLine(instream)
                except EOFError:
                    raise ParseError(text, None,
                                     'End of input while reading extended line')

            return None, text, pos
        else:
            return self._unescape(text, pos)



    #===========================================================================
    ### Processing of "-option[=value]" subexpressions

    _optX = _tokenSearch(LITERAL, LITERALXML, SPACE,
                         BACKSLASH, SUBEXPRESSION, SUB_NESTED, SUB_END, ARGUMENT,
                         SINGLEQUOTE, DOUBLEQUOTE, EQUALSIGN)

    _optArgX = _tokenSearch(LITERAL, LITERALXML, SPACE,
                            BACKSLASH, SUBEXPRESSION, SUB_NESTED, SUB_END,
                            HIDDEN, ARGUMENT,
                            SINGLEQUOTE, DOUBLEQUOTE)

    def _process_option (self, start, text, pos, instream, argmap):
        option, text, pos, equalsign = \
                self._expandText(text, pos, instream, self._optX,
                                 argmap=argmap,
                                 end=(SPACE, EQUALSIGN))

        if equalsign == '=':
            arg, text, pos, endtoken = \
                 self._expandText(text, pos, instream, self._optArgX,
                                  argmap=argmap,
                                  end=(SPACE,))
        else:
            arg = None

        raise self.Option(option, arg, text, pos)



    #===========================================================================
    ### Processing of "$..." subexpressions

    _subX = _tokenSearch(BACKSLASH, SUBEXPRESSION, SUB_NESTED, SUB_END, ARGUMENT)


    def _process_subexpression (self, start, text, pos, instream, argmap):
        try:
            method = getattr(self, _processing[start])
        except AttributeError as e:
            return start, text, pos
        else:
            arg, text, pos, end = self._expandText(text, pos, instream,
                                                   self._subX,
                                                   argmap=argmap,
                                                   end=(SUB_END,))


            self._check_end(text, pos, start, end)

            try:
                raw = method(arg, **argmap)
                if raw is None:
                    arg = ''
                else:
                    arg = str(raw)

            except Exception as e:
                raw = arg.join((start, end))
                raise ParseError(text, pos, str(e), raw, e, sys.exc_info())

            return arg, text, pos


    _nestedX = _tokenSearch(BACKSLASH, SUBEXPRESSION, SUB_NESTED, SUB_END, ARGUMENT)

    def _process_sub_nested (self, start, text, pos, instream, argmap):
        arg, text, pos, end = self._expandText(text, pos, instream,
                                               self._nestedX,
                                               argmap=argmap,
                                               end=(SUB_END,))

        arg = ''.join([_f for _f in (start, arg, end) if _f])
        return arg, text, pos


    def _process_sub_end (self, start, text, pos, instream, argmap):
        for candidate, methodname in list(_processing.items()):
            if _endTokens[candidate] == start:
                try:
                    getattr(self, methodname)
                except AttributeError:
                    pass
                else:
                    raise ParseError(text, pos, 'Mismatched %r'%start)

        return start, text, pos



    _hiddenX = _tokenSearch(BACKSLASH, HIDDEN_END)

    def _process_hidden (self, start, text, pos, instream, argmap):
        startpos = pos
        arg, text, pos, end = self._expandText(text, pos, instream,
                                               self._hiddenX,
                                               argmap=argmap,
                                               end=(HIDDEN_END,))


        self._check_end(text, pos, start, end)

#        replacement = '.'*len(arg)
        replacement = '*'
        text = text[:startpos] + replacement + end + text[pos:]
        pos  = startpos + len(replacement) + len(end)
        return arg, text, pos


    def _process_argument (self, start, text, pos, instream, argmap):
        try:
            method = self._getInputArgument
        except AttributeError:
            return start, text, pos
        else:
            return method(start[1:], **argmap), text, pos


    #===========================================================================
    ### Processing of quoted subexpressions

    _sqX = _tokenSearch(SINGLEQUOTE)

    def _process_singlequote (self, start, text, pos, instream, argmap):
        arg, text, pos, end = self._expandText(text, pos, instream,
                                               self._sqX,
                                               argmap=argmap,
                                               end=(SINGLEQUOTE,))
        if end != "'":
            raise ParseError(text, pos, 'Missing quote character (\')')

        return arg, text, pos


    _dqX = _tokenSearch(DOUBLEQUOTE, BACKSLASH, SUBEXPRESSION, ARGUMENT)

    def _process_doublequote (self, start, text, pos, instream, argmap):
        startpos = pos
        arg, text, pos, end = self._expandText(text, pos, instream,
                                               self._dqX,
                                               argmap=argmap,
                                               end=(DOUBLEQUOTE,))

        if end != '"':
            raise ParseError(text, pos,
                             'Missing quote character (") after expression: %s'%text[startpos:pos])

        return arg, text, pos



    #===========================================================================
    ### Procssing of <quote<literal text>quote>

    def _process_literal (self, start, text, pos, instream, argmap, reX=_literalX, reEnd='>'):
        tagtype, tag = reX.search(start).groups()

        if tagtype == reEnd:
            raise ParseError(text, pos, 'Mismatched quotation tag: %s'%start)

        balance  = 1
        lines    = [ text ]
        startpos = pos

        while balance > 0:
            match = reX.search(text, pos)
            while match:
                if match.group(2) == tag:
                    balance += (1, -1)[match.group(1) == reEnd]
                    if balance == 0:
                        break

                match = reX.search(text, match.end())

            else:
                try:
                    text = self.readLine(instream)
                    pos  = 0
                    lines.append(text)
                except EOFError:
                    raise ParseError(''.join(lines), None,
                                     'End of input reached within literal quotation "%s"'%(start,))


        text      = ''.join(lines)
        linestart = len(text) - len(lines[-1])
        arg       = text[startpos:linestart+match.start()]
        pos       = linestart + match.end()

        return arg, text, pos




    #===========================================================================
    ### Processing of <quote>literal text</quote>


    def _process_literalxml (self, start, text, pos, instream, argmap):
        return self._process_literal(start, text, pos, instream, argmap,
                                     reX=_literalXmlX, reEnd='/')



    def _process_literal_experimental (self, start, text, pos, instream, argmap):

        slash, tag = _literalXmlX.match(start).groups()
        if slash:
            raise ParseError(text, pos, 'Mismatched quotation tag: %s'%start)

        lines    = [ text ]
        opentag  = '<%s>'%tag
        closetag = '</%s>'%tag
        subtext  = text[pos:]
        balance  = 1 + subtext.count(opentag) - subtext.count(closetag)
        startpos = pos

        try:
            while balance > 0:
                text     = self.readLine(instream)
                balance += text.count(opentag) - text.count(closetag)
                lines.append(text)

        except EOFError:
            raise ParseError(''.join(lines), None,
                             'End of input reached within literal quotation %s'%opentag)

        if balance < 0:
            raise ParseError(text, text.rindex(closetag),
                             'Mismatched quoatation tag: %s'%closetag)


        text  = ''.join(lines)
        pos   = text.rindex(closetag)
        arg   = text[startpos:pos]
        pos  += len(closetag)

        return arg, text, pos


    def _check_end (self, text, pos, start, end):
        if not end:
            raise ParseError(text, pos, 'Missing %r at end of line'%(_endTokens[start]))

        elif end != _endTokens[start]:
            raise ParseError(text, pos, 'Expected %r, not %r'%(_endTokens[start], end))


    matchMethods = {
        LITERAL       : _process_literal,
        LITERALXML    : _process_literalxml,
        SPACE         : _process_space,
        BACKSLASH     : _process_backslash,
        SUBEXPRESSION : _process_subexpression,
        SUB_NESTED    : _process_sub_nested,
        SUB_END       : _process_sub_end,
        HIDDEN        : _process_hidden,
        ARGUMENT      : _process_argument,
        OPTION        : _process_option,
        SINGLEQUOTE   : _process_singlequote,
        DOUBLEQUOTE   : _process_doublequote,
        EQUALSIGN     : _process_equalsign}


    def _expandText (self, text, pos, instream, regexp, argmap={}, skip=(), end=()):
        parts   = []
        token   = None

        while pos < len(text):
            match   = regexp.search(text, pos)
            if not match:
                parts.append(text[pos:])
                pos   = len(text)
                token = None
                break

            index = match.lastindex
            group = match.lastgroup
            token = match.group(index)
            start = match.start(index)
            intro = text[pos:start]
            pos   = match.end(index)

            if intro:
                parts.append(intro)

            elif not parts and group in skip:
                continue

            if group in end:
                parts.append('')
                break

            else:
                method = self.matchMethods[group]
                arg, text, pos = method(self, token, text, pos, instream, argmap)
                if arg is not None:
                    parts.append(arg)


        if parts:
            arg = ''.join(map(str, parts))
        else:
            arg = None

        return arg, text, pos, token


    _escapeChars   = re.compile('(\\n)|(\\r)|(\\t)|(\')|(")|(\\$)|(\\\\)|(\x00-x1F\x7F-xA0)')
    _escapes       = (None, '\\n', '\\r', '\\t', '\\\'', '\\"', '\\$', '\\\\', None)


    def _escape (self, text, pos=0, keep=(), quote=''):
        match = self._escapeChars.search(text, pos)
        parts = [ quote ]

        while match:
            parts.append(text[pos:match.start()])
            char   = match.group()

            if char in keep:
                esc = char

            else:
                esc = self._escapes[match.lastindex] or r'\x%02X'%ord(char)

            parts.append(esc)
            pos    = match.end()
            match  = self._escapeChars.search(text, pos)

        parts.append(text[pos:])
        parts.append(quote)
        return ''.join(parts)



    _unescapeX = re.compile(r'[0-7]{3}|x[0-9a-fA-F]{2}|[0abnfrtv]')
    _unescapeU = re.compile(r'u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}')

    def _unescape (self, text, pos):
        match = self._unescapeX.match(text, pos)
        if match:
            return eval('"\\%s"'%match.group()), text, match.end()

        match = self._unescapeU.match(text, pos)
        if match:
            code = int(match.group()[1:], 16)
            return chr(code), text, match.end()

        return text[pos], text, pos+1


    _protectX  = _tokenSearch(SINGLEQUOTE, DOUBLEQUOTE, BACKSLASH, SPACE)
    _tagSplitX = _tokenSearch(LITERAL)

    _alreadyQuotedX = re.compile(r'''(['"])(?:.*?[^\\])?(?:\\\\)*(?:\1)''')

    def toString (self, text, encoding="UTF-8"):
        if text is None:
            text = ''

        elif isinstance(text, (bytes, bytearray)):
            text = text.decode(encoding)

        elif not isinstance(text, str):
            text = str(text)

        return text


    def protectString (self, text, tag=None, quoting=QUOTE_AUTO):
        tagPrefix = None
        string = self.toString(text)

        if quoting == QUOTE_ALWAYS:
            return self._escape(string, keep="'", quote='"')

        if tag is not None:
            match = _protectTags.search(string)
            if match:
                if tag:
                    tagPrefix = match.lastgroup
                    basetag = "%s.%s"%(tagPrefix, tag)
                    idx     = 0
                    while basetag in string:
                        idx += 1
                        basetag = "%s.%s%d"%(tagPrefix, tag, idx)

                    opentag  = "<%s>%s"%(basetag, ("\n", "")[string.startswith("\n")])
                    closetag = "</%s>"%(basetag,)

                else:
                    opentag  = "<<<"
                    closetag = ">>>"

                return string.join((opentag, closetag))

        if (quoting != QUOTE_NEVER) and _protectEscapes.search(string):
            if quoting == QUOTE_NEVER:
                keep  = ()
                quote = None

            elif quoting == QUOTE_ALWAYS:
                keep  = ("'",)
                quote = '"'

            else:
                keep  = ("'",)
                quote = '"'

            return self._escape(string, keep=keep, quote=quote)

        else:
            return string


    def readLine (self, instream):
        try:
            text = instream.readline()
        except (AttributeError, socket.error):
            raise EOFError
        else:
            if not text:
                raise EOFError

        if isinstance(text, bytes):
            try:
                text = text.decode()
            except UnicodeDecodeError:
                ### Failed to decode with default conversion (normally UTF8).
                ### Try again with `latin1`, where anything goes.
                text = text.decode('latin1')

        return text


parser = CommandParser()
