#!/usr/bin/python
#===============================================================================
## @file scpiDocumentGenerator.py
## @brief Document SCPI commands available from a server
#===============================================================================

### Modules relative to install folder
from ..client import SCPIClient, OK, ERROR, SCPIError, ACCESS_ADMINISTRATOR

### Standard Python modules
from optparse         import OptionParser
from xhtmlGenerator   import HTMLPage
from xml.dom.minidom  import parseString
from xml.sax.saxutils import escape
from os               import makedirs
from os.path          import isdir, join, basename
from re               import compile, MULTILINE
from sys              import stdout, stderr, argv
from time             import strftime
from socket           import gethostname

version    = "0.1"
varX       = compile(r'(&lt;\S+&gt;)')
indentX    = compile(r'\n( *)')
sectionX   = compile(r'^(\S+:)', MULTILINE)

seen       = {}


def getOptions (version, defaulthost="localhost", defaultport=7000):
    parser = OptionParser()

    parser.add_option(
        "-s", "--server",
        dest="server", nargs=1, default="localhost",
        help="Host on which the SCPI server is running [%default]")

    parser.add_option(
        "-p", "--port",
        dest="port", nargs=1, default=7000,
        help="TCP port on which the SCPI server is listening [%default]")

    parser.add_option(
        "-d", "--directory",
        dest="directory", nargs=1, default="commandset",
        help="Top-level directory in which HTML files will be saved [%default]")

    parser.add_option(
        "-b", "--branch",
        dest="branch", nargs=1, default="",
        help="List command only within a given branch/scope.")

    parser.add_option(
        "-q", "--quiet",
        dest="quiet", action='store_true', default=False,
        help='Be vewwwy quiet (I am hunting wabbits)')

    parser.add_option(
        "-f", "--full",
        dest="full", action='store_true', default=False,
        help="Full descriptions; do not cross-reference duplicate commands")

    parser.add_option(
        "--short",
        dest="short", action='store_true', default=False,
        help="Short list; only unique commands for each branch is included")

    options, args = parser.parse_args()
    return options, args



def _getServerInfo (scpi, branch, item, default=None):
    try:
        status, reply = scpi.sendReceive("%s:%s"%(branch, item))
        return reply
    except SCPIError:
        return default


def getServerInfo (scpi, branch):
    product = _getServerInfo(scpi, branch, 'PRODuct?')
    version = _getServerInfo(scpi, branch, 'VERSion?')
    return ' version '.join([ item for item in (product, version) if item ])


def sendReceive (scpi, command, decompose=False, timeout=60.0):
    status, response  = scpi.sendReceive(command, timeout=timeout, decompose=decompose)
    if outputs:
        return outputs[0]


def generate ():
    options, args  = getOptions(version)
    connection     = SCPIClient(access=ACCESS_ADMINISTRATOR)
    connection.connect((options.server, int(options.port)))
    server         = getServerInfo(connection, 'SYSTem')   or '&lt;Unknown&gt;'
    return generatePage(connection, server,
                        options.directory,"", options)



def generatePage (scpi, server, directory, branch, options):

    title = "%s Commands"%(branch or "Top-Level")

    page = HTMLPage()
    head = page.head()
    head.title("%s: %s"%(server, title))
    head.link(href="style.css", rel="stylesheet", type="text/css")

    body = page.body()
    body.h1(title, style="text-align:center;")

    fields = (('Date',      strftime('%F %R')),
              ('Generator', '%s on %s'%(basename(argv[0]), gethostname())),
              ('Server',    '%s on %s:%d'%(server,
                                           options.server, int(options.port))))

    buildTable(body, fields)

    subbranches = generateCommandList(scpi, branch, options, body)
    saveFile(directory, 'index.html', page())

    for subbranch in subbranches:
        try:
            dirpath = join(directory, subbranch.lower())
            cmdpath = ":".join([_f for _f in (branch, subbranch) if _f])

            generatePage(scpi, server, dirpath, cmdpath, options)
        except Exception as e:
            stderr.write('While documenting %s%s%s\n### %s\n'%
                         (branch, branch and ":", subbranch, e))



def buildTable (html, items):
    table = html.table()
    for key, value in items:
        row  = table.tr(style='vertical-align:top;')
        cell = row.td(style='text-align:right;').b(key+':')
        cell = row.td(value)




def generateCommandList (scpi, branch, options, body):

    if branch:
        branch += ":"

        p = body.p(style='text-align: center')
        p.add('[')
        p.a(href="../index.html").i('Up one level')
        p.add(']')

    print(("Generating command list in branch %r"%(branch,)))

    command = [ branch + "@" ]

    if options.short:
        command.append("-unique")

    status, response, keywords = scpi.sendReceive(command, decompose=True)

    body.h2('Overview:')
    tocstyle   = 'margin-left: 100px; border-width:0; border-spacing:0; padding:10;'
    toc        = body.table(style=tocstyle)

    body.hr()
    body.h2('Descriptions:')
    desc = body

    uniques    = []
    duplicates = []
    branches   = []

    for line in response[0].splitlines():
        text, parts = scpi.expandArgs(line)
        if not parts:
            continue

        args, props, text = scpi.decomposeParts(parts)
        command = args[0]


        if not options.quiet:
            stdout.write('Processing %s%s: '%(branch, command))

        if eval(props['branch']):
            ref = '%s/index.html'%(command.lower(),)
            branches.append(command)
        else:
            ref = 'index.html#%s'%(command,)


        status, outputs, keywords = scpi.sendReceive((branch + "HELP?", command), decompose=True)
        helpText, = outputs


        ### Compare help text with prior texts to identify duplicates
        crossref = None
        if not options.full:
            try:
                crossref = seen[helpText]
            except KeyError:
                if not branch:
                    seen[helpText] = branch.replace(':', '/').lower() + ref
            else:
                ref         = ("../" * branch.count(':')) + crossref
                stdout.write('Linking to %s\n'%ref)

        if crossref:
            duplicates.append((command, props['type'], ref))
        else:
            stdout.write('Generating description\n')
            desc.a(name=command)
            desc.hr()
            desc.h3(branch+command)
            desc.hr()
            describeInformally(desc, helpText)

            uniques.append((command, props['type'], ref))


    sections = (('%s Commands'%(branch.rstrip(':') or 'Top-Level'), uniques),
                ('Duplicate Commands', duplicates))

    for header, data in sections:
        if data:
            row = toc.tr()
            row.th(style='text-align: left').b(header)
            row.th(style='text-align: left').b(': Type')

            for command, kind, ref in data:
                row = toc.tr()
                row.td().a(branch + command, href=ref)
                row.td(': %s'%kind)

            row = toc.tr()
            row.td()
            row.td()


    return branches



def describeInformally (html, helpText):
    helpText = varX.sub(r"<i>\1</i>", escape(helpText))
    helpText = sectionX.sub(r'<b>\1</b>', helpText)
    html.pre(helpText)


def saveFile (directory, filename, lines):
    if not isdir(directory):
        makedirs(directory)

    outfile = file(join(directory, filename), 'w')
    outfile.writelines(lines)


if __name__ == '__main__':
    generate()
