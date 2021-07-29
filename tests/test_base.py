"""
tests for the pydo.base module.

"""
from testingtesting import tag
import config
from fixture import Fixture, base_fixture, get_sequence_sql
import pydo as P

import random
import string
import sys
import itertools

def ranwords(num, length=9):
    s=set()
    while len(s)<length:
        s.add(''.join(random.sample(string.ascii_lowercase, length)))
    return s


alltags=config.ALLDRIVERS + ['base']


@tag(*alltags)
def test_inheritance1():
    class nougat(P.PyDO):
        schema='public'
        fields=(P.Sequence('id'),
                P.Unique('title'),
                'foo',
                'bar')
    class ripple(nougat):
        fields=('foople',
                'pinko')
    cols=set(('id',
              'title',
              'foo',
              'bar',
              'foople',
              'pinko'))
    assert set(ripple.getColumns())==cols
    uniq=frozenset(map(frozenset, (('id',), ('title',))))
    assert ripple.getUniquenessConstraints()==uniq
    assert ripple.getSequences()==dict(id=True)


@tag(*alltags)
def test_inheritance2():
    FIELDS1=('nincompoop', P.Unique('id'))
    FIELDS2=('imbecile', 'id')
    
    class foo(object):
        fields=FIELDS1

    class goo(object):
        fields=FIELDS2

    class phoo1(foo, goo):
        pass

    class phoo2(goo, foo):
        pass

    assert phoo1.fields==FIELDS1
    assert phoo2.fields==FIELDS2

    class foo(P.PyDO):
        fields=FIELDS1

    class goo(P.PyDO):
        fields=FIELDS2

    class phoo1(foo, goo):
        pass

    class phoo2(goo, foo):
        pass

    assert phoo1.fields==FIELDS1
    assert phoo1.getUniquenessConstraints(), "phoo1 should have a unique key"
    assert phoo2.fields==FIELDS2
    assert not phoo2.getUniquenessConstraints(), "phoo2 shouldn't have a unique key"

    

@tag(*alltags)
def test_unique1():
    class baba(P.PyDO):
        fields=('x', 'y', 'z')
        unique=(('x', 'y'),)

    uniq=list(baba.getUniquenessConstraints())
    assert len(uniq)==1
    assert uniq[0]==frozenset(('x', 'y'))

class test_unique2(base_fixture):
    usetables=['D']
    tags=alltags

    def pre(self):
        for i in range(20):
            self.D.new(id=i, x=100)
        

    def run(self):
        assert self.D.getUnique(id=15).x==100
        assert self.D.getUnique(id=800)==None

class test_unique3(base_fixture):
    usetables=['A']
    tags=alltags

    def run(self):
        tmp=sorted(self.A._matchUnique(dict(id=3,
                                            name='foo',
                                            w=40,
                                            y=40)))
        assert tmp==['id', 'name']
        tmp=sorted(self.A._matchUnique(dict(name='nougat',
                                            w=40,
                                            x=40,
                                            y=40)))
        assert tmp==['name']
        tmp=sorted(self.A._matchUnique(dict(name='nougat',
                                            x=40,
                                            y=40,
                                            z=40)))
        assert tmp==['name', 'y', 'z']

class test_unique4(base_fixture):
    usetables=['A']
    tags=alltags

    def pre(self):
        tmp=self.A.new(name='hooey',
                       x=1,
                       y=1,
                       z=1)
        self.tmpid=tmp.id

    def run(self):
        res=self.A.getUnique(id=self.tmpid, name='froggie')
        assert res is None

        
@tag(*alltags)        
def test_project1():
    class torte(P.PyDO):
        fields=(P.Sequence('id'),
                P.Unique('title'),
                'x',
                'y',
                'z')
    foo=torte.project('id', 'title', 'x')
    assert foo.getSequences()==dict(id=True)
    assert len(foo.getColumns())==3
    assert len(foo.getUniquenessConstraints())==2

