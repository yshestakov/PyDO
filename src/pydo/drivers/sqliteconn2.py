"""
PyDO driver for sqlite v3, using the sqlite3 module
(built in to Python 2.5+), falling back to the external
pysqlite2 module.

"""

from pydo.dbi import DBIBase, ConnectionPool
from pydo.field import Field, Sequence
from pydo.exceptions import PyDOError
from pydo.log import debug
from pydo.operators import BindingConverter

#
# Python 2.5 comes with pysqlite2 as standard,
# called sqlite3. Try to import it that way
# first. If that fails, assume we're on an
# earlier version of Python and import the
# external module.
#
try:
  from sqlite3 import dbapi2 as sqlite
except ImportError:
  from pysqlite2 import dbapi2 as sqlite

#
# sqlite registers converters for date and timestamp.
# But the matching is case-sensitive, and since I
# always use uppercase datatypes, reregister the
# variants here (only has effect for some versions of
# pysqlite2 (e.g., 2.2.2)
#
for t, ulist in (('date', ('DATE',)),
                 ('timestamp', ('TIMESTAMP', 'DATE'))):
  try:
    c=sqlite.converters[t]
  except KeyError:
    continue
  else:
    for u in ulist:
      if u not in sqlite.converters:
        sqlite.register_converter(u, c)
    del c, u
del t, ulist

      
#
# pysqlite has its own mechanism for handling conversions between
# database columns and Python datatypes: Dates and Datetimes are
# added by the module itself, and aliased above. Binary columns
# are returned as buffer objects. Other adapters can be added by
# user code, so there's no need to use PyDO's converter protocols.
#
# I'm not sure therefore if the SqliteConverter class really needs 
# to exist, but no harm in its being here explicitly, and maybe some 
# other conversion will be needed which sqlite can't cope with.
#
class SqliteConverter(BindingConverter):
    converters={}

#
# The sqlite conversion routines rely either on column datatype
# definitions or on column names to know which converter to apply.
# We're using datatype defs here (PARSE_DECLTYPES) which means
# that a column of type DATE will call the converter registered
# against that string (sqlite.converters['DATE']).
#
def sqlite_connect (*args, **kwargs):
  return sqlite.connect (detect_types=sqlite.PARSE_DECLTYPES, *args, **kwargs)

class SqliteDBI(DBIBase):
   # sqlite uses an auto increment approach to sequences
   auto_increment=True
   paramstyle = 'qmark'

   def __init__(self, connectArgs, pool=None, verbose=False, initFunc=None):
      if pool and not hasattr(pool, 'connect'):
         pool=ConnectionPool()
      super(SqliteDBI, self).__init__(connectArgs,
                                      sqlite_connect,
                                      sqlite,
                                      pool,
                                      verbose,
                                      initFunc)
      #
      # This appears to be the correct default value
      # for isolation level on pysqlite.
      #
      self._isolation_level = ""
   
   def getConverter(self):
      return SqliteConverter(self.paramstyle)

   def getAutoIncrement(self, name):
      sql="SELECT last_insert_rowid ()"
      return self.conn.execute (sql).fetchone ()[0]
   
   def listTables(self, schema=None):
      """list the tables in the database schema.
      The schema parameter is not supported by this driver.
      """
      if schema is not None:
         raise ValueError, "db schemas not supported by sqlite driver"
      sql="SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
      return self.conn.execute (sql).fetchall ()

   def describeTable(self, table, schema=None):
      if schema is not None:
         raise ValueError, "db schemas not supported by sqlite driver"
      
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
      
      sql="pragma table_info('%s')" % table
      execute(sql)
      res=c.fetchall()
      if not res:
         raise ValueError, "no such table: %s" % table
      for row in res:
         cid, name, type, notnull, dflt_value, pk=row
         # we ignore the nullable bit for sequences, because
         # apparently sqlite permits sequences to be defined as nullable
         # (thanks Tim Golden)
         if type=='INTEGER' and int(pk): # and int(notnull):
            # a sequence
            fields[name]=Sequence(name)
         else:
            fields[name]=Field(name)
         if not int(notnull):
            nullable.append(name)
            
      # get indexes
      sql="pragma index_list('%s')" % table
      execute(sql)
      res=c.fetchall()
      for row in res:
         seq, name, uneek=row
         if uneek:
            sql="pragma index_info('%s')" % name
            execute(sql)
            subres=c.fetchall()
            unset=frozenset(x[-1] for x in subres)
            if not unset.intersection(nullable):
               unique.add(unset)
      c.close()
      return fields, unique

   #
   # Slightly confusingly, pysqlite doesn't offer an autocommit
   # mode as such: you set it by setting the isolation level
   # to None. Unsetting it, therefore, is a slightly open
   # operation: I've taken the view that you should reset
   # isolation level to whatever it was before you used it
   # to set autocommit on.
   #
   def autocommit():
      def fget(self):
         return (self.conn.isolation_level is None)
      def fset(self, val):
         current_value = (self.conn.isolation_level is None)
         if bool (current_value) <> bool (val):
           if val:
              self._isolation_level = self.conn.isolation_level
              self.conn.isolation_level = None
           else:
              self.conn.isolation_level = self._isolation_level or ""
      return fget, fset, None, None
   autocommit=property(*autocommit())
