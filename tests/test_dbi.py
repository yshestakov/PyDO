"""
Tests for the pydo.dbi module.

"""
import threading
import time
from pydo.utils import every

from testingtesting import tag
import config
from fixture import base_fixture
dbitags=config.ALLDRIVERS+['dbi']
import pydo.dbi as D
import pydo as P

@tag(*dbitags)
def test_initAlias1():
    """ calls initAlias with bogus arguments.  Should succeed."""    
    alias='pomposity'
    D.initAlias(alias, 'anything', 'anything', True, True)
    try:
        assert D._aliases.has_key(alias)
    finally:
        D.delAlias(alias)
        assert not D._aliases.has_key(alias)

@tag(*dbitags)    
def test_initAlias2():
    """ calls initAlias twice with the same arguments.  Should succeed. """
    alias='fruitcake'
    driver='pong'
    connectArgs='blimp'
    
    D.initAlias(alias, driver, connectArgs)
    try:
        try:
            D.initAlias(alias, driver, connectArgs)
        except ValueError:
            raise ValueError, \
                  "ValueError should not be raised when an alias is reinitialized"\
                  " with identical data!"
        
    finally:
        D.delAlias(alias)

@tag(*dbitags)
def test_initAlias3():
    """ calls initAlias twice with different arguments.  Should fail. """
    alias='fruitcake'
    driver='pong'
    connectArgs='blimp'
    D.initAlias(alias, driver, connectArgs)
    connectArgs='potato'
    try:
        try:
            D.initAlias(alias, driver, connectArgs)
        except ValueError:
            error_raised=True
        else:
            error_raised=False
        assert error_raised, \
               "ValueError should be raised when a change is made to alias config"
    finally:
        D.delAlias(alias)

@tag(*dbitags)
def test_delAlias1():
    """ calls delAlias for an alias that does not exist. Should succeed."""
    D.delAlias('jackandjill')

@tag(*dbitags)
def test_threads1():
    """
    tests that each thread gets its own dbapi connection.
    """
    db=D.getConnection('pydotest')
    id1=id(db.conn)

    class mythread(threading.Thread):
        def run(self):
            mydb=D.getConnection('pydotest')
            self.connid=id(mydb.conn)
    t=mythread()
    t.start()
    t.join()
    assert t.connid!=id1
    assert id(db.conn)==id1

@tag(*dbitags)
def test_swapConnection1():
    db=D.getConnection('pydotest')
    conn1=db._connect()
    conn2=db.conn
    assert not (conn1 is conn2)
    conn3=db.swapConnection(conn1)
    assert conn3 is conn2
    assert conn1 is db.conn


@tag(*dbitags)    
def test_pool1():
    stuff=D._aliases['pydotest'].copy()
    D.initAlias('pydotestpool',
                stuff['driver'],
                stuff['connectArgs'],
                D.ConnectionPool(max_poolsize=4, keep_poolsize=4),
                stuff['verbose'])
    db=D.getConnection('pydotestpool')
    try:
        assert len(db.pool._busy)==0
        assert len(db.pool._free)==0
        conn=db.conn
        assert len(db.pool._busy)==1
        assert len(db.pool._free)==0
        c=conn.cursor()
        c.execute('SELECT 1+1')
        res=c.fetchone()
        assert res[0]==2
        c.close()
        conn.close()
        assert len(db.pool._busy)==0
        assert len(db.pool._free)==1
    finally:
        D.delAlias('pydotestpool')

@tag(*dbitags)
def test_pool2():
    stuff=D._aliases['pydotest'].copy()
    D.initAlias('pydotestpool',
                stuff['driver'],
                stuff['connectArgs'],
                # keep_poolsize actually doesn't matter here
                D.ConnectionPool(max_poolsize=0, keep_poolsize=4),
                stuff['verbose'])
    hold=True
    threads=[]    
    class mythread(threading.Thread):
        def run(self):
            mydb=D.getConnection('pydotestpool')
            self.connid=id(mydb.conn)
            while hold:
                time.sleep(0.1)

    for i in range(10):
        t=mythread()
        threads.append(t)
        t.start()
    # we don't want any threads to terminate until
    # all threads have been initialized; otherwise,
    # some connections might get reused.
    ready=lambda t: hasattr(t, 'connid')
    while 1:
        if every(True, (ready(t) for t in threads)):
            break
        time.sleep(0.1)

    # let the threads die
    hold=False
    for t in threads:
        t.join()
    connids=[t.connid for t in threads]
    # assertion means: no connection has been handed out
    # to a plural number of simultaneously active threads
    assert len(connids)== len(set(connids))


@tag(*dbitags)
def test_autocommit1():
    db=D.getConnection('pydotest')
    if config.DRIVER=='mysql':
        assert db.autocommit
    else:
        assert not db.autocommit
    

class test_autocommit2(base_fixture):
    usetables=['C']
    # don't test mysql for now
    tags=[x for x in dbitags if x!='mysql']

    def setup(self):
        base_fixture.setup(self)
        self.db.commit()

    def post(self):
        self.db.autocommit=False
        c=self.db.cursor()
        try:
            c.execute('drop table c')
        except:
            pass
        else:
            self.db.commit()

    def run(self):
        assert not self.db.autocommit
        def subtest(ac):
            self.C.new(x=4000)
            i=self.C.getSome(x=4000)
            assert len(i)==1
            del i
            if not ac:
                self.db.rollback()
            if not ac:
                assert len(self.C.getSome(x=4000))==0
            else:
                assert len(self.C.getSome(x=4000))==1
                
        subtest(False)
        self.db.autocommit=True
        try:
            subtest(True)
        finally:
            self.db.autocommit=False
    
class test_describeTable1(base_fixture):
    tags=('dbi', 'psycopg',)

    def setup(self):
        sql=["CREATE SCHEMA testytesty",
             "CREATE TABLE testytesty.foo (id SERIAL PRIMARY KEY, name TEXT NOT NULL)"]
        c=self.db.cursor()
        for s in sql:
            c.execute(s)
        c.close()

    def run(self):
        class foo(P.PyDO):
            connectionAlias='pydotest'
            schema='testytesty'
            guess_columns=True
        s=sorted(foo.getColumns())
        assert s==['id', 'name']
             
        
    
