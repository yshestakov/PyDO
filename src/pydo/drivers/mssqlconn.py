"""
PyDO driver for mssql, using the ADO adapter.
"""
from pydo.dbi import DBIBase, ConnectionPool
from pydo.field import Field, Sequence
from pydo.exceptions import PyDOError
from pydo.dbtypes import (DATE, TIMESTAMP, BINARY, INTERVAL,
                          date_formats, timestamp_formats)
from pydo.log import debug
from pydo.operators import BindingConverter

import time
import datetime

# do we actually need to import this, or is it optional? @@ TBD
import mx.DateTime

import adodbapi

def connection_string (server, database):
  return "Provider=SQLOLEDB;Data Source=%s;Initial Catalog=%s;Integrated Security=SSPI;" % (server, database)
  
def convert_DATE(dt):
   val=dt.value
   if isinstance(val, mx.DateTime.DateTimeType):
      return val
   elif isinstance(val, datetime.date):
      return mx.DateTime.DateFrom(dt.year, dt.month, dt.day)
   elif isinstance(val, (int, float, long)):
      d=datetime.date.fromtimestamp(val)
      return mx.DateTime.DateFrom(d.year, d.month, d.day)
   elif isinstance(val, (tuple, list)):
      return mx.DateTime.DateFrom(*val[:3])
   elif isinstance(val, basestring):
      for f in date_formats:
         try:
            t=time.strptime(val, f)[:3]
         except ValueError:
            continue
         else:
            return mx.DateTime.DateFrom(*t)
      else:
         raise ValueError, "cannot parse date format: '%s'" % val
   raise ValueError, val

def convert_TIMESTAMP(ts):
   val=ts.value
   if isinstance(val, mx.DateTime.DateTimeType):
      return val
   elif isinstance(val, datetime.datetime):
      return mx.DateTime.DateTimeFromTicks(time.mktime(ts.timetuple()))
   elif isinstance(val, (int, float, long)):
      return mx.DateTime.DateTimeFromTicks(val)
   elif isinstance(val, (tuple, list)) and len(val)==9:
      return mx.DateTime.DateTimeFromTicks(time.mktime(val))
   elif isinstance(val, basestring):
      for f in timestamp_formats:
         try:
            return mx.DateTime.strptime(val, f)
         except ValueError:
            continue
      else:
         raise ValueError, "cannot parse timestamp format: '%s'" % val
   raise ValueError, val


_converters={datetime.datetime: lambda x: mx.DateTime.DateTimeFromTicks(time.mktime(x.timetuple())),
             datetime.date: lambda x: mx.DateTime.DateFromTicks(time.mktime(x.timetuple())),
             DATE: convert_DATE,
             TIMESTAMP: convert_TIMESTAMP,
             # removing BINARY, was using sqlite.Binary ... @@ FIX ME
             INTERVAL: lambda x: x.value}

class MssqlConverter(BindingConverter):
    converters=_converters


