"""

tests for the pydo.operators module.

(There are doctests in the module itself, so this is a bit spare at
the moment.)


"""
from testingtesting import tag
import config
from fixture import base_fixture
from cPickle import loads, dumps

alltags=config.ALLDRIVERS + ['operators']

from pydo.operators import *
import pydo as P

@tag(*alltags)
def test_AND1():
    assert str(AND(FIELD('x')))=='x'

@tag(*alltags)               
def test_converter1():
    op=AND(FIELD('x'), EQ(FIELD('y'), 'fiddler\'s roof'))
    assert str(op)=="(x AND (y = 'fiddler''s roof'))"
    c=BindingConverter('qmark')
    op.setConverter(c)
    s=str(op)
    assert s=="(x AND (y = ?))"
    assert c.values==["fiddler's roof"]



class test_converter2(base_fixture):
    usetables=['E']
    tags=alltags

    def pre(self):
        self.E.new(user1="doo'ood", user2='crinkle')
        self.E.new(user1="snoozer's zzzs", user2='hoho')

    def run(self):
        match=SQLOperator(('LIKE', FIELD('user1'), "doo'oo%"))
        res=self.E.getSome(match)
        assert len(res)==1
        match = AND(SQLOperator(('LIKE', FIELD('user1'), "snoozer's%")),
                    SQLOperator(('=', FIELD('user2'), "hoho")))
        res=self.E.getSome(match)
        assert len(res)==1


@tag(*alltags)
def test_pickleconstant1():
    f=FIELD('ho')
    f2=loads(dumps(f))
    assert str(f)==str(f2)
    