@tag(*alltags)
def test_project2():
    class torte2(P.PyDO):
        fields=(P.Sequence('id'),
                P.Unique('title'),
                'x',
                'y',
                'z')
    assert not torte2._projections
    foo=torte2.project(P.Field('id'), 'title', 'x')
    assert not foo.getSequences(), "expected no sequences, got: %s" % str(foo.getSequences())
    assert len(foo.getUniquenessConstraints())==1

@tag(*alltags)
def test_project3():
    class A(P.PyDO):
        fields=(P.Sequence('id'), 'x')
    p=A.project(P.Field('id'))
    assert not p.getSequences()
    assert not p.getUniquenessConstraints()

@tag(*alltags)
def test_project4():
    class torte4(P.PyDO):
        fields=(P.Sequence('id'),
                'title',
                'x',
                'y',
                'z')
    foo=torte4.project(P.Field('id'), 'title', 'x', 'y')
    assert not foo.getSequences(), "expected no sequences, got: %s" % str(foo.getSequences())
    assert len(foo.getUniquenessConstraints())==0

class test_project5(base_fixture):
    usetables=['D']
    tags=alltags

    def pre(self):
        self.D.new(id=1, x=1)

    def run(self):
        r1=self.D.getUnique(id=1)
        r1.refresh()
        r2=self.D.project('x').getSome()[0]
        try:
            r2.refresh()
        except ValueError:
            pass
        else:
            assert 0, "projection without unique constraint shouldn't be refreshable!"

class test_project6(base_fixture):
    usetables=['D']
    tags=alltags

    def pre(self):
        for i in range(1, 41, 2):
            self.D.new(id=i, x=i)
            self.D.new(id=i+1, x=i+1)

    def run(self):
        o=self.D.getUnique(id=4)
        assert o.x==4
        p=self.D.project('id', 'x')
        x=p.getUnique(id=4)
        assert x.x==4
        p1=p.project('id', 'x')
        y=p1.getUnique(id=4)
        assert y.x==4

class test_project7(base_fixture):
    usetables=['A_C']
    tags=alltags

    def pre(self):
        for i in range(1, 10):
            self.A_C.new(a_id=i,
                         c_id=i+1)

    def run(self):
        o1=self.A_C.getUnique(a_id=1, c_id=2)
        assert o1
        o2=self.A_C.project('a_id', 'c_id').getUnique(a_id=1, c_id=2)
        assert o2

class test_project8(base_fixture):
    usetables=['E']
    tags=alltags

    def pre(self):
        self.E.new(user1='me', user2='you')

    def run(self):
        o1=self.E.getUnique(id=1)
        assert o1.user1=='me'
        assert o1.user2=='you'
        p1=self.E.project('id', 'user1')
        o2=p1.getUnique(id=1)
        assert o2.user1=='me'

        class tmp(P.PyDO):
            connectionAlias='pydotest'
            table='e'
            fields=(P.Sequence('id'),
                    'user1')

        o3=tmp.getUnique(id=1)
        assert o3.user1=='me'
        p2=tmp.project('id', 'user1', 'user2')
        o4=p2.getUnique(id=1)
        assert o4.user1=='me'
        assert o4.user2=='you'
#       # Faber's aggregate trick, which I'm not sure should be supported.
#       p3=tmp.project('id', 'user1', 'user2', 'count(*) as count')
#       res=p3.getSome()
#       assert len(res)==1
#       assert res[0]['count'] == 1

class test_project9(base_fixture):
    usetables=['E']
    tags=alltags

    def pre(self):
        self.E.new(user1='me', user2='you')

    def run(self):
        p1=self.E.project('user1', mutable=False)
        assert p1.mutable==False
        p2=self.E.project('user1', mutable=True)
        assert p2.mutable==True
        res=p1.getSome()
        assert len(res)==1


class test_project10(base_fixture):
    usetables=['E']
    tags=alltags

    def run(self):
        p1=self.E.project('user1', dict(name='user2', asname='poop'))
        cols=p1.getColumns()
        assert len(cols)==2
        assert 'user1' in cols
        assert 'poop' in cols

