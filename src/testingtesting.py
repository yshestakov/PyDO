"""
a very very simple test framework.
"""

import re
import sys
import types
import logging
import unittest

logger=logging.getLogger('testingtesting')
exception=logger.exception
info=logger.info
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate=False
_defaultNamePat=re.compile(r'^test')

def _testsForModule(m, namePat, tags):
    return _testsForNamespace(vars(m), namePat, tags)

def _testsForNamespace(ns, namePat, tags):
    for name, value in sorted(ns.iteritems()):
        if callable(value) and namePat.search(name):
            ftags=getattr(value, 'tags', None)
            if not ftags:
                yield value
            else:
                if set(tags).issubset(ftags):
                    yield value
            
def runtests(tests, with_unittest=False):
    if with_unittest:
        return runtests_with_unittest(tests)
    success=[]
    fail=[]
    for i, t in enumerate(tests):
        if type(t)==types.TypeType:
            name=t.__name__
            t=t()
            if not callable(t):
                continue
        else:
            name=t.__name__
        i+=1
        info('running test no %d (%s)', i, name)

        try:
            t()
        except:
            exception("test no. %d (%s)  failed", i, name)
            fail.append((t, sys.exc_info()))
        else:
            info('test %s passed', name)
            success.append(t)
    summarize_tests(success, fail)
    if fail:
        return 1
    return 0

def runtests_with_unittest(tests):
    cases=[unittest.FunctionTestCase(x) for x in tests]
    suite=unittest.TestSuite(cases)
    runner=unittest.TextTestRunner(verbosity=2)
    result=runner.run(suite)
    return not result.wasSuccessful()

def runModule(m, tags=None, namePat=_defaultNamePat, with_unittest=False):
    return runtests(_testsForModule(m, namePat, tags), with_unittest)

def runNamespace(tags=None, ns=None, namePat=_defaultNamePat, with_unittest=False):
    if ns is None:
        ns=globals()
    return runtests(_testsForNamespace(ns, namePat, tags), with_unittest)

def summarize_tests(success, fail):
    total=len(success)+len(fail)
    if total == 1:
        TESTS='test'
    else:
        TESTS='tests'
    info("%d %s run; passed: %d, failed: %d",
         total,
         TESTS,
         len(success),
         len(fail))

def tag(*tags):
    """ decorator for tests """
    def wrapper(func):
        func.tags=tags
        return func
    return wrapper


__all__=['runModule', 'runNamespace', 'info', 'tag']    

@tag('choo')    
def test_anything():
    assert 1==1

@tag('foo')
def test_anotherthing():
    # this one will fail
    assert 2==1, "2 should equal 1"

@tag('foo', 'choo')
def test_exception():
    try:
        1 / 0
    except ZeroDivisionError:
        x=1
    else:
        x=0
    assert x==1

if __name__=='__main__':
    import optparse
    parser=optparse.OptionParser('usage: %prog [options] [tags....]')
    parser.add_option('-p',
                      '--pattern',
                      dest='pattern',
                      help="pattern to match against to find tests by name",
                      metavar='PATTERN',
                      action='store')
    opts, tags=parser.parse_args(sys.argv[1:])
    logger.setLevel(logging.INFO)
    info('running tests')
    if opts.pattern:
        try:
            pat=re.compile(opts.pattern)
        except re.error:
            parser.error("error: invalid regular expression: %s" % opts.pattern)
    else:
        pat=_defaultNamePat
    res=runNamespace(tags, namePat=pat)
    sys.exit(res)
    
    
    
