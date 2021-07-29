"""

contains utility functions for obtaining configuration data for the pydo tests --
either from command line or a config file

"""

import optparse
import os
import re
import sys
import traceback
from pydo.dbi import initAlias, _driverConfig
from testingtesting import _defaultNamePat

DEFAULT_CONFIG='~/.pydotestrc'

ALLDRIVERS=_driverConfig.keys()

def _readConfigFile(fname=DEFAULT_CONFIG):
    fname=os.path.expanduser(fname)
    d={}
    if os.path.exists(fname):
        execfile(fname, {}, d)
    return d

def readCmdLine(args, usage=None):
    if usage:
        parser=optparse.OptionParser(usage=usage)
    else:
        parser=optparse.OptionParser()
    parser.add_option('-c', '--config',
                      dest='config',
                      help='config file to read (default: ~/.pydotestrc)',
                      default='~/.pydotestrc',
                      metavar='CONFIG',
                      action='store')
    parser.add_option('-d', '--drivers',
                      dest='drivers',
                      help='drivers to test against',
                      metavar='DRIVERS',
                      action='store')
    parser.add_option('-t', '--tags',
                      dest='tags',
                      help='tags to use',
                      metavar='TAGS',
                      action='store')
    parser.add_option('-v', '--verbose',
                      dest='verbose',
                      help="whether to be verbose",
                      action='store_true',
                      default=None)
    parser.add_option('-p',
                      '--pattern',
                      dest='pattern',
                      help="pattern to match against to find tests by name",
                      metavar='PATTERN',
                      action='store')
    parser.add_option('-u',
                      '--unittest',
                      dest='unittest',
                      help="use unittest module",
                      metavar='WITH_UNITTEST',
                      action='store_true',
                      default=False)
    opts, args=parser.parse_args(args)
    try:
        c=_readConfigFile(opts.config)
    except:
        traceback.print_exc()
        parser.error("error reading config file!")

    if not opts.tags:
        tags=set()
    else:
        tags=set(opts.tags.split())
    possdrivers=set(ALLDRIVERS)        
    if not opts.drivers:
        drivers=possdrivers
    else:
        drivers=set(opts.drivers.split())
        if not drivers.issubset(possdrivers):
            parser.error("unrecognized driver(s): %s" % ', '.join(drivers.difference(possdrivers)))

    retdrivers={}
    # init all the aliases
    for d in drivers:
        try:
            connectArgs=c[d]
        except:
            print >> sys.stderr, "no config for driver: %s" % d
        else:
            connectArgs['driver']=d
            if opts.verbose is not None:
                connectArgs['verbose']=opts.verbose
            # the connection alias will always be "pydotest"
            connectArgs['alias']='pydotest'
            if not isinstance(connectArgs, dict):
                parser.error("configuration error: must be a dict, got a %s" % type(connectArgs))
            retdrivers[d]=connectArgs

    if opts.pattern:
        try:
            pat=re.compile(opts.pattern)
        except re.error:
            parser.error("error: invalid regular expression: %s" % opts.pattern)
    else:
        pat=_defaultNamePat    

    return retdrivers, tags, pat, opts.unittest