@tag(*alltags)
def test_guess_tablename1():
    class base(P.PyDO):
        guess_tablename=True

    class A(base):
        pass

    class B(A):
        pass

    class C(base):
        table="donut"

    class D(C):
        pass

    assert base.table=='base'
    assert A.table=='a'
    assert B.table=='b'
    assert C.table=='donut'
    assert D.table=='donut'
        
    
@tag('sqlite', 'mysql', 'psycopg', 'base')        
def test_guess_columns1():
    create="""CREATE TABLE test_guess_columns1 (
    id %s,
    x INTEGER NOT NULL UNIQUE,
    y INTEGER NOT NULL,
    z INTEGER UNIQUE,
    r1 INTEGER NOT NULL,
    r2 INTEGER NOT NULL,
    UNIQUE (r1, r2)
    )""" % get_sequence_sql()
    
    db=P.getConnection('pydotest')
    c=db.cursor()
    c.execute(create)
    try:
        class testclass(P.PyDO):
            guess_columns=True
            table='test_guess_columns1'
            connectionAlias='pydotest'

        cols=testclass.getColumns()

        uniq=testclass.getUniquenessConstraints()
        seq=testclass.getSequences()
        assert set(cols)==set(('id', 'x', 'y', 'z', 'r1', 'r2'))
        assert seq.keys()==['id']
        assert uniq==frozenset((frozenset(('r1', 'r2')),
                                frozenset(('x',)),
                                frozenset(('id',))))

    finally:
        if db.autocommit or config.DRIVER == "sqlite2":
            c.execute('drop table test_guess_columns1')
        else:
            db.rollback()
        c.close()                               

@tag(*alltags)
def test_unique5():
    class porkbarrel(P.PyDO):
        fields=(P.Sequence('a'),
                'b',
                'c')
        unique=(('b', 'c'),)
    u=porkbarrel.getUniquenessConstraints()
    assert len(u)==2
    assert frozenset(('b', 'c')) in u
    assert frozenset(('a',)) in u

@tag(*alltags)
def test_schema1():
    class A(P.PyDO):
        table='froggie'
        schema='pants'
    assert A.getTable(False)=='froggie'
    assert A.getTable(True)=='pants.froggie'
    assert A.getTable()=='pants.froggie'
    assert A.table=='froggie'
    assert A.schema=='pants'

@tag(*alltags)
def test_picklebase1():
    global zingo
    class zingo(P.PyDO):
        fields=(P.Sequence('id'),
                'nohat',
                'nofrog',
                'pig')
    import cPickle
    dump=cPickle.dumps(zingo, 2)
    orig=cPickle.loads(dump)
    assert orig==zingo
    del zingo
        
class test_new1(Fixture):
    tags=alltags[:]
    class obj(P.PyDO):
        table='test_new1'
        connectionAlias='pydotest'
        fields=(P.Unique('id'), 'x')

    def setup(self):
        create=""" CREATE TABLE test_new1 (id INTEGER PRIMARY KEY NOT NULL,
        x INTEGER)"""
        c=self.db.cursor()
        c.execute(create)
        c.close()

    def cleanup(self):
        if self.db.autocommit or config.DRIVER == "sqlite2":
            c=self.db.cursor()
            c.execute('DROP TABLE test_new1')
            c.close()
        else:
            self.db.rollback()

    def run(self):
        for i in range(100):
            self.obj.new(id=i, x=100)
        res=[x.id for x in self.obj.project('id').getSome(order='id')]
        assert res==range(100)


class test_new2(base_fixture):
    usetables=('A',)
    tags=alltags

    def run(self):
        res=self.A.newfetch(name='porkhat',
                            x=4,
                            y=5,
                            z=20)
        assert res.d==33
        res=self.A.newnofetch(name='pinger',
                              x=50,
                              y=100,
                              z=0)
        assert res.d==None
        


class test_update1(base_fixture):
    tags=alltags
    usetables=['A']

    def pre(self):
        for i, w in enumerate(ranwords(100)):
            if i % 2:
                ta=None
            else:
                ta=w.upper()
            self.A.new(name=w,
                       ta=ta,
                       x=i,
                       y=i+100,
                       z=40)

    def run(self):
        all=self.A.getSome()
        for a in all:
            a.tb='choo choo'

