from itertools import izip
from threading import Lock, local
from collections import deque
import time
from pydo.log import *
from pydo.operators import BindingConverter
from pydo.exceptions import PyDOError
from pydo.utils import _strip_tablename, _import_a_class

exception_names=('DataError',
                 'DatabaseError',
                 'Error',
                 'IntegrityError',
                 'InterfaceError',
                 'InternalError',
                 'NotSupportedError',
                 'OperationalError',
                 'ProgrammingError')

class DBIBase(object):
    """base class for db connection wrappers.
    """
    paramstyle='format'
    # default to postgresql style for sequences,
    # out of sheer postgresql bigotry. 
    auto_increment=False
    # should we pay attention to rowcount by default?
    has_sane_rowcount=True
    
    def __init__(self,
                 connectArgs,
                 connectFunc,
                 dbapiModule,
                 pool=None,
                 verbose=False,
                 initFunc=None):
        """
        constructor.
        * connectArgs are arguments passed directly to the underlying
          DBAPI driver.
        * connectFunc is the connect function from the DBAPI module.
        * pool is a connection pool instance.
        * verbose is whether or not to log the sql being executed.
        """
        self.connectArgs=connectArgs
        self.connectFunc=connectFunc        
        self.pool=pool
        self.verbose=verbose
        self.initFunc=initFunc
        self._local=local()
        self.dbapiModule=dbapiModule
        self._initExceptions()

    
    def _initExceptions(self):
        self.exceptions=dict((e, getattr(self.dbapiModule, e)) for e in exception_names)

    def conn():
        def fget(self):
            try:
                return self._local.connection
            except AttributeError:
                # vivify connection
                c=self._connect()
                self._local.connection=c
                return c

        def fset(self, c):
            self._local.connection=c

        def fdel(self):
            c=self._local.connection
            del self._local.connection
            c.close()
            
        return fget, fset, fdel, "the underlying db connection"
    conn=property(*conn())

    def swapConnection(self, connection):
        """switch the connection in use for the current thread with another one."""
        c=self._local.__dict__.get('connection')
        self._local.connection=connection
        return c

    def endConnection(self):
        """ disassociate from the current connection, which may be
        deleted or returned to a pool."""
        del self.conn
        
    def commit(self):
        """commits a transaction"""
        self.conn.commit()
        if self.pool:
            # release connection
            del self.conn

    def rollback(self):
        """rolls back a transaction"""
        self.conn.rollback()
        if self.pool:
            # release connection
            del self.conn

    def cursor(self):
        """returns a database cursor for direct access to the db connection"""
        return self.conn.cursor()

    def _connect(self):
        if self.pool:
            return self.pool.connect(self.connectFunc, self.connectArgs, self.initFunc)
        else:
            return _real_connect(self.connectFunc, self.connectArgs, self.initFunc)

    def getConverter(self):
        """returns a converter instance."""
        return BindingConverter(self.paramstyle)

    def execute(self, sql, values=(), qualified=False):
        """Executes the statement with the values and does conversion
        of the return result as necessary.
        result is list of dictionaries, or number of rows affected"""
        if self.verbose:
            debug("SQL: %s", sql)
            debug("bind variables: %s", values)

        c=self.conn.cursor()
        if values:
            c.execute(sql, values)
        else:
            # I don't want to assume that all drivers will like None,
            # or (), or {}, equally when there are no bind variables
            c.execute(sql)
        resultset=c.fetchall()
        if not resultset:
            return c.rowcount
        res=self._convertResultSet(c.description, resultset, qualified)
        c.close()
        #if self.autocommit and self.pool:
        #    # release connection
        #    del self.conn
        return res
    
    @staticmethod
    def _convertResultSet(description, resultset, qualified=False):
        """internal function that turns a result set into a list of dictionaries."""
        if qualified:
            fldnames=[x[0] for x in description]
        else:
            fldnames=[_strip_tablename(x[0]) for x in description]
        return [dict(izip(fldnames, row)) for row in resultset]

    @staticmethod
    def orderByString(order, limit, offset):
        def do_order(o):
            if isinstance(o, basestring):
                return o
            return ' '.join(o)
        if not order:
            order=""
        elif not isinstance(order, basestring):
            order= ', '.join(map(do_order, order))
        if order:
            order="ORDER BY %s" % order
        if limit not in ("", None):
            limit="LIMIT %s" % limit
        else:
            limit=""
        if offset not in ("", None):
            offset="OFFSET %s" % offset
        else:
            offset=""
        return " ".join(filter(None, (order, limit, offset)))


    def getSequence(self, name, field, table):
        """If db has sequences, this should return
        the next value of the sequence named 'name'"""
        pass

    def getAutoIncrement(self, name):
        """If db uses auto increment, should obtain
        the value of the auto-incremented field named 'name'"""
        pass

    def listTables(self, schema=None):
        """list the tables in the database schema"""
        raise NotImplementedError

    def describeTable(self, table, schema=None):
        """for the given table, returns a 2-tuple: a dict of Field objects
        keyed by name, and list of multi-column unique constraints (sets of Fields)).
        The Field instances should contain information about whether they are unique
        or sequenced.
        """
        raise NotImplementedError



