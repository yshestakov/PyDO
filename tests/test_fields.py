"""

tests for the pydo.fields module.

"""
from testingtesting import tag
import config
alltags=config.ALLDRIVERS + ['fields']
from cPickle import dumps, loads
import pydo as P

@tag(*alltags)
def test_getattr1():
    class A(P.PyDO):
        fields=(P.Sequence('id'), 'x')

    # this should not throw an error, although it did up through 2.0b0
    getattr(A, 'x')
    
@tag(*alltags)
def test_picklefield1():
    f=P.Field('x')
    f2=loads(dumps(f))
    assert f.name==f2.name