class test_update2(base_fixture):
    usetables=['A']
    # this will fail with mysql, because we can't count
    # on the rowcount property meaning that the update has
    # failed when zero rows are affected -- the update
    # could be vacuous.
    tags=[x for x in alltags if x!='mysql']

    def pre(self):
        self.A.new(name='froggie',
                   x=1,
                   y=1,
                   z=1)

    def run(self):
        instance1=self.A.getUnique(name='froggie')
        instance2=self.A.getUnique(name='froggie')
        instance1.name='jones'
        try:
            instance2.x=45
        except P.PyDOError:
            pass
        else:
            assert 0, "should have failed to update out-of-date instance"

class test_update3(base_fixture):
    usetables=['A']
    tags=alltags

    def pre(self):
        self.A.new(name='dingbat',
                   x=3,
                   y=2,
                   z=33)

    def run(self):
        obj=self.A.getUnique(name='dingbat')
        # in PyDO 2.0b2, this raises an exception
        # with mysql, because no row has actually
        # changed.  Fixed in 2.0rc1.
        obj.update(obj)

class test_deleteSome1(base_fixture):
    usetables=('B',)
    tags=alltags

    def pre(self):
        for x in xrange(200):
            self.B.new(x=random.randint(0, 1000))

    def run(self):

        self.B.deleteSome(P.LT(P.FIELD('x'), 500))
        sql='SELECT COUNT(*) FROM b WHERE x < 500'
        c=self.db.cursor()
        c.execute(sql)
        cnt=c.fetchone()[0]
        assert cnt==0


class test_updateSome1(base_fixture):
    usetables=('B',)
    tags=alltags
    
    def pre(self):
        for x in xrange(200):
            self.B.new(x=random.randint(0, 1000))
        c=self.db.cursor()
        sql='SELECT COUNT(*) FROM b WHERE x < 500'
        c.execute(sql)
        self.count=c.fetchone()[0]
        c.close()

    def run(self):

        self.B.updateSome(dict(x=None), P.LT(P.FIELD('x'), 500))
        sql='SELECT COUNT(*) FROM b WHERE x IS NULL'
        c=self.db.cursor()
        c.execute(sql)
        nullcnt=c.fetchone()[0]
        assert nullcnt==self.count


class test_updateSome2(base_fixture):
    usetables=('B',)
    tags=alltags
    
    def pre(self):
        for x in xrange(200):
            self.B.new(x=random.randint(0, 1000))
        c=self.db.cursor()
        sql='SELECT COUNT(*) FROM b WHERE x < 500'
        c.execute(sql)
        self.count=c.fetchone()[0]
        c.close()

    def run(self):

        self.B.updateSome(dict(x=2000), P.LT(P.FIELD('x'), 500))
        sql='SELECT COUNT(*) FROM b WHERE x = 2000'
        c=self.db.cursor()
        c.execute(sql)
        newcnt=c.fetchone()[0]
        assert newcnt==self.count


class test_updateSome3(base_fixture):
    usetables=('B',)
    tags=alltags
    
    def pre(self):
        for x in xrange(200):
            self.B.new(x=random.randint(0, 1000))
        c=self.db.cursor()
        sql='SELECT COUNT(*) FROM b WHERE x < 500'
        c.execute(sql)
        self.count=c.fetchone()[0]
        c.close()

    def run(self):
        if config.DRIVER == 'sqlite2':
          self.B.updateSome(dict(x=2000), "x < ?", 500)
        else:
          self.B.updateSome(dict(x=2000), "x < %s", 500)
        sql='SELECT COUNT(*) FROM b WHERE x = 2000'
        c=self.db.cursor()
        c.execute(sql)
        newcnt=c.fetchone()[0]
        assert newcnt==self.count                


class test_delete1(base_fixture):
    usetables=('C',)
    tags=alltags

    def pre(self):
        self.objs=[self.C.new(x=i) for i in range(100)]

    def run(self):
        for o in self.objs:
            i=o.id
            o.delete()
            assert not o.mutable
            o1=self.C.getUnique(id=i)
            assert o1 is None

