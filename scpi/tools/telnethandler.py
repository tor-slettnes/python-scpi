#===============================================================================
## @file telnetserver.py
## @brief Handle incoming connections from telnet clients
## @author Tor Slettnes <tor@slett.net>
##
#===============================================================================

### Standard Python modules
from telnetlib   import Telnet, IAC, DONT, DO, WONT, WILL, ECHO, SGA, NAWS, TTYPE, NEW_ENVIRON, SB, SE
from socket      import error as SocketError
from threading   import Lock
from weakref     import proxy
#from traceback   import print_exc

import sys

affirm = { DO:WILL, DONT:WONT, WILL:DO,   WONT:DONT }
reject = { DO:WONT, DONT:WONT, WILL:DONT, WONT:DONT }


usage = '''\r
=== Legend: ===\r
    C-<X> means hold [Control] key and press <X>.\r
    M-<X> means hold [Meta] or [Alt] key and press <X>, or press [ESC] then <X>.\r
\r
=== Editing keys: ===\r
    C-P, Up          - Go backward in command history (recall previous command)\r
    C-N, Down        - Go forward in command history\r
    C-B, Left        - Move cursor one character to the left\r
    C-F, Right       - Move cursor one character to the right\r
    M-B, M-Left      - Move cursor one word to the left\r
    M-F, M-Right     - Move cursor one word to the right\r
    C-A, Home        - Move cursor to beginning of line\r
    C-E, End         - Move cursor to end of line\r
    Backspace        - Erase previous character\r
    C-D, Fwd Delete  - Erase character under cursor\r
    C-W              - Cut from mark to current position, or last word\r
    M-D              - Cut word under cursor\r
    C-K              - Cut remainder of line\r
    C-Space, M-Space - Set mark\r
    C-G              - Clear mark\r
    C-X              - Set mark, or cut from mark to current position\r
    C-C, M-W         - Copy from mark to current position\r
    C-V, C-Y         - Yank (paste)\r
    C-U              - Cut entire line\r
    M-H, F1          - Print this text\r
\r
'''


### There is a bug in Python's "telnetlib", wherein null characters in IAC sequences are suppressed.
### It does so by comparing against "theNULL", so we'll override that to prevent this supression.

import telnetlib
telnetlib.theNULL = None

ControlSequences = {
    None      : (b"\x1b[H\x1b[J", b"\x1b[K", b"\x1b[31m", b"\x1b[36;1m", b"\x1b[34;47m", b"\x1b[0m"),       # Initial (before negotiation)
    "_default": (b"\x1b[H\x1b[J", b"\x1b[K", b"\x1b[31m", b"\x1b[34;48;5;15m", b"\x1b[34;46m", b"\x1b[0m"), # Default: Blue on white.
    b"ANSI"   : (b"\x1b[H\x1b[J", b"\x1b[K", b"\x1b[31m", b"\x1b[36;1m", b"\x1b[36;47;1m", b"\x1b[0m"),     # Windows telnet: Cyan on black.
    b"LINUX"  : (b"\x1b[H\x1b[J", b"\x1b[K", b"\x1b[31m", b"\x1b[36;1m", b"\x1b[36;47;1m", b"\x1b[0m")      # Linux console: Cyan on black.
}

(CLEARSCREEN, CLEARLINE, PROMPT, INPUT, HIGHLIGHT, RESET) = list(range(len(ControlSequences[None])))

class TelnetHandler (Telnet):
    def __init__ (self, socket, intro="\n* Press [ESC] then [H] for help on editing.\n"):
        Telnet.__init__ (self)
        self.sock             = socket
        self.doEcho           = False
        self.terminaltype     = ''
        self.control          = ControlSequences[None]
        self.prompt           = ""
        self.inputLine        = b''
        self.inputPos         = None
        self.markpos          = None
        self.endOfInputColumn = 0
        self.inputColumns     = 80
        self.receiveBuffer    = []
        self.cutBuffer        = b''
        self.history          = []
        self.historyIndex     = 0
        self.mutex            = Lock()
        self.completionMethod = None

        self.set_option_negotiation_callback(self.handleRequest)

        self.negotiate(IAC, WILL, SGA)   # Suppress GoAhead
        self.negotiate(IAC, WILL, ECHO)  # Echo from server
        self.negotiate(IAC, DONT, ECHO)  # Not from client
        self.negotiate(IAC, DO,   NAWS)  # Negotiate about window size

        self.negotiate(IAC, DO, TTYPE)  # Negotiate about terminal type
        self.negotiate(IAC, SB, TTYPE, ECHO, IAC, SE) # Ask for terminal type

