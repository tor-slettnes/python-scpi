#!/usr/bin/python
#===============================================================================
## @file timeformat.py
## @brief Time functions
## @author Tor Slettnes <tor@slett.net>
#===============================================================================

import re, time, calendar

class Time (object):
    __slots__ = ('timestamp',)

    def __init__ (self, timestamp=None):
        if timestamp is None:
            self.timestamp = time.time()
        else:
            self.timestamp = timestamp

    def asStruct (self, local=True):
        return local and time.localtime(self.timestamp) or time.gmtime(self.timestamp)

    def isdst (self, local=True):
        return local and time.daylight and time.localtime(self.timestamp).tm_isdst or 0

    def tzoffset (self, local=True):
        if local:
            offset = (time.timezone, time.altzone)[self.isdst(local)]
        else:
            offset = 0
        return -offset

    def zone (self, local=True, separator=':', precision=2):
        offset = self.tzoffset(local)
        h, m, s = offset/3600, (abs(offset)%3600)/60, (abs(offset)%60)

        hs = "%+03d"%h
        ms = ("", "%02d"%m)[bool(m or s or precision>1)]
        ss = ("", "%02d"%s)[bool(s or precision>2)]
        return separator.join([_f for _f in (hs, ms, ss) if _f])


    def zonename (self, local=True):
        if local:
            name = time.tzname(self.isdst(local))
            return "".join([c for c in name if c.isupper()])
        else:
            return "UTC"

    _fmt = re.compile(r'(?:^|(?<=[^%]))(?:%%)*(%(?:(\:{0,3})(z)|(Z)|\.(\d)))')

    def format (self, fmt, local=True):
        parts = []
        pos   = 0
        for match in self._fmt.finditer(fmt):
            All, NumZonePfx, NumZone, ZoneName, Decimals = match.groups('')
            parts.append(fmt[pos:match.start(1)])
            #m = match.groupdict()
            if NumZone:
                precision = (len(NumZonePfx or ":")+1, 0)[len(NumZonePfx)==3]
                separator = NumZonePfx[:1]
                parts.append(self.zone(local, separator, precision))
            elif ZoneName:
                parts.append(self.zonename(local))
            elif Decimals:
                decimals   = int(Decimals)
                multiplier = 10**decimals
                parts.append(".%0*d"%(decimals, int(self.timestamp*multiplier)%multiplier))
            pos = match.end()

        parts.append(fmt[pos:])
        return time.strftime(''.join(parts), self.asStruct(local))

    def isoformat (self, local=True, delimiter='T', suffix=True, separator="", zulu=False, decimals=0):
        fmt  = delimiter.join(("%F", "%T"))
        if decimals:
            fmt += "%."+str(decimals)

        iso  = self.format(fmt, local and not zulu)
        if suffix:
            iso += zulu and 'Z' or self.zone(local, separator)
        return iso

    _iso = re.compile(r'(?:(\d+)-(\d+)-(\d+))?[\sT]?(?:(\d+)\:(\d+)(?:\:(\d+))?(?:\.(\d+))?)?'
                      r'\s*(?:(?P<zulu>Z)|(?P<offset>[\+-]\d{2})\:?(\d{2})?\:?(\d{2})?)?$')

    @classmethod
    def fromiso (cls, isostring, local=True):
        match = cls._iso.match(isostring)
        if not match:
            raise ValueError("time data '%s' does not match ISO 8601 format")

        groups = match.groups(0)
        (Y, M, D, h, m, s) = [int(group) for group in groups[:6]]
        if match.group('zulu'):
            local = False
        elif match.group('offset'):
            local = False
            ho, mo, so = [int(group) for group in groups[7:10]]
            h -= ho
            m = (m+mo, m-mo)[ho>0]
            s = (s+so, s-so)[ho>0]

        struct = (Y, M, D, h, m, s, 0, 0, -1)
        if local:
            timestamp = time.mktime(struct)
        else:
            timestamp = calendar.timegm(struct)

        return cls(timestamp)