class test_delete2(base_fixture):
    usetables=('C',)
    tags=alltags

    def pre(self):
        self.C.new(id=100, x=1)

    def run(self):
        proj=self.C.project('x')
        o=proj.getSome(order='id DESC', limit=1)[0]
        try:
            o.delete()
        except ValueError:
            pass
        else:
            assert 0, \
                   ('expected ValueError to be raised '
                    'when deleting an object without a '
                    'unique constraint')
            

class test_joinTable1(base_fixture):
    usetables=('A', 'C', 'A_C')
    tags=alltags

    def pre(self):
        insert=["""INSERT INTO a (id, b_id, name, x, y, z) VALUES (1, NULL, 'poco a poco', 3, 5, 2)""",
                """INSERT INTO a (id, b_id, name, x, y, z) VALUES (2, 1, 'mammoth', 30, 20, 1000)""",
                """INSERT INTO c (id, x) VALUES (1, 100)""",
                """INSERT INTO a_c (a_id, c_id) VALUES (2, 1)"""]
        c=self.db.cursor()
        for i in insert:
            c.execute(i)

    def run(self):
        o1=self.A.getUnique(id=1)
        assert o1 is not None
        j=o1.joinTable('id', 'a_c', 'a_id', 'c_id', self.C, 'id')
        assert len(j)==0
        o2=self.A.getUnique(id=2)
        assert o2 is not None
        j=o2.joinTable('id', 'a_c', 'a_id', 'c_id', self.C, 'id')
        assert len(j)==1
        assert j[0].id==1
        
class test_getSome1(base_fixture):
    usetables=('A',)
    tags=alltags

    def pre(self):
        self.A.new(name='MAX FACTOR',
                   b_id=5,
                   d=55,
                   x=0,
                   y=1,
                   z=2)

        self.A.new(name='HORTENSE MAXIMUS',
                   b_id=60,
                   d=0,
                   x=40,
                   y=50,
                   z=60)

        self.A.new(name='TENSION EXTREMUS',
                   b_id=-100,
                   x=40,
                   y=-80,
                   z=6000)

    def run(self):
        r=self.A.getSome()
        assert len(r)==3
        r=self.A.getSome('id <2')
        assert len(r)==1
        assert r[0].d==55
        r=self.A.getSome(P.EQ(P.FIELD('d'), 55))
        assert len(r)==1
        assert r[0].x==0
        r=self.A.getSome(P.OR(P.LT(P.FIELD('y'), 0),
                              P.LIKE(P.FIELD('name'), '%MAX%')))
        assert len(r)==3
        r=self.A.getSome(P.LIKE(P.FIELD('name'), '%TENS%'), order='z DESC')
        assert len(r)==2
        assert r[0].z==6000
        assert r[1].z==60

class test_getSome2(base_fixture):
    usetables=('B',)
    tags=alltags

    def pre(self):
        for i in range(5):
            self.B.new(x=None)
        for i in range(5):
            self.B.new(x=1)

    def run(self):
        some=self.B.getSome(x=None)
        assert len(some)==5
        
        

class test_refresh1(base_fixture):
    usetables=('A',)
    tags=alltags

    def pre(self):
        self.obj=self.A.new(name='bingo junction',
                            b_id=4,
                            ta=300,
                            x=0,
                            y=30,
                            z=-1)

    def run(self):
        assert self.obj.d is None
        self.obj.refresh()
        assert self.obj.d==33

class test_refresh2(base_fixture):
    usetables=('A', 'B')
    tags=alltags

    def pre(self):
        self.B.new(x=4)

    def run(self):
        obj=self.B.getUnique(id=1)
        obj.refresh()
        assert obj.id==1
        assert obj.x==4
        n=self.A.new(name='ho hum',
                     b_id=obj.id,
                     ta=0,
                     x=0,
                     y=0,
                     z=0)

        assert n.id==1
    
