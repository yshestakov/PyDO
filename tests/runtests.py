#! /usr/bin/env python2.4

import sys
import re
import logging

# munge sys.path

sys.path.insert(0, '../src')

import config
from testingtesting import runNamespace, info, runModule, _defaultNamePat, _testsForModule
from pydo import initAlias, delAlias, setLogLevel

setLogLevel(logging.DEBUG)

# import the actual tests
from test_base import *
from test_dbi import *
from test_dbtypes import *
from test_fields import *
from test_guesscache import *
from test_multifetch import *
from test_operators import *

if __name__=='__main__':
    drivers, tags, pat, use_unit=config.readCmdLine(sys.argv[1:])
    res=0
    import runtests
    for d, connectArgs in drivers.iteritems():
        initAlias(**connectArgs)
        curtags=list(tags)+[d]
        if tags:
            info("testing with driver: %s, tags: %s", d, ", ".join(tags))
        else:
            info("testing with driver: %s", d)
        config.DRIVER=d
        try:
            res |= runModule(runtests, curtags, pat, use_unit)
        finally:
            delAlias('pydotest')
            del config.DRIVER
    sys.exit(res)
