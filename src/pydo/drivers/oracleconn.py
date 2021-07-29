from pydo.dbi import DBIBase, ConnectionPool
from pydo.exceptions import PyDOError
from pydo.operators import BindingConverter
from pydo.dbtypes import DATE, TIMESTAMP, BINARY, INTERVAL
from pydo.log import debug
from pydo.field import Field
import cx_Oracle
from itertools import groupby
from operator import itemgetter

class OracleDBI(DBIBase):

    paramstyle = 'named'
    autocommit = None
    auto_increment = True  # Assume a trigger increments the relevant sequence
    
    def __init__(self, connectArgs, pool=None, verbose=False, initFunc=None):
       if pool and not hasattr(pool, 'connect'):
          pool = ConnectionPool()
       super(OracleDBI, self).__init__(connectArgs, cx_Oracle.connect,
           cx_Oracle, pool, verbose, initFunc)

    @staticmethod
    def sequence_mapper(table, column):
        return "%s_%s_SEQ" % (table, column)
    
    def execute(self, sql, values=(), qualified=False):
        """Executes the statement with the values and does conversion
        of the return result as necessary.
        result is list of dictionaries, or number of rows affected"""
        if self.verbose:
            debug("SQL: %s", sql)
            debug("bind variables: %s", values)
        c = self.conn.cursor()
        if values:
            c.execute(sql, values)
        else:
            c.execute(sql)
        if c.description is None:
            resultset = None
        else:
            lob_types = set((cx_Oracle.CLOB, cx_Oracle.BLOB))
            field_types = set(d[1] for d in c.description)
            have_lobs = field_types & lob_types
            if have_lobs:
                resultset = [list(self.field_values(row)) for row in c]
            else:
                resultset = c.fetchall()
        if not resultset:
            return c.rowcount
        res = self._convertResultSet(c.description, resultset, qualified)
        c.close()
        return res

    @staticmethod
    def field_values(row):
        """Produces the value of each item in the row, reading any LOBs before 
        the LOB locators get invalidated by a subsequent fetch."""
        for item in row:
            if hasattr(item, "read"):
                yield item.read()
            else:
                yield item

    def getAutoIncrement(self, name):
        """If db uses auto increment, should obtain
        the value of the auto-incremented field named 'name'"""
        cur = self.conn.cursor()
        sql= "SELECT %s.CURRVAL from dual" % name
        cur.execute(sql)
        (result,) = cur.fetchone()
        cur.close()
        return result

    def listTables(self, schema=None):
        """lists the tables in the database schema"""
        if schema is None:
            schema = 'PUBLIC'
        sql = """
            SELECT t.object_name
            FROM sys.all_objects t
            WHERE t.owner = :schema AND t.object_type IN ('TABLE', 'VIEW')
            """
        cur = self.conn.cursor()
        if self.verbose:
            debug("SQL: %s", (sql,))
        cur.execute(sql, schema=schema)
        res = cur.fetchall()
        cur.close()
        if not res:
            return []
        return sorted(x[0] for x in res)

    def describeTable(self, table, schema=None, sequence_mapper=None):
        """for the given table, returns a 2-tuple: a dict of Field objects
        keyed by name, and list of multi-column unique constraints (sets of Fields)).
        The Field instances should contain information about whether they are unique
        or sequenced.
        """
        if schema is None:
            schema = 'PUBLIC'
            
        cur = self.conn.cursor()

        # Build dict of Field objects
        sql= """
            SELECT tc.column_name, nullable
            FROM sys.all_tab_columns tc
            WHERE tc.owner = :schema AND tc.table_name = :table_name
            ORDER BY column_id
            """
        cur.execute(sql, schema=schema, table_name=table)
        fields = {}
        for row in cur:
            (column_name, nullable) = row
            if nullable:
                fields[column_name] = Field(column_name)
        if not fields:
            raise Exception("table %s not found" % table)

        # Get uniqueness constraints
        sql= """
            SELECT concol.constraint_name, concol.column_name
            FROM sys.all_constraints con
            JOIN sys.all_cons_columns concol ON con.constraint_name = concol.constraint_name
            WHERE con.owner = :schema AND con.table_name = :table_name
                AND con.constraint_type in ('P', 'U')
            ORDER BY constraint_name
            """
        cur.execute(sql, schema=schema, table_name=table)
        unique = set()
        for (key, rows) in groupby(cur, itemgetter(0)):
            columns = frozenset(r[1] for r in rows)
            unique.add(columns)
            if len(columns) == 1:
                fields[list(columns)[0]].unique = True

        # Get Sequence fields. Essentially this is a best guess as Oracle doesn't have an 
        # autosequence type as such, this functionality typically being implemented via a trigger 
        # that increments a user-specified sequence. For all numeric fields that are modified by 
        # a trigger, I check if the sequence exists whose name is given by the sequence_mapper 
        # function (supplied as a parameter to describeTable).
        sql = """
            SELECT seq.sequence_name
            FROM sys.all_sequences seq
            WHERE seq.sequence_owner = :schema
            """
        cur.execute(sql, schema=schema)
        sequences = frozenset(sequence for (sequence,) in cur)
        if not sequence_mapper:
            sequence_mapper = self.sequence_mapper
        sql = """
            SELECT tabcol.column_name
            FROM sys.all_tab_cols tabcol
                JOIN sys.all_trigger_cols trigcol ON tabcol.owner = trigcol.table_owner  
                    AND tabcol.table_name = trigcol.table_name 
                    AND tabcol.column_name = trigcol.column_name
				JOIN sys.all_triggers trig ON trigcol.trigger_owner = trig.owner 
                    AND trigcol.trigger_name = trig.trigger_name 
            WHERE tabcol.owner = :schema AND tabcol.table_name = :table_name 
                 AND tabcol.data_type = 'NUMBER' AND trigcol.column_usage = 'NEW OUT'
				 AND trig.status = 'ENABLED'
            """
        cur.execute(sql, schema=schema, table_name=table)
        for (column,) in cur:
            sequence = sequence_mapper(table, column)
            if sequence in sequences:
                fields[column].sequence = sequence

        return fields, unique