class test_refresh3(base_fixture):
    usetables=('C',)
    tags=alltags

    def pre(self):
        class wrong(P.PyDO):
            table='c'
            connectionAlias='pydotest'
            # this is wrong in two ways;
            # id is a sequence, and
            # x isn't unique.

            fields=(P.Unique('id'),
                    P.Unique('x'))
        self.wrong=wrong

    def run(self):
        n=self.wrong.new(x=5)
        assert n.id is None
        assert n.x==5
        try:
            n.refresh()
        except ValueError:
            pass
        else:
            assert 0, "refresh should fail"


            
class test_group1(base_fixture):
    usetables=('C',)
    tags=alltags

    def pre(self):
        for i in range(4):
            for c in range(3):
                self.C.new(x=i)

    def run(self):
        sql=['x=3 GROUP BY x',
             'GROUP BY x HAVING x=3']
        p=self.C.project('x')
        for s in sql:
            res=p.getSome(s)
            assert len(res)==1

        
class test_foreignkey1(base_fixture):
    usetables=('A', 'B')
    tags=alltags

    def pre(self):
        self.A.B=P.ForeignKey('b_id', 'id', self.B)
        b1=self.B.new(x=44)
        b2=self.B.new(x=88)
        self.A.new(name='aardvark',
                   b_id=b1.id,
                   x=1,
                   y=2,
                   z=3)

    def run(self):
        a=self.A.getUnique(name='aardvark')
        b=a.B
        assert isinstance(b, self.B)
        assert b.x==44
        b2=self.B.getSome(x=88)[0]
        assert b2
        a.B=b2
        assert a.b_id==b2.id

class test_foreignkey2(base_fixture):
    usetables=('A_C', 'F')
    tags=alltags

    def pre(self):
        self.F.A_C=P.ForeignKey(('a_id', 'c_id'), ('a_id', 'c_id'), self.A_C)
        self.A_C.new(a_id=1, c_id=1)
        self.f=self.F.new(a_id=1, c_id=1)

    def run(self):
        assert self.f.A_C.a_id==1
        assert self.f.A_C.c_id==1
        self.f.A_C=None


class test_foreignkey3(base_fixture):
    usetables=('A_C', 'F')
    tags=alltags

    def pre(self):
        global A_C
        A_C=self.A_C
        self.F.A_C=P.ForeignKey(('a_id', 'c_id'), ('a_id', 'c_id'), 'test_base.A_C')
        self.A_C.new(a_id=1, c_id=1)
        self.f=self.F.new(a_id=1, c_id=1)

    def run(self):
        assert self.f.A_C.a_id==1
        assert self.f.A_C.c_id==1
        self.f.A_C=None        
        
        
class test_one_to_many1(base_fixture):
    usetables=('A', 'B')
    tags=alltags

    def pre(self):
        self.B.getA=P.OneToMany('id', 'b_id', self.A)
        n=itertools.count().next
        self.b1=b1=self.B.new(x=n())
        self.b2=b2=self.B.new(x=n())
        self.A.new(name='aardvark',
                   b_id=b1.id,
                   x=n(),
                   y=n(),
                   z=n())
        self.A.new(name='gonzo',
                   b_id=b1.id,
                   x=n(),
                   y=n(),
                   z=n())
        self.A.new(name='hoboken',
                   b_id=b1.id,
                   x=n(),
                   y=n(),
                   z=n())

    def run(self):
        some=self.b1.getA()
        assert len(some)==3
        nuttin=self.b2.getA()
        assert len(nuttin)==0
    

class test_one_to_many2(base_fixture):
    usetables=('A_C', 'F')
    tags=alltags

    def pre(self):
        self.A_C.getF=P.OneToMany(('a_id', 'c_id'), ('a_id', 'c_id'), self.F)
        self.ac1=self.A_C.new(a_id=1, c_id=1)
        self.ac2=self.A_C.new(a_id=2, c_id=2)
        for i in range(4):
            self.F.new(a_id=1, c_id=1)
        for i in range(3):
            self.F.new(a_id=2, c_id=2)

    def run(self):
        tmp=self.ac1.getF()
        assert len(tmp)==4
        tmp=self.ac2.getF()
        assert len(tmp)==3

