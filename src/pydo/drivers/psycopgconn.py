"""
PyDO driver for PostgreSQL, using the psycopg driver.

Currently this has been tested with psycopg 1.1.18 and 1.99.1.12,
and attempts to support both.

"""

from pydo.dbi import DBIBase, ConnectionPool
from pydo.exceptions import PyDOError
from pydo.log import debug
from pydo.operators import BindingConverter
from pydo.dbtypes import (DATE, TIMESTAMP, BINARY, INTERVAL, 
                          date_formats, timestamp_formats)
from pydo.field import Field

import time
import datetime

try:
    import psycopg2 as psycopg
except ImportError:
    import psycopg

if psycopg.__version__[:3] >= '1.9':
    #psycopg version two.
    psycopg_version=2
else:
    psycopg_version=1

try:
   import mx.DateTime
   havemx=True
except ImportError:
   havemx=False
    
if havemx:
   try:
      from psycopg import TimestampFromMx
   except:
      assert psycopg_version==2
      def TimestampFromMx(x):
         return psycopg.TimestampFromTicks(x.ticks())
elif psycopg_version==1:
   raise ImportError, "mx.DateTime required when using psycopg version 1"

def convert_DATE(dt):
   val=dt.value
   if havemx and isinstance(val, mx.DateTime.DateTimeType):
      return psycopg.DateFromMx(val)
   elif isinstance(val, datetime.date):
      return psycopg.Date(dt.year, dt.month, dt.day)
   elif isinstance(val, (int, float, long)):
      d=datetime.date.fromtimestamp(val)
      return psycopg.Date(d.year, d.month, d.day)
   elif isinstance(val, (tuple, list)):
      return psycopg.Date(*val[:3])
   elif isinstance(val, basestring):
      for f in date_formats:
         try:
            t=time.strptime(val, f)[:3]
         except ValueError:
            continue
         else:
            return psycopg.Date(*t)
      else:
         raise ValueError, "cannot parse date format: '%s'" % val
   raise ValueError, val
    

def convert_TIMESTAMP(ts):
   val=ts.value
   if havemx and isinstance(val, mx.DateTime.DateTimeType):
      return TimestampFromMx(val)
   elif isinstance(val, datetime.datetime):
      return psycopg.TimestampFromTicks(time.mktime(ts.timetuple()))
   elif isinstance(val, (int, float, long)):
      return psycopg.TimestampFromTicks(val)
   elif isinstance(val, (tuple, list)) and len(val)==9:
      return psycopg.TimestampFromTicks(time.mktime(val))
   elif isinstance(val, basestring):
      for f in timestamp_formats:
         try:
            t=time.strptime(val, f)
         except ValueError:
            continue
         else:
            return psycopg.TimestampFromTicks(time.mktime(t))
      else:
         raise ValueError, "cannot parse timestamp format: '%s'" % val
   raise ValueError, val
    
_converters={datetime.datetime: lambda x: psycopg.TimestampFromTicks(time.mktime(x.timetuple())),
             datetime.date: lambda x: psycopg.Date(x.year, x.month, x.day),
             DATE: convert_DATE,
             TIMESTAMP: convert_TIMESTAMP,
             BINARY: lambda x: psycopg.Binary(x.value),
             INTERVAL: lambda x: x.value}

if havemx:
    # add automatic wrapping for mx.DateTime types
    _converters[mx.DateTime.DateTimeType]=TimestampFromMx
    _converters[mx.DateTime.DateTimeDeltaType]=lambda x: x.strftime("%d:%H:%M:%S")

class PsycopgConverter(BindingConverter): 
    converters=_converters

class PsycopgDBI(DBIBase):
    
    def __init__(self, connectArgs, pool=None, verbose=False, initFunc=None):
       if pool and not hasattr(pool, 'connect'):
          pool=ConnectionPool()
       super(PsycopgDBI, self).__init__(connectArgs,
                                        psycopg.connect,
                                        psycopg,
                                        pool,
                                        verbose,
                                        initFunc)
       if psycopg_version<2:
           # try to keep state
           self._autocommit=None

    if psycopg_version==2:
        def autocommit():
            def fget(self):
                return self.conn.isolation_level==0
            def fset(self, val):
                self.conn.set_isolation_level(not val)
            return fget, fset, None, None
        autocommit=property(*autocommit())

    else:
##         def autocommit():
##             def fget(self):
##                 return self._autocommit
##             def fset(self, val):
##                 self._autocommit=val
##                 if val:
##                     self.conn.autocommit()
##                 else:
##                     self.conn.autocommit(0)
##             return fget, fset, None, None
##        autocommit=property(*autocommit())
        autocommit=False
    
    def getConverter(self):
        return PsycopgConverter(self.paramstyle)
    
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
            c.execute(sql)
        if c.statusmessage=='SELECT':
            resultset=c.fetchall()
        else:
            resultset=None
        if not resultset:
            if c.statusmessage.startswith('INSERT') or c.statusmessage.startswith('UPDATE'):
                # rowcount doesn't work
                return int(c.statusmessage.split()[-1])
            return -1
        res=self._convertResultSet(c.description, resultset, qualified)
        c.close()
        return res    

    def getSequence(self, name, field, table):
        if name==True:
            # not a string; infer the sequence name
            name='%s_%s_seq' % (table, field)
            if self.verbose:
                debug('inferring sequence name: %s', name)
        cur=self.conn.cursor()
        sql="select nextval('%s')" % name
        if self.verbose:
            debug("SQL: %s", (sql,))
        cur.execute(sql)
        res=cur.fetchone()
        if not res:
            raise PyDOError, "could not get value for sequence %s!" % name
        return res[0]


    def listTables(self, schema=None):
        """lists the tables in the database schema"""
        if schema is None:
            schema='public'
        sql="""
        SELECT t.tablename AS name
        FROM pg_catalog.pg_tables t
        WHERE t.schemaname=%s
        UNION
        SELECT v.viewname AS name
        FROM pg_catalog.pg_views v
        WHERE v.schemaname=%s
        """
        cur=self.conn.cursor()
        if self.verbose:
            debug("SQL: %s", (sql,))
        cur.execute(sql, (schema, schema))
        res=cur.fetchall()
        cur.close()
        if not res:
            return []
        return sorted(x[0] for x in res)
        

    def describeTable(self, table, schema=None):
        # verify that the table exists
        sql = """
        SELECT t.tablename AS tname
        FROM pg_catalog.pg_tables t
        WHERE t.tablename=%s
        AND t.schemaname=%s
        UNION
        SELECT v.viewname AS tname
        FROM pg_catalog.pg_views v
        WHERE v.viewname=%s
        and v.schemaname=%s
        """
        if schema is None:
            schema='public'
        cur=self.conn.cursor()
        bind=(table, schema, table, schema)
        if self.verbose:
            debug("SQL: %s", (sql,))
        cur.execute(sql, bind)
        for row in cur.fetchall():
            # it exists, get on with it
            break
        else:
            raise ValueError, "no such table or view: %s.%s" % (schema, table)
        
        sql = """
        SELECT a.attname, a.attnum
        FROM pg_catalog.pg_attribute a,
          pg_catalog.pg_namespace n,
          pg_catalog.pg_class c
        WHERE a.attrelid = %s::regclass
          AND c.oid=a.attrelid
          AND c.relnamespace=n.oid
          AND n.nspname=%s
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
        """
        fields = {}
        cur = self.conn.cursor()
        if self.verbose:
            debug("SQL: %s", (sql,))
        qtable="%s.%s" % (schema, table)
        cur.execute(sql, (qtable,schema))
        for row in cur.fetchall():
            if self.verbose:
                debug("Found column %s" % list(row))
            fields[row[1]] = Field(row[0])
        sql = """
        SELECT indkey
        FROM pg_catalog.pg_index i,
        pg_catalog.pg_class c,
        pg_catalog.pg_namespace n,
        pg_catalog.pg_attribute a
        WHERE i.indrelid = %s::regclass
          AND c.oid=i.indrelid
          AND c.relnamespace=n.oid
          AND n.nspname=%s
          AND i.indisunique
          AND a.attrelid=c.oid
          AND a.attnum=indkey[0]
          AND a.attnotnull
        """
        unique = set()
        if self.verbose:
            debug("SQL: %s", (sql,))
        cur.execute(sql, (qtable,schema))
        for row in cur.fetchall():
            L=[int(i) for i in row[0].split(' ')]
            if [x for x in L if x < 0]:
                if self.verbose:
                    debug("skipping constraint with system columns: %s" % row[0])
                continue
            if self.verbose:
                debug("Found unique index on %s" % L)
            if len(L) == 1:
                fields[L[0]].unique = True
            else:
                unique.add(frozenset([fields[i].name for i in L]))

        sql = """
        SELECT c.relname
        FROM pg_catalog.pg_class c, pg_catalog.pg_namespace n
        WHERE relname like '%s_%%%%_seq'
          AND c.relnamespace=n.oid
          AND n.nspname=%%s
          AND relkind = 'S'
        """ % table
        if self.verbose:
            debug("SQL: %s", (sql,))
        cur.execute(sql, (schema,))
        for row in cur.fetchall():
            maybecolname = row[0][len(table) + 1:-4]
            for field in fields.values():
                if field.name == maybecolname:
                    if self.verbose:
                        debug("Found sequence %s on %s" % (row[0], field.name))
                    field.sequence = row[0]
                    break
        cur.close()
        d = {}
        for f in fields.values():
            d[f.name] = f
        return (d, unique)
    