#        self.negotiate(IAC, DO, NEW_ENVIRON) # Negotiate about environment
#        self.negotiate(IAC, SB, NEW_ENVIRON, ECHO, IAC, SE) # Ask for environment

        self.setprompt()

        if intro:
            self.send(intro.replace('\n', '\r\n').encode() + b'\n')

    def negotiate (self, *sequence):
        self.sock.sendall(b"".join(sequence))


    def handleRequest (self, socket, command, option):
        if command in (DO, DONT):
            request = (command, option)
            handled = True

            if request in ((DO, ECHO), (WONT, ECHO)):
                self.doEcho = True

            elif request in ((DONT, ECHO), (WILL, ECHO)):
                self.doEcho = False

            elif request in ((DO, SGA), (DONT, SGA)):
                pass

            else:
                handled = False

            response = (handled and affirm[command] or reject[command])
            if self.sock:
                self.negotiate(IAC, response, option)

        elif command == SE:
            self.handleSubRequest()


    def handleSubRequest (self):
        data   = self.read_sb_data()
        option = data[0]
        if option == NAWS:
            columns = ord(data[1])<<8 | ord(data[2])
            if columns != 0:
                self.inputColumns = columns
                self.echoInput()

        elif option == TTYPE:
            self.terminaltype = terminal = data[2:]
            try:
                self.control = ControlSequences[terminal.upper()]
            except KeyError:
                self.control = ControlSequences["_default"]