class test_one_to_many3(base_fixture):
    usetables=('A_C', 'F')
    tags=alltags

    def pre(self):
        self.A_C.getF=P.OneToMany(('a_id', 'c_id'), ('a_id', 'c_id'), self.F)
        self.ac1=self.A_C.new(a_id=1, c_id=1)
        self.ac2=self.A_C.new(a_id=2, c_id=2)
        for i in range(4):
            self.F.new(a_id=1, c_id=1)
        for i in range(3):
            self.F.new(a_id=2, c_id=2)

    def run(self):
        tmp=self.ac1.getF(P.NE(P.FIELD('a_id'), 2))
        assert len(tmp)==4
        if config.DRIVER == "sqlite2":
          tmp=self.ac1.getF("a_id > ?", 100)
        else:
          tmp=self.ac1.getF("a_id > %s", 100)
        assert len(tmp)==0
        tmp=self.ac1.getF(a_id=4000)
        assert len(tmp)==0


class test_many_to_many1(base_fixture):
    """
    this is the same as test_joinTable1, but rewritten to use ManyToMany.
    """
    usetables=('A', 'C', 'A_C')
    tags=alltags

    def pre(self):
        self.A.getC=P.ManyToMany('id', 'a_c', 'a_id', 'c_id', self.C,  'id')
        insert=["""INSERT INTO a (id, b_id, name, x, y, z) VALUES (1, NULL, 'poco a poco', 3, 5, 2)""",
                """INSERT INTO a (id, b_id, name, x, y, z) VALUES (2, 1, 'mammoth', 30, 20, 1000)""",
                """INSERT INTO c (id, x) VALUES (1, 100)""",
                """INSERT INTO a_c (a_id, c_id) VALUES (2, 1)"""]
        c=self.db.cursor()
        for i in insert:
            c.execute(i)

    def run(self):
        o1=self.A.getUnique(id=1)
        assert o1 is not None
        j=o1.getC()
        assert len(j)==0
        o2=self.A.getUnique(id=2)
        assert o2 is not None
        j=o2.getC()
        assert len(j)==1
        assert j[0].id==1    



class test_getCount1(base_fixture):
    usetables=['D']
    tags=alltags

    def pre(self):
        for x in range(20):
            self.D.new(id=x, x=x)
        
    def run(self):
        c=self.D.getCount(id=4)
        assert c == 1
        c=self.D.getCount()
        assert c == 20
        if config.DRIVER == "sqlite2":
          c=self.D.getCount("x < ?", 3)
        else:
          c=self.D.getCount("x < %s", 3)
        assert c == 3
        c=self.D.getCount(P.OR(P.EQ(P.FIELD('id'), 5), P.GT(P.FIELD('x'), 10)))
        assert c == 10

        
class test_as1(base_fixture):
    usetables=['E']
    tags=alltags

    def pre(self):
        self.E.new(user1='me', user2='you')
        self.E.new(user1='me', user2='gonga')
        self.E.new(user1='bongo', user2='you')

    def run(self):
        o1=self.E.getUnique(id=1)
        assert o1.user1=='me'
        assert o1.user2=='you'
        p=self.E.project('user1', P.Field('count(*)', asname='count'))
        if config.DRIVER=='sqlite2':
            res=p.getSome('user1=? group by user1', 'me')
        else:
            res=p.getSome('user1=%s group by user1', 'me')
        #print res
        assert len(res)==1
        assert res[0].count==2
        if config.DRIVER=='sqlite2':
            res=p.getSome('user1 = ? group by user1', 'bongo')
        else:
            res=p.getSome('user1 = %s group by user1', 'bongo')
        assert len(res)==1
        assert res[0].count==1
        

        
class test_as2(base_fixture):
    usetables=['E']
    tags=alltags

    def run(self):
        p=self.E.project('user1', P.Field(name='user3', asname='plapitude'))
        #p=self.E.project('user1', 'user3 as plapitude')
        cols=p.getColumns()
        assert 'plapitude' in cols
        assert 'user1' in cols
        assert len(cols)==2
        p2=self.E.project('user1', 'user3 as plapitude')
        cols=p2.getColumns()
        assert 'plapitude' in cols
        assert 'user1' in cols
        assert len(cols)==2