_driverConfig = {
    'mysql':       'pydo.drivers.mysqlconn.MysqlDBI',
    'psycopg':	   'pydo.drivers.psycopgconn.PsycopgDBI',
    'sqlite':      'pydo.drivers.sqliteconn.SqliteDBI',
    'sqlite2':     'pydo.drivers.sqliteconn2.SqliteDBI',
    # since the sqlite driver in Python2.5 is called sqlite3 ...
    'sqlite3':     'pydo.drivers.sqliteconn2.SqliteDBI',
    'mssql' :      'pydo.drivers.mssqlconn.MssqlDBI',
    'oracle' :     'pydo.drivers.oracleconn.OracleDBI'
    
    # more to come!
    }
_loadedDrivers = {}
_aliases= {}
_connlock=Lock()

def _real_connect(connfunc, connargs, initFunc=None):
    if isinstance(connargs, dict):
        conn=connfunc(**connargs)
    elif isinstance(connargs, tuple):
        conn=connfunc(*connargs)
    else:
        conn=connfunc(connargs)
    if initFunc:
        initFunc(conn)
    return conn

def _connect(driver, connectArgs, pool=None, verbose=False, initFunc=None):
    if isinstance(driver, basestring):
        driver=_get_driver_class(driver)
    return driver(connectArgs, pool, verbose, initFunc)



def _get_driver_class(name):
    if not _loadedDrivers.has_key(name):
        fqcn = _driverConfig[name]
        cls=_import_a_class(fqcn)
        _loadedDrivers[name] = cls
        return cls
    return _loadedDrivers[name]
             
def initAlias(alias, driver, connectArgs, pool=None, verbose=False, init=None):
    """initializes a connection alias with the stated connection arguments.
    
    It can cause confusion to let this be called repeatedly; you might
    think you are initializing it one way and not realize it is being
    initialized elsewhere differently.  Therefore, this raises a
    ValueError if the alias is already initialized with different
    data.  Multiple initializations with the same data (such as
    happens when a module calling initAlias is reloaded) are permitted.

    If you need to change the connect values at runtime, call delAlias
    before initAlias.
    
    """
    if isinstance(init, basestring):
        sql=init
        def init(conn):
            c=conn.cursor()
            c.execute(sql)
            c.close()
    elif isinstance(init, (list, tuple)):
        for s in init:
            if not isinstance(s, basestring):
                raise ValueError, "expected string, got %s" % s
        sql=init
        def init(conn):
            c=conn.cursor()
            for s in sql:
                c.execute(s)
            c.close()
    elif init and not callable(init):
        raise ValueError, \
              "init must be either None, a string, or callable, got %s" % type(init)
        
    data=dict(driver=driver,
              connectArgs=connectArgs,
              pool=pool,
              verbose=verbose,
              initFunc=init)
    _connlock.acquire()
    try:
        old=_aliases.get(alias)
        if old:
            old=old.copy()
            # get rid of connection for the sake of comparison
            old.pop('connection', None)
            if data!=old:
                raise ValueError, "already initialized: %s" % alias
        else:
            _aliases[alias]=data
    finally:
        _connlock.release()


def delAlias(alias):
    """delete a connection alias if it has already been initialized;
    does nothing otherwise"""
    _connlock.acquire()
    try:
        if _aliases.has_key(alias):
            del _aliases[alias]
    finally:
        _connlock.release()

def getConnection(alias, create=True):
    """get a connection given a connection alias"""
    _connlock.acquire()
    try:
        try:
            conndata=_aliases[alias]
        except KeyError:
            raise ValueError, "alias %s not recognized" % alias
        if not conndata.has_key('connection'):
            if not create:
                return None
            res=_connect(**conndata)
            conndata['connection']=res
            return res
        return conndata['connection']
    finally:
        _connlock.release()