#        elif option == NEW_ENVIRON:
#            print("Client environment received: %r"%(data))


    def read_at_most_one_line (self):
        if not self.receiveBuffer:
            newtext = self.read_some().replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            self.receiveBuffer.extend(newtext.splitlines(True))

        try:
            return self.receiveBuffer.pop(0)
        except IndexError:
            raise EOFError


    def setprompt (self, prompt=">"):
        self.prompt = prompt


    def readline (self):
        try:
            return self._readline()
        except EOFError:
            pass

    def _readline (self):
        historyIndex      = len(self.history)
        self.inputLine    = b""
        self.inputPos     = 0
        self.markpos      = None
        self.history.append(self.inputLine)


        while True:
            pos    = min(self.inputPos, len(self.inputLine))

            try:
                self.echoInput()
            except SocketError:
                return None

            chars = self.read_at_most_one_line()

            if chars == b'\x1b':                         # Esape key
                self.echoInput(prefix="[ESC]")
                chars += self.read_at_most_one_line()


            if chars in (b'\x1b[A', b'\x1bOA', b'\x10'):   # C-P, Up
                if historyIndex:
                    if historyIndex == len(self.history) - 1:
                        self.history[historyIndex] = self.inputLine

                    historyIndex    -= 1
                    self.inputLine = self.history[historyIndex]
                    self.inputPos  = len(self.inputLine)
                    self.markpos   = None


            elif chars in (b'\x1b[B', b'\x1bOB', b'\x0e'): # C-N, Down
                if historyIndex < len(self.history) - 1:
                    historyIndex    += 1
                    self.inputLine = self.history[historyIndex]
                    self.inputPos  = len(self.inputLine)
                    self.markpos   = None


            elif chars in (b'\x02', b'\x1b[D', b'\x1bOD'): # C-B, Left
                if pos:
                    self.inputPos = pos-1

            elif chars in (b'\x06', b'\x1b[C', b'\x1bOC'): # C-F, Right
                if pos < len(self.inputLine):
                    self.inputPos = pos+1

            elif chars in (b'\x01', b'\x1b[7~', b'\x1bOH', b'\x1b[1~'):          # C-A, Home
                self.inputPos = 0

            elif chars in (b'\x05', b'\x1b[8~', b'\x1bOF', b'\x1b[4~'):          # C-E, End
                self.inputPos = len(self.inputLine)

            elif chars in (b'\x08', b'\x7F'):             # Backspace, Delete
                self.markpos = None
                if pos:
                    self.inputPos  = pos - 1
                    self.inputLine = self.inputLine[:self.inputPos] + self.inputLine[self.inputPos+1:]

            elif chars in (b'\x1b[3~', ):                # Delete (forward)
                self.markpos   = None
                self.inputPos  = pos
                self.inputLine = self.inputLine[:self.inputPos] + self.inputLine[self.inputPos+1:]

            elif chars in (b'\x04',):                    # C-D: Delete character or end session
                self.markpos = None
                if self.inputLine:
                    self.inputPos  = pos
                    self.inputLine = self.inputLine[:self.inputPos] + self.inputLine[self.inputPos+1:]
                else:
                    break

            elif chars in (b'\x00', b'\x1b '):             # C-@ (C-Space), M-Space: Set/clear mark
                self.markpos = pos

            elif chars in (b'\x07', ):                    # C-G: Clear mark/cancel
                self.markpos = None

            elif chars in (b'\x19', b'\x16'):              # C-Y, C-V: Yank/Paste
                if self.markpos is not None:
                    start = min(self.markpos, pos)
                    end   = max(self.markpos, pos)
                    self.markpos = None
                else:
                    start = end = pos

                self.inputLine = self.inputLine[:start] + self.cutBuffer + self.inputLine[end:]
                self.inputPos  = start + len(self.cutBuffer)

            elif chars in (b'\x17',):                    # C-W: Kill region, or word backwards
                if self.markpos is not None:
                    start = min(self.markpos, pos)
                    end   = max(self.markpos, pos)
                    self.markpos = None

                elif pos:
                    end   = pos
                    start = self._prevWordPos(self.inputLine, end)

                else:
                    start = end = None

                if start < end:
                    self.cutBuffer = self.inputLine[start:end]
                    self.inputLine = self.inputLine[:start] + self.inputLine[end:]
                    self.inputPos  = start

            elif chars in (b'\x18',):                    # C-X: Set mark, or cut region
                if self.markpos is not None:
                    start = min(self.markpos, pos)
                    end   = max(self.markpos, pos)
                    self.cutBuffer = self.inputLine[start:end]
                    self.inputLine = self.inputLine[:start] + self.inputLine[end:]
                    self.inputPos  = start
                    self.markpos   = None
                else:
                    self.markpos   = pos


            elif chars.upper() in (b'\x1bW', b'\x03'):    # C-C, M-W: Copy region
                if self.markpos is not None:
                    start = min(self.markpos, pos)
                    end   = max(self.markpos, pos)
                    self.markpos = None
                    self.cutBuffer = self.inputLine[start:end]

            elif chars.upper() in (b'\x1bD',):            # M-D: Kill word forward
                self.inputPos = pos
                pos = self._nextWordPos(self.inputLine, pos)
                self.cutBuffer = self.inputLine[self.inputPos:pos]
                self.inputLine = self.inputLine[:self.inputPos] + self.inputLine[pos:]
                self.markpos   = None

            elif chars.upper() in (b'\x1bB', b'\x1b[2D' b'\x1b[3D', b'\x1b[5D'):   # M-B, M-Left: Previous word
                self.inputPos = self._prevWordPos(self.inputLine, pos)

            elif chars.upper() in (b'\x1bF', b'\x1b[2C' b'\x1b[3C', b'\x1b[5C'):   # M-F, M-Right: Next word
                self.inputPos = self._nextWordPos(self.inputLine, pos)

            elif chars in (b'\x15',):                     # C-U: Kill line
                self.cutBuffer = self.inputLine
                self.markpos   = None
                self.inputLine = b""
                self.inputPos = 0

            elif chars in (b'\x0b',):                     # C-K: Kill remainder of line
                self.cutBuffer = self.inputLine[self.inputPos:]
                self.markpos   = None
                self.inputLine = self.inputLine[:self.inputPos]
                self.inputPos  = pos

            elif chars in (b'\x0c',):                     # C-L: Clear screen
                self.clearScreen()

            elif chars in (b'\x09',):                     # TAB: Autocomplete
                while pos < len(self.inputLine) and self.inputLine[pos:pos+1].isalpha():
                    pos += 1

                self.inputLine = self.autoComplete()

            elif chars.upper() in (b'\x1bH', b'\x1b[11~', b'\x1bOP'):  # M-H, F1: Help
                self._write(usage.encode())

            elif (chars >= b' ') or chars.isspace():     # Printable characters
                ### Remove input prompt from start of input
                ### (to allow copy/paste of multiple lines)
                self.markpos = None

                if len(chars) > 1 and chars[0] == b">":
                    chars = chars[1:]

                self.inputLine = (self.inputLine[:pos] +
                                  chars.rstrip(b'\n') +
                                  self.inputLine[pos:])

                if chars.endswith(b'\n'):
                    self.history[-1] = self.inputLine
                    self.inputLine += b'\n'
                    break

                self.inputPos = pos + len(chars)


        line = self.inputLine
        if line:
            self.echoInput()
            self.inputLine = b""
        else:
            self.send(b"\r" + self.control[CLEARLINE])

        self.inputPos = None
        return line


    def __iter__ (self):
        return self


    def __next__ (self):
        line = self.readline()
        if line:
            return line
        else:
            raise StopIteration


    def send (self, buffer):
        if self.sock:
            Telnet.write(self, buffer)

    def write (self, data):
        self._write(data)
        self.echoInput()

    def _write (self, data):
        data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n').replace(b'\n', b'\r\n')
        if self.inputPos is not None:
            data = b'\r' + self.control[CLEARLINE] + data
        self.send(data)
        return b'\n' in data

    def flush (self):
        pass

    def _prevWordPos (self, text, pos):
        while pos and not text[pos-1:pos].isalnum():
            pos -= 1

        foundUpper = False
        while pos and text[pos-1:pos].isalnum():
            if text[pos-1:pos].isupper():
                foundUpper = True
            elif foundUpper:
                break
            pos -= 1

        return pos


    def _nextWordPos (self, text, pos):
        foundLower = False
        while pos < len(text) and text[pos:pos+1].isalnum():
            if text[pos:pos+1].islower():
                foundLower = True
            elif foundLower:
                break
            pos += 1

        while pos < len(text) and not text[pos:pos+1].isalnum():
            pos += 1

        return pos


    def echoInput (self, prefix=None):
        inputPos = self.inputPos

        if inputPos is not None:
            with self.mutex:
                prompt    = ((prefix or "") + self.prompt).encode()
                inputPos  = min(len(self.inputLine), inputPos)
                maxlen    = self.inputColumns - len(prompt) - 1
                start     = max(0, inputPos - maxlen/2)
                end       = min(start + maxlen, len(self.inputLine))
                start     = max(0, end - maxlen)
                visible   = end - start
                line      = self.inputLine.rstrip(b'\n')
                eol       = self.inputLine.endswith(b'\n')

                if self.markpos is not None:
                    mstart = min(self.markpos, inputPos)
                    mend   = max(self.markpos, inputPos)
                else:
                    mstart = None
                    mend   = None

                surplus   = max(0, self.endOfInputColumn - len(prompt) - visible)
                parts     = [b'\r', self.control[PROMPT], prompt]
                self.endOfInputColumn = len(prompt)

                if mend is not None and (mend > start) and (mstart < end):
                    parts.extend([self.control[INPUT], line[start:min(mstart, end)],
                                  self.control[HIGHLIGHT], line[max(start, mstart):min(end, mend)], self.control[RESET],
                                  self.control[INPUT], line[max(start, mend):end]])
                else:
                    parts.extend([self.control[INPUT], line[start:end]])

                parts.append(self.control[CLEARLINE])
                parts.append(self.control[RESET])
                parts.append(b'\x08' * (end - inputPos))

                if eol:
                    parts.append(b'\r\n')
                else:
                    self.endOfInputColumn += visible

                self.send(b''.join(parts))


    def clearScreen (self):
        self.send(self.control[CLEARSCREEN])


    def autoComplete (self):
        method = self.completionMethod
        if method and self.inputPos is not None:
            first, second = self.inputLine[:self.inputPos], self.inputLine[self.inputPos:]

            completion = method(first.decode())
            if not completion:
                self.send(b'\x07') # Bell

            elif len(completion) == 1:
                self.inputLine = completion[0].encode() + second
                self.inputPos  = len(completion[0])

            else:
                longest  = max([len(s) for s in completion])
                colwidth = longest+4
                columns  = max(1, self.inputColumns / colwidth)

                words = []
                for index, word in enumerate(completion):
                    if (index%columns == columns-1) or (index == len(completion)-1):
                        words.append((word+"\n").encode())
                    else:
                        words.append(word.ljust(colwidth).encode())

                self._write(b''.join(words))

        return self.inputLine

    def setAutoComplete (self, method):
        self.completionMethod = method
