#!/usr/bin/python2.7

import sys
import re
import logging
import os

# munge sys.path

_d = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_d, '../src'))

import config as _config
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
    drivers, tags, pat, use_unit = _config.readCmdLine(sys.argv[1:])
    res=0
    import runtests
    for d, connectArgs in drivers.items():
        _config.DRIVER = d
        initAlias(**connectArgs)
        curtags=list(tags)+[d]
        # clean up existing sqlite db
        if d.startswith('sqlite'):
            _ca = connectArgs['connectArgs']
            # print("d=%r _ca=%r" % (d, _ca))
            db = _ca['database']
            if db != ':memory:' and os.path.exists(db):
                os.remove(db)
        if tags:
            info("testing with driver: %s, tags: %s", d, ", ".join(tags))
        else:
            info("testing with driver: %s", d)
        try:
            res |= runModule(runtests, curtags, pat, use_unit)
        finally:
            delAlias('pydotest')
            del _config.DRIVER
    sys.exit(res)
