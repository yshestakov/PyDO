"""

tests for the pydo.multifetch module.


"""
import pydo as P
import config
alltags=config.ALLDRIVERS+['fetch']
from test_base import base_fixture

class test_fetch1(base_fixture):
    alltables=['A', 'B', 'C', 'A_C']
    tags=alltags
    
    def pre(self):
        A=self.A
        B=self.B
        b1=B.new(x=400)
        A.new(name="George Wagner",
              b_id=b1.id,
              ta='ho ho',
              tb='Zola\'s Gorgon',
              w=4,
              x=4,
              y=45,
              z=46)
        A.new(name='Bob Casillo',
              b_id=b1.id,
              ta='ponzee',
              x=100,
              y=101,
              z=102)
        A.new(name='Big Bill',
              x=200,
              y=201,
              z=202)
        A.new(name='Pavarotti',
              x=300,
              y=301,
              z=302)
        
    def run(self):
        objs=[(self.A,'asparagus'), (self.B, 'bunko')]
        sql="""SELECT $COLUMNS FROM $TABLES
        WHERE asparagus.x<=200 AND asparagus.b_id=bunko.id"""
        res=P.fetch(objs, sql)
        assert len(res)==2
        for r in res:
            a, b=r
            assert isinstance(a, self.A)
            assert isinstance(b, self.B)


class test_fetch2(base_fixture):
    tags=alltags
    alltables=['C']

    def pre(self):
        for n in (0, 20, 40, 60, 77, 77, 77, 77):
            self.C.new(x=n)

    def run(self):
        objs=[self.C.project('x'), 'count(id)as rubberducky']
        sql="""
        SELECT $COLUMNS FROM $TABLES
        GROUP BY x HAVING x=77
        """
        res=P.fetch(objs, sql)
        assert len(res)==1
        cobj, cnt=res[0]
        assert cobj.x==77
        assert int(cnt)==4
        