class ConnectionWrapper(object):
    """a connection object returned from a connection pool which wraps
    a real db connection.  It delegates to the real connection, but
    overrides close(), which instead of closing the connection,
    returns the it to the pool.  """
    
    __slots__=('_conn', '_pool', '_closed')
    
    def __init__(self, conn, pool):
        self._conn=conn
        self._pool=pool
        self._closed=0
        
    def __getattr__(self, attr):
        return getattr(self._conn, attr)

    def __setattr__(self, attr, val):
        if attr in self.__slots__:
            super(ConnectionWrapper, self).__setattr__(attr, val)
        else:
            setattr(self._conn, attr, val)

    def close(self):
        # tell the cache that we are done and can be reused
        self._pool.release(self._conn)
        self._closed=1

    def __del__(self):
        if not self._closed:
            self.close()


class ConnectionPool(object):
    """ a connection pool for a single connection alias."""
    def __init__(self,
                 max_poolsize=0,
                 keep_poolsize=1,
                 delay=0.2,
                 retries=10):
        # deque of unused connections
        self._free=deque()
        # list of in-use connections
        # we need real references to these, not just a count.
        self._busy=[]
        # maximum number of connections to create
        # 0 or a negative value means no maximum
        self._max_poolsize=max_poolsize
        # maximum number of connections to keep alive
        self._keep_poolsize=keep_poolsize
        # time to sleep in seconds if max_poolsize connections are in
        # use before retrying
        self._delay=delay
        # number of times to retry in that case
        self._retries=retries
        self._lock=Lock()

    def connect(self, connectFunc, connectArgs, initFunc=None):
        return self._connect(connectFunc,
                             connectArgs,
                             initFunc,
                             self._retries)

    def _connect(self, connectFunc, connectArgs, initFunc, retries):
        """internal method; don't call it"""
        max_poolsize=self._max_poolsize
            
        self._lock.acquire()            
        try:
            # is there a connection available?
            free=self._free
            busy=self._busy
            if free:
                c=free.popleft()
                busy.append(c)
            else:
                lenbusy=len(busy)
                if max_poolsize>0:
                    # there is a cap on the number of connections
                    # we are allowed to create
                    assert lenbusy <= max_poolsize
                    if lenbusy==max_poolsize:
                        # can't create more, must retry or barf
                        if not retries:
                            # barf
                            raise PyDOError, \
                                  ("all connections in use, attempted retries: "
                                   "%d") % self._retries
                        else:
                            # retry, but get out of the mutex first
                            c=None
                    else:
                        # All are in use and we are allowed to create more.
                        # Do so.
                        c=_real_connect(connectFunc, connectArgs, initFunc)
                        busy.append(c)
                else:
                    # unlimited headroom, create new connection
                    c=_real_connect(connectFunc, connectArgs, initFunc)
                    busy.append(c)
        finally:
            self._lock.release()
        if c:
            if self.onHandOut(c):
                return ConnectionWrapper(c, self)
            else:
                # not ok, completely expunge this connection
                busy.remove(c)
                # we're going to block, encourage c to die first
                del c
        # wait and then retry
        time.sleep(self._delay)             
        return self._connect(connectFunc, connectArgs, initFunc, retries-1)

    def release(self, conn):
        keep_poolsize=self._keep_poolsize
        self._lock.acquire()
        try:
            # do we keep this connection?
            free=self._free
            busy=self._busy
            numconns=len(free)+len(busy)
            keep=keep_poolsize >= numconns
            busy.remove(conn)
            if keep:
                free.append(conn)
            self.onRelease(conn)
        finally:
            self._lock.release()

    def onRelease(self, realConn):
        """anything you want to do to a connection when it is returned
        (default: rollback)"""
        try:
            #if not realConn.autocommit:
            realConn.rollback()
        except:
            # psycopg 2 doesn't seems to support autocommit, which
            # seems bogus to me...
            pass

        

    def onHandOut(self, realConn):
        """any test you want to perform on a cached (i.e., not newly
        connected) connection before giving it out.  If the connection
        isn't good, return False"""
        if hasattr(realConn, 'closed'):
            return not realConn.closed
        if hasattr(realConn, 'open'):
            return realConn.open
        return 1
        


__all__=['initAlias',
         'delAlias',
         'getConnection',
         'ConnectionPool']