class MssqlDBI(DBIBase):
   auto_increment=True

   def __init__(self, connectArgs, pool=None, verbose=False, initFunc=None):
      if pool and not hasattr(pool, 'connect'):
         pool=ConnectionPool()
      super(MssqlDBI, self).__init__(connectArgs,
                                     adodbapi.connect,
                                     adodbapi,
                                     pool,
                                     verbose,
                                     initFunc)

      autocommit = False

   def getConverter(self):
      return MssqlConverter(self.paramstyle)

   def getAutoIncrement(self, name):
      q = self.conn.db.cursor ()
      q.execute ("SELECT @@IDENTITY")
      return q.fetchone ()[0]

   def listTables(self, schema=None):
      """list the tables in the database schema.
      """
      if schema:
        sql="""
          SELECT
            TABLE_NAME
          FROM
            INFORMATION_SCHEMA.TABLES
          WHERE
            TABLE_TYPE='BASE_TABLE' AND
            SCHEMA='%s'
          ORDER BY
            TABLE_NAME
        """ % schema
      else:
        sql="""
          SELECT
            TABLE_NAME
          FROM
            INFORMATION_SCHEMA.TABLES
          WHERE
            TABLE_TYPE='BASE_TABLE'
          ORDER BY
            TABLE_NAME
        """
      c=self.conn.cursor()
      c.execute(sql)
      res=c.fetchall()
      if res:
         return sorted(x[0] for x in res)
      return ()

   def describeTable(self, table, schema=None):
      schema = schema or 'dbo'
      fields={}
      unique=set()

      nullable=[]
      c=self.conn.cursor()

      if self.verbose:
         def execute(sql):
            debug('SQL: %s', (sql,))
            c.execute(sql)
      else:
         execute=c.execute

      sql = """
        select 
          column_name = col.COLUMN_NAME, 
          is_nullable = CASE LOWER (col.IS_NULLABLE) WHEN 'yes' THEN 1 ELSE 0 END,
          is_identity = COLUMNPROPERTY (OBJECT_ID (col.TABLE_SCHEMA + '.' + col.TABLE_NAME), col.COLUMN_NAME, 'IsIdentity'),
          is_primary_key = CASE WHEN ccu.COLUMN_NAME IS NULL THEN 0 ELSE 1 END
        FROM
          INFORMATION_SCHEMA.COLUMNS AS col
        LEFT OUTER JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tco ON
          tco.TABLE_SCHEMA = col.TABLE_SCHEMA AND
          tco.TABLE_NAME = col.TABLE_NAME AND
          tco.CONSTRAINT_TYPE = 'PRIMARY KEY'
        LEFT OUTER JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE AS ccu ON
          ccu.CONSTRAINT_CATALOG = tco.CONSTRAINT_CATALOG AND
          ccu.CONSTRAINT_SCHEMA = tco.CONSTRAINT_SCHEMA AND
          ccu.CONSTRAINT_NAME = tco.CONSTRAINT_NAME AND
          ccu.COLUMN_NAME = col.COLUMN_NAME
        WHERE
          col.TABLE_SCHEMA = '%s' AND
          col.TABLE_NAME = '%s'
      """ % (schema, table)
      execute (sql)
      for name, is_nullable, is_identity, is_primary_key in c.fetchall ():
        #
        # We're only interested in a sequence if it is
        #  a NOT-NULL PK IDENTITY. 
        #  ROWGUIDCOL columns probably do not count here, 
        #   since their values have to be filled in by hand 
        #   although typically via a DEFAULT of NewID ().
        #
        if is_identity and not is_nullable and is_primary_key:
          fields[name] = Sequence (name)
        else:
          fields[name] = Field (name)
        if is_nullable:
          nullable.append (name)
        
      #
      # In theory this query should pull out unique constraints
      #  and unique indexes, but in practice it only pulls out
      #  the former.
      #
      constraint_sql = """
      SELECT
        tco.CONSTRAINT_CATALOG,
        tco.CONSTRAINT_SCHEMA,
        tco.CONSTRAINT_NAME
      FROM
        INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tco
      WHERE
        tco.TABLE_SCHEMA = '%s' AND
        tco.TABLE_NAME = '%s'
      AND
        tco.CONSTRAINT_TYPE IN ('UNIQUE', 'PRIMARY KEY')
      """ % (schema, table)
      column_sql = """
      SELECT
        ccu.COLUMN_NAME
      FROM
        INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE AS ccu
      WHERE
        ccu.CONSTRAINT_CATALOG = '%s' AND
        ccu.CONSTRAINT_SCHEMA = '%s' AND
        ccu.CONSTRAINT_NAME = '%s'
      """
      execute (constraint_sql)
      for constraint_catalog, constraint_schema, constraint_name in c.fetchall ():
        q2 = self.conn.cursor ()
        q2.execute (column_sql % (constraint_catalog, constraint_schema, constraint_name))
        unique.add (frozenset ([r[0] for r in q2.fetchall ()]))
        
      #
      # The adodbapi driver complains if the sp_helpindex returns with
      #  no indexes, so make sure that there is at least one before
      #  trying.
      #
      sql = """
      SELECT * FROM sysindexes WHERE id = OBJECT_ID ('%s.%s') AND indid BETWEEN 1 AND 254
      """ % (schema, table)
      execute (sql)
      rows = c.fetchall ()
      print "rows=", rows
      if rows: # c.fetchall ():
        sql = "sp_helpindex '%s.%s'" % (schema, table)
        execute (sql)
        for index_name, index_description, index_keys in c.fetchall ():
          #
          # The description field from sp_helpindex contains an ill-defined
          #  set of descriptors, somewhere including the word "unique". The
          #  separators could be commas or spaces, or both.
          #
          descriptions = [d.strip () for d in index_description.lower ().replace (",", " ").split ()]
          if "unique" in descriptions:
            unique.add (frozenset ([k.strip () for k in index_keys.split (",")]))
      
      return fields, unique
