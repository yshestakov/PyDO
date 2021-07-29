from pydo.dbi import getConnection
from pydo.field import Field
from pydo.guesscache import GuessCache
from pydo.exceptions import PyDOError
from pydo.operators import AND, EQ, FIELD, IS, NULL
from pydo.dbtypes import unwrap
from pydo.utils import (_tupleize, _setize, formatTexp, moduleize,
                        _strip_tablename, every, string_to_obj)

from itertools import izip
import re
from inspect import isfunction

_group_pat=re.compile(r'\s*group ', re.I)
_as_pat=re.compile(r'^(\w+)\s+as\s+(\w+)$', re.I)

def _restrict(flds, coll):
    """private method for cleaning a set or dict of any items that aren't
    in a field list (or dict); needed for handling attribute inheritance
    for projections"""
    
    # handle sets (_unique).  Sets may contain groupings of fieldnames
    # for multi-column unique constraints; this tests each member of
    # the grouping (sets, frozensets, lists, and tuples are tolerated)

    def infld(thing, flds):
        if thing in flds:
            return True
        if hasattr(thing, 'asname'):
            if thing.asname in flds:
                return True
        return False
    
    if isinstance(coll, set):
        s=set()
        for v in coll:
            # this isn't where the type of the set element
            # is enforced
            if isinstance(v, (set, frozenset, tuple, list)):
                for v1 in v:
                    if not infld(v1, flds):
                        break
                    else:
                        # (added just to make indentation clearer)
                        continue
                else:
                    # if we get here, the fields in the
                    # grouping are in the projection
                    s.add(v)
            elif infld(v,flds):
                s.add(v)
        return s
    # It isn't necessary to test for multi-column keys in dicts
    elif isinstance(coll, dict):
        return dict((x, y) for x, y in coll.iteritems() if infld(x,flds))

class _metapydo(type):
    """metaclass for _pydobase.
    Manages attribute inheritance.
    """

    def __init__(cls, cl_name, bases, namespace):
        # add a dictionary to store projections for this class.
        cls._projections={}
        # tablename guessing
        if namespace.get('table') is not None:
            # table has been explicitly declared, so
            # turn off guess_tablename for subclasses
            if not namespace.has_key('guess_tablename'):
                cls.guess_tablename=False
        elif cls.guess_tablename:
            # leave guess_tablename for subclasses
            cls.table=cl_name.lower()

        # sequence mapping
        sequence_mapper = namespace.get("sequence_mapper")
        if isfunction(sequence_mapper):
            cls.sequence_mapper = staticmethod(sequence_mapper)
        else:
            cls.sequence_mapper = sequence_mapper

        # field guessing
        if namespace.get('guess_columns', False):
            if cls.guesscache == True:
                # supply default cache
                cls.guesscache=GuessCache()
            elif isinstance(cls.guesscache, basestring):
                # assume it is a path
                cls.guesscache=GuessCache(cls.guesscache)
            if 'fields' in namespace or 'unique' in namespace:
                raise ValueError, ("incompatible declarations: guess_columns "
                                   "with explicit declaration of fields and/or unique")
            gfields, gunique=cls._getTableDescription()
            namespace['fields']=gfields.values()
            namespace['unique']=gunique
        
        # create Field objects declared locally in this class
        # and store them in a temporary dict
        fielddict={}
        # we keep track of which fields are declared just with a string;
        # inheritance semantics are a little different for these
        simplefields=set()
        for f in namespace.get('fields', ()):
            # support for tuple syntax for plain Jane fields.
            if isinstance(f, basestring):
                m=_as_pat.match(f)
                if m:
                    name=m.group(1)
                    asname=m.group(2)
                    simplefields.add(asname)
                    f=cls._create_field(name=name, asname=asname)
                else:
                    simplefields.add(f)                
                    f=cls._create_field(f)
            elif isinstance(f, dict):
                f=cls._create_field(**f)
            elif isinstance(f, (tuple, list)):
                f=cls._create_field(*f)
            elif not isinstance(f, Field):
                raise ValueError, "cannot coerce into a field: %s" % f
                
            # add to field container
            fielddict[f.asname]=f

        # handle inheritance of fields and unique declarations.
        # skipping object and dict is a trivial optimization,
        # because we know those classes won't be relevant

        revbases=[x for x in bases[::-1] if x not in (object, dict)]

        cls._fields={}
        uniqueset=set()
        for b in revbases:
            flds=getattr(b, '_fields', None)
            if flds:
                if cls._is_projection:
                    flds=_restrict(fielddict, flds)
                cls._fields.update(flds)
            uniq=getattr(b, 'unique', None)
            if uniq:
                # transform into a set of sets.  This way,
                # multi-column unique constraints are
                # unordered.
                uniq=set(_setize(x) for x in uniq)
                if cls._is_projection:
                    uniq=_restrict(fielddict, uniq)
                uniqueset.update(uniq)

        # If a field is declared upstream and you redeclare it in a
        # subclass as a simple field (just a fieldname), then the
        # previous field definition is inherited; otherwise, the
        # subclass's definition wins.  This is useful for projections.
        updatefields=((x, y) for x, y in fielddict.iteritems() \
                      if not (x in cls._fields and x in simplefields))
        cls._fields.update(updatefields)
        uniqueset.update(_setize(x) for x in namespace.get('unique', ()))

        # We now have all the inherited declarations, and figure out
        # sequences and additional unique constraints.
        cls._sequenced={}
        for f in cls._fields.itervalues():
            if f.sequence:
                cls._sequenced[f.asname] = f.sequence
            if f.unique:
                uniqueset.add(frozenset((f.asname,)))

        cls._unique=frozenset(uniqueset)

        # add attribute access to fields
        if cls.use_attributes:
            for name in cls._fields:
                if not hasattr(cls, name):
                    # a field is also a descriptor
                    setattr(cls, name, cls._fields[name])
        
class PyDO(dict):
    """ Base class for PyDO data classes."""

    __metaclass__=_metapydo

    # subclasses may customize these
    guess_tablename=True
    guess_columns=False
    sequence_mapper=None
    use_attributes=True
    mutable=True
    connectionAlias=None
    table=None
    schema=None
    refetch=False
    guesscache=None
    _ignore_update_rowcount=False
    
    ## not defined by default, but if you aren't using guess_columns
    ## you'll want to define it at some point in your class hierarchy
    # fields 

    # private - don't touch
    _is_projection=False

    @classmethod
    def _getTableDescription(cls):
        
        """ Supplies the table fields (as a dict of fieldnames to
        Field objects) and a list of multi-column unique constraints
        to the metaclass, which will call it when guessing columns.
        If cls.guesscache is false, this delegates directly to the DBI
        driver's describeTable() method, and performs no caching;
        otherwise, cls.guesscache is presumed to be something
        compatible a pydo.GuessCache, and it will be consulted and
        populated. 
        """
        args = [cls.getTable(False), cls.schema]
        if cls.sequence_mapper:
            args.append(cls.sequence_mapper)
        if cls.guesscache:
            data=cls.guesscache.retrieve(cls)
            if not data:
                data=cls.getDBI().describeTable(*args)
                cls.guesscache.store(cls, data)
            return data
        else:
            return cls.getDBI().describeTable(*args)
    
    @staticmethod
    def _create_field(*args, **kwargs):
        """ controls how fields are created when declared in the field
        list with a simple string, list, tuple, or dictionary rather
        than a field instance.  By default, passes field declaration
        to the Field constructor.
        """
        
        return Field(*args, **kwargs)

    @classmethod
    def getTable(cls, withSchema=True):
        """returns the name of the table, qualified with the schema,
        if any, if withSchema is true.
        """
       
        if cls.schema and withSchema:
            return '%s.%s' % (cls.schema, cls.table)
        else:
            return cls.table


    @classmethod
    def project(cls, *fields, **kwargs):
        # also accept passing in a list or tuple (backwards compatibility)
        if len(fields)==1 and isinstance(fields[0], (list, tuple)):
            fields=fields[0]
            
        acceptable=frozenset(('mutable','module'))
        diff=frozenset(kwargs)-acceptable
        if diff:
            raise ValueError, "unrecognized keyword arguments: %s" \
                  % ', '.join(str(x) for x in diff)
        mutable=kwargs.get('mutable', cls.mutable)
        module=kwargs.get('module', None)
        s=[]
        for f in fields:
            if not isinstance(f, Field):
                if isinstance(f, dict):
                    f=cls._create_field(**f)
                elif isinstance(f, (list, tuple)):
                    f=cls._create_field(*f)
                elif isinstance(f, basestring):
                    f=cls._create_field(f)
                else:
                    raise ValueError, "weird thing in field list: %s" % f
            s.append(f.asname.lower())
        s.sort()
        if kwargs:
            s.append('0')
            s.append('_'.join(sorted('%s_%s' % x for x in kwargs.items())))        
        t=tuple(s)
        if cls._projections.has_key(t):
            kls=cls._projections[t]
        else:
            klsname='projection_%s__%s' % (cls.__name__,
                                           '_'.join(s))
            kls=type(klsname, (cls,), dict(fields=fields,
                                           mutable=mutable,
                                           table=cls.getTable(False),
                                           _is_projection=True))
            cls._projections[t]=kls
        if module:
            moduleize(module, kls)
        return kls


    def update(self, adict):
        """ Part of dictionary interface for field access"""
        if not self.mutable:
            raise ValueError, "instance isn't mutable!"
        if not self._unique:
            raise ValueError, "cannot update without unique index!"
        # call (normally empty) hook for modifying the update
        d=self.onUpdate(adict)
        # Check that the fields in the dictionary are kosher
        self._validateFields(d)
        # do the actual update
        self._update_raw(d)
        # if successful, modify the object's field data,
        # taking any wrapped values out of their wrappers
        unwrapped=dict((k, unwrap(v)) for k,v in d.iteritems())
        super(PyDO, self).update(unwrapped)

    def onUpdate(self, adict):
        """a hook for subclasses to modify/validate updates; 
        by default returns the original data unchanged."""
        return adict

    def __setitem__(self, k, v):
        self.update({k:v})

    def _update_raw(self, adict):
        """update self in database with the values in adict"""

        # precondition: fields in adict are already validated,
        # and class/instance is mutable

        conn=self.getDBI()
        converter=conn.getConverter()
        sqlbuff=["%s  = %s" % (x, converter(y)) for x, y in adict.iteritems()]
        # pass in the same converter so that we don't get generated
        # interpolation names that clobber any others
        where, values=self._uniqueWhere(conn, self, converter)
        sql = "UPDATE %s SET %s WHERE %s" % (self.getTable(),
                                             ", ".join(sqlbuff),
                                             where)
        result=conn.execute(sql, values)
        # mysql will return 0 if the update was vacuous,
        # but that doesn't imply failure.  Postgresql and sqlite
        # will return 1 in this case.  
        if conn.has_sane_rowcount and result !=1:
            # hack/hook to enable updateable views to work that don't
            # return a correct rowcount.  (This is probably unnecessary now 
            # that we accept 0.)
            if self._ignore_update_rowcount:
                pass
            else:
                raise PyDOError, "updated %s rows instead of 1" % result        

    @classmethod
    def updateSome(cls, adict, *args, **fieldData):
        """update possibly many records at once, and return the number updated"""
        if not cls.mutable:
            raise ValueError, "class isn't mutable!"
        # N.B. it *is* possible to use this method without a unique index
        if not adict:
            # vacuous update, just return
            return
        cls._validateFields(adict)
        conn=cls.getDBI()
        converter=conn.getConverter()
        sqlbuff=["UPDATE ",
                 cls.getTable(),
                 " SET ",
                 ', '.join(["%s = %s" % (x, converter(y)) \
                            for x, y in adict.iteritems()])]
        where, values=cls._processWhere(conn, args, fieldData, converter)
        if where:
            sqlbuff.extend([' WHERE ', where])
        return conn.execute(''.join(sqlbuff), values)


    def dict(self):
        """returns a copy of self as a plain dict"""
        return dict(self)

    def copy(self):
        """returns a copy of self"""
        return self.__class__(dict(self))
    
    def clear(self):
        """not implemented for PyDO classes"""
        raise NotImplementedError, "PyDO classes don't implement clear()"

    def pop(self):
        """not implemented for PyDO classes"""
        raise NotImplementedError, "PyDO classes don't implement pop()"

    def popitem(self):
        """not implemented for PyDO classes"""
        raise NotImplementedError, "PyDO classes don't implement popitem()"

    def setdefault(self, key, val):
        """not implemented for PyDO classes"""
        raise NotImplementedError, "PyDO classes don't implement setdefault()"
    
    @classmethod
    def getColumns(cls, qualifier=None, with_as=False):
        """Returns a list of all columns in this table, in no
        particular order.

        If qualifier is true, returns fully qualified column names
        (i.e., table.column).  If you pass in a string to qualifier,
        it will be used as a table alias; otherwise the table name
        will be used.
        
        """
        if qualifier and not isinstance(qualifier, basestring):
            qualifier=cls.getTable()
        if with_as:
            return [x.get_column_expression(qualifier) for x in cls._fields.itervalues()]
        elif not qualifier:
            return cls._fields.keys()
        else:
            return ["%s.%s" % (qualifier, x) for x in cls._fields.iterkeys()]

    @classmethod
    def getFields(cls):
        """returns the effective fields of the class"""
        return cls._fields.copy()

    @classmethod
    def getUniquenessConstraints(cls):
        """returns the effective uniqueness constraints of the class"""
        return cls._unique

    @classmethod
    def getSequences(cls):
        """returns the effective sequences for the class"""
        return cls._sequenced.copy()


    @classmethod
    def _validateFields(cls, adict):
        """a simple field validator that verifies that the keys
        in the dictionary passed are declared fields in the class.
        """
        asnames=cls._fields
        for k in adict:
            if not k in asnames:
                raise KeyError, "object %s has no field %s" %\
                      (cls, k)

    # DB interface
    @classmethod
    def getDBI(cls):
        """return the database interface"""
        conn=getConnection(cls.connectionAlias)
        return conn

    @classmethod
    def commit(cls):
        """ Commit changes to database"""
        cls.getDBI().commit()

    @classmethod
    def rollback(cls):
        """ Rollback current transaction"""
        cls.getDBI().rollback()

    @classmethod
    def new(cls, **fieldData):
        """create and return a new data class instance using the
        values in fieldData.  This will also effect an INSERT into the
        database.  If the keyword argument refetch is passed and is true,
        or, if it is not and cls.refetch is true, effectively do a getUnique
        on cls.  """
        if 'refetch' in cls._fields:
            # don't use refetch keyword
            refetch=cls.refetch
        elif 'refetch' in fieldData:
            refetch=fieldData.pop('refetch')
        else:
            refetch=cls.refetch
        return cls._new(fieldData, refetch)

    @classmethod
    def newfetch(cls, **fieldData):
        """like new(), but always refetches."""
        return cls._new(fieldData, 1)

    @classmethod
    def newnofetch(cls, **fieldData):
        """like new(), but never refetches."""
        return cls._new(fieldData, 0)

    @classmethod
    def _new(cls, fieldData, refetch):
        if not cls.mutable:
            raise ValueError, 'cannot make a new immutable object!'
        if refetch and not cls._unique:
            raise ValueError, "cannot refetch without a unique index!"
        # sanity check the field data
        cls._validateFields(fieldData)
        
        conn = cls.getDBI()

        if not conn.auto_increment:
            for s, sn in cls._sequenced.items():
                if not fieldData.has_key(s):
                    fieldData[s] = conn.getSequence(sn, s, cls.getTable(True))
        cols=fieldData.keys()
        vals=[fieldData[c] for c in cols]
        converter=conn.getConverter()
        converted=map(converter, vals)
        
        sql = 'INSERT INTO %s (%s) VALUES  (%s)' \
              % (cls.getTable(),
                 ', '.join(cols),
                 ', '.join(converted))
        res = conn.execute(sql, converter.values)
        if res != 1:
            raise PyDOError, "inserted %s rows instead of 1" % res
        
        if conn.auto_increment:
            for k, v in cls._sequenced.items():
                if not fieldData.has_key(k):
                    if v == True:
                        v = cls._sequence_for(k)
                    fieldData[k] = conn.getAutoIncrement(v)
        # unwrap any wrapped values in fieldData
        fieldData=dict((k, unwrap(v)) for k,v in fieldData.iteritems())
        if not refetch:
            # add None for any missing columns
            for c in cls.getColumns():
                fieldData.setdefault(c, None)
            return cls(fieldData)
        return cls.getUnique(**fieldData)

    @classmethod
    def _sequence_for(cls, field):
        mapper = cls.sequence_mapper or getattr(cls.getDBI(), 'sequence_mapper', None)
        if mapper:
            return mapper(cls.table, field)
        
    @classmethod
    def _matchUnique(cls, kw):
        """return a tuple of column names that will uniquely identify
        a row given the choices from kw
        """
        ulist=[]
        for unique in cls._unique:
            if isinstance(unique, basestring):
                if kw.has_key(unique): 
                    ulist.append(unique)
            elif isinstance(unique, (frozenset,list,tuple)):
                for u in unique:
                    if not kw.has_key(u):
                        break
                else:
                    ulist.extend(list(unique))
        return tuple(ulist)

    @classmethod
    def _uniqueWhere(cls, conn, kw, converter=None):
        """given a connection and kw, using _matchUnique, generate a
        where clause to select a unique row.
        """
        unique = cls._matchUnique(kw)
        if not unique:
            raise ValueError, 'No way to get unique row! %s %s' % \
                  (str(kw), unique)
        for u in unique:
            if kw[u] in (None, NULL):
                raise ValueError, "NULL value encountered for field declared unique: %s" % u
            
        if converter is None:
            converter=conn.getConverter()        
        if len(unique)==1:
            u=tuple(unique)[0]
            sql=str(EQ(FIELD(u), kw[u], converter=converter))
        else:
            sql=str(AND(converter=converter, *[EQ(FIELD(u), kw[u]) for u in unique]))
        return sql, converter.values

    
    @classmethod
    def getUnique(cls, **fieldData):
        """ Retrieve one particular instance of this class.
        
        Given the attribute/value pairs in fieldData, retrieve a unique row
        and return a data class instance representing said row or None
        if no row was retrieved.
        """
        cls._validateFields(fieldData)
        conn = cls.getDBI()
        where, values = cls._uniqueWhere(conn, fieldData)
        sql = "%s WHERE %s" % (cls._baseSelect(), where)
        results = conn.execute(sql, values)
        if not results or not isinstance(results, (list,tuple)):
            return
        if len(results) > 1:
            raise PyDOError, 'got more than one row on unique query!'
        if results:
            return cls(results[0]) 

    @classmethod
    def _baseSelect(cls, qualified=False):
        """returns the beginning of a select statement for this object's table."""
        return 'SELECT %s FROM %s' % (', '.join(cls.getColumns(qualified, with_as=True)),
                                      cls.getTable())


    @staticmethod
    def _processWhere(conn, args, fieldData, converter=None):
        if args and isinstance(args[0], basestring):
            if fieldData:
                raise ValueError, "cannot pass keyword args when including sql string"
            sql=args[0]
            values=args[1:]
            if len(values)==1 and isinstance(values[0], dict):
                values=values[0]
            # the converter may conceivably contain values as well;
            # merging them in this case is not foolproof, but can be done
            # is some cases.
            if converter:
                origVals=converter.values
                if origVals:
                    if isinstance(values, dict):
                        if isinstance(origVals, dict):
                            origVals.update(values)
                            values=origVals
                        else:
                            # two different bind formats are being used, that's a no-no.
                            raise ValueError, "incompatible bind variable format"
                    else:
                        if isinstance(origVals, dict):
                            raise ValueError, "incompatible bind variable format"
                        assert isinstance(origVals, (list, tuple))
                        values=list(origVals)+list(values)
        else:
            # N.B. -- we don't call _validateFields here, as we permit
            # fields expressed as keyword arguments that aren't 
            # declared in the class/projection.
            andValues=list(args)
            for k, v in fieldData.items():
                if v is None or v == NULL:
                    andValues.append(IS(FIELD(k), NULL))
                else:
                    andValues.append(EQ(FIELD(k), v)) 
            andlen=len(andValues)
            if converter is None:
                converter=conn.getConverter()
            if andlen==0:
                sql=''
            elif andlen==1:
                andValues[0].setConverter(converter)
                sql=repr(andValues[0])
            else:
                sql=repr(AND(converter=converter, *andValues))
            values=converter.values
        return sql, values


    @classmethod
    def getSome(cls,
                *args,
                **fieldData):
        """ Retrieve some objects of this particular class.

        [todo: examples of use of operators, column-name keyword args,
        order, limit, and offset.]

        If you use SQL directly and pass variables, it is up to
        you to use the same paramstyle as the underlying driver.
        
        """
        order=fieldData.pop('order', None)
        limit=fieldData.pop('limit', None)
        offset=fieldData.pop('offset', None)
        
        conn=cls.getDBI()
        sql, values=cls._processWhere(conn, args, fieldData)
        query=[cls._baseSelect()]
        if sql:
            if _group_pat.match(sql):
                query.append(sql)
            else:
                query.extend(['WHERE', sql])
        if filter(None, (order, limit, offset)):
            query.append(conn.orderByString(order, limit, offset))
        query=' '.join(query)

        results = conn.execute(query, values)
        if results and isinstance(results, (list, tuple)):
            return map(cls, results)
        else:
            return []

    @classmethod
    def getCount(cls, *args, **fieldData):
        """ Retrieve the number of object of this particular class,
            optionally limited by query arguments.
        """

        proj=cls.project("COUNT(*) AS count")
        res=proj.getSome(*args, **fieldData)
        if res:
            return res[0]['count']
        return 0


    @classmethod
    def deleteSome(cls, *args, **fieldData):
        """delete possibly many records at once, and return the number deleted"""
        if not cls.mutable:
            raise ValueError, "cannot deleteSome through an immutable class"
        conn=cls.getDBI()
        sql, values=cls._processWhere(conn, args, fieldData)
        query=["DELETE FROM %s" % cls.getTable()]
        if sql:
            query.extend(['WHERE', sql])
        return conn.execute(' '.join(query), values)

    def delete(self):
        """remove the row that represents me in the database"""
        if not self.mutable:
            raise ValueError, "instance isn't mutable!"
        if not self._unique:
            raise ValueError, "cannot delete, no unique index!"
        conn = self.getDBI()
        unique, values = self._uniqueWhere(conn, self)
        # if the class has unique constraints, and all data
        # is presented, there will be something returned from
        # unique unless someone is doing bad things to the
        # object 
        assert unique
        sql = 'DELETE FROM %s WHERE %s' % (self.getTable(), unique)
        conn.execute(sql, values)
        # shadow the class attribute with an instance attribute
        self.mutable = False

    def refresh(self):
        """refetch myself from the database"""
        if not self._unique:
            raise ValueError, "cannot refresh without a unique index"
        obj = self.getUnique(**self)
        if not obj:
            raise ValueError, "current object doesn't exist in database!"
        # the ordinary dict update needs to be called here, not the
        # overloaded method that updates the database!
        super(PyDO, self).update(obj)


    def joinTable(self,
                  thisAttrNames,
                  pivotTable,
                  thisSideColumns,
                  thatSideColumns,
                  thatObject,
                  thatAttrNames,
                  *whereArgs,
                  **extra):

        """Handles many to many relations.  In short, do:
        
        SELECT thatObject.getColumns(1)
        FROM thatObject.table, pivotTable
        WHERE pivotTable.thisSideColumn = self.myAttrName
        AND pivotTable.thatSideColumn = thatObject.table.thatAttrName
        
        and return a list of thatObjects representing the resulting
        rows.  The parameters which accept column names
        (thisAttrNames, thisSideColumns, thatSideColumns,
        thatAttrNames) can be strings (silently turned to tuples of
        length 1) or tuples of strings.  For each pair P of the two
        pairs (thisSideColumns, thisAttrNames) and (thatSideColumns,
        thatAttrNames) len(P[0]) must equal len(P[1]).

        In addition, you can add extra tables and arbitrary sql to the
        where clause, as you can with getSome(), including order,
        limit and offset, using the "extraTables", "order", "limit"
        and "offset" keyword arguments, using SQLOperators or
        (sql-string, bind values) as positional arguments, and by
        specifying columns by keyword argument.
        
        """
        extraTables=extra.pop('extraTables', None)
        if extraTables:
            extraTables=list(_tupleize(extraTables))
        order=extra.pop('order', None)
        limit=extra.pop('limit', None)
        offset=extra.pop('offset', None)
        conn=self.getDBI()
        converter=conn.getConverter()
        wheresql, wherevals=self._processWhere(conn, whereArgs, extra, converter=converter)
        sql, vals = self._joinTableSQL(conn,
                                       thisAttrNames,
                                       pivotTable,
                                       thisSideColumns,
                                       thatSideColumns,
                                       thatObject,
                                       thatAttrNames,
                                       extraTables,
                                       wheresql,
                                       converter,
                                       order,
                                       limit,
                                       offset)
        results = conn.execute(sql, vals)
        if results and isinstance(results, (list, tuple)):
            return map(thatObject, results)
        return []

    def _joinTableSQL(self,
                      conn,
                      thisAttrNames,
                      pivotTable,
                      thisSideColumns,
                      thatSideColumns,
                      thatObject,
                      thatAttrNames,
                      extraTables,
                      wheresql,
                      converter,
                      order,
                      limit,
                      offset):
        """SQL generating function for joinTable"""
        if extraTables is None:
            extraTables=[]

        thisAttrNames = _tupleize(thisAttrNames)
        thisSideColumns = _tupleize(thisSideColumns)
        thatSideColumns = _tupleize(thatSideColumns)
        thatAttrNames = _tupleize(thatAttrNames)
        
        if len(thisSideColumns) != len(thisAttrNames):
            raise ValueError, ('thisSideColumns and thisAttrNames must '
                               'contain the same number of elements')
        if len(thatSideColumns) != len(thatAttrNames):
            raise ValueError, ('thatSideColumns and thatAttrNames must '
                               'contain the same number of elements')
        
        sql=[thatObject._baseSelect(True),
             ', ',
             ', '.join([pivotTable]+extraTables),
             ' WHERE ']
        
        joins = []
        for attr, col in zip(thisAttrNames, thisSideColumns):
            lit=converter(self[attr])
            joins.append("%s.%s = %s" % (pivotTable, col, lit))
        vals=converter.values
        joins.extend(['%s.%s = %s.%s' % (pivotTable,
                                         col,
                                         thatObject.getTable(),
                                         attr) \
                      for attr, col in zip(thatAttrNames,
                                           thatSideColumns)])
        sql.append(' AND '.join(joins))
        if wheresql:
            #sql.append(' AND (%s)' % wheresql)
            sql=' AND '.join(wheresql, sql)
        if filter(None, (order, limit, offset)):
            sql.append(conn.orderByString(order, limit, offset))                
        return ''.join(sql), vals

def autoschema(alias, schema=None, guesscache=True, module=None, sequence_mapper=None):
    """
    returns a dictionary of PyDO objects created automatically by
    schema introspection, keyed by class name.  Typical usage:

      globals().update(autoschema('myalias'))

    The PyDO objects created are extremely bare, but may be enough for
    quick scripts.   If you want to pickle them, pass in a module
    for them to live in for the "module" parameter.  
    """
    ns={}
    db=getConnection(alias)
    for table in db.listTables(schema):
        d=dict(guesscache=guesscache,
               guess_columns=True,
               connectionAlias=alias,
               schema=schema,
               table=table)
        if sequence_mapper:
            d['sequence_mapper'] = sequence_mapper
        Table=table.capitalize()
        obj=type(Table, (PyDO,), d)
        if module:
            moduleize(module, obj)
        ns[Table]=obj
    return ns



class ForeignKey(object):
    """ descriptor that enables succinct creation of foreign key attributes.
    Both single-column and multi-column foreign key associations are supported.

    Example usage:

    class A(PyDO):
        fields=(Sequence('id'),
                'b_fkey',
                'c_fkey1',
                'c_fkey2')
        B=ForeignKey('b_fkey', 'id', B)
        C=ForeignKey(('c_fkey1', 'c_fkey2'), ('key1', 'key2'), C)

    a=A.getUnique(id=1)
    a.B # returns B.getUnique(id=a.b_fkey)
    a.C # returns C.getUnique(key1=a.c_fkey1, key2=a.c_fkey2)
    a.C=my_C_instance # updates a with new values for c_fkey1 and c_fkey2 
    a.B=None # equivalent to a.b_fkey=None

    """
    def __init__(self, this_side, that_side, kls):
        """
        @type this_side: string or sequence
        @param this_side: name(s) of the column(s) in this PyDO class
             which references the key of another table
        @type that_side: string or sequence
        @param that_side: name(s) of the column(s) in the other PyDO class
             being referenced
        @type kls: PyDO
        @param kls: the other PyDO class
        """
        if isinstance(this_side, basestring):
            this_side=(this_side,)
        if isinstance(that_side, basestring):
            that_side=(that_side,)
        if len(this_side) != len(that_side):
            raise ValueError, \
                  "lengths of keys do not match: %d "\
                  "(length of %s) != %d (length of %s)" \
                  % (len(this_side), str(this_side),
                     len(that_side), str(that_side))
        self.this_side=this_side            
        self.that_side=that_side
        self._kls=kls

    def kls():
        def fget(self):
            if isinstance(self._kls, basestring):
                return string_to_obj(self._kls)
            return self._kls
        return fget
    kls=property(kls())

    def __get__(self, obj, type_):
        d=dict((x, obj[y]) for x, y in zip(self.that_side, self.this_side))
        if not every(None, d.itervalues()):
            return self.kls.getUnique(**d)

    def __set__(self, obj, value):
        if value in (None, NULL):
            obj.update(dict((f, None) for f in self.this_side))
        else:
            if not isinstance(value, self.kls):
                raise ValueError, "value passed is a %s, not an instance of %s" \
                      % (type(value), self.kls.__name__)
            else:
                obj.update(dict((this, value[that]) \
                                for this, that in zip(self.this_side,
                                                      self.that_side)))


def OneToMany(this_side, that_side, kls):
    """
    function to define an accessor to a 1-to-many relation.
    """
    if isinstance(this_side, basestring):
        this_side=(this_side,)
    if isinstance(that_side, basestring):
        that_side=(that_side,)
    if len(this_side) != len(that_side):
        raise ValueError, \
              "lengths of keys do not match: %d "\
              "(length of %s) != %d (length of %s)" \
              % (len(this_side), str(this_side),
                 len(that_side), str(that_side))
    zipped=zip(that_side, this_side)


    def getMany(self, *args, **kwargs):
        if isinstance(kls, basestring):
            # resolve it to a class
            realkls=string_to_obj(kls)
        else:
            realkls=kls
        eq=[EQ(FIELD(x), self[y]) for x, y in zipped]
        if args and isinstance(args[0], basestring):
            # combining a string requires awkward special casing...
            conn=self.getDBI()
            converter=conn.getConverter()
            sql, values=self._processWhere(conn, eq, {}, converter=converter)
            converter.reset()
            extrasql, extravalues=self._processWhere(conn, args, kwargs, converter=converter)
            # merge sql strings
            sql=' AND '.join((sql, extrasql))
            # merge values
            if isinstance(values, dict):
                if not isinstance(extravalues, dict):
                    raise ValueError, "expected dictionary of bind variables!"
                values.update(extravalues)
                newargs=(sql, values)
            else:
                values=tuple(values)+tuple(extravalues)
                newargs=(sql,)+values
            del converter
            return realkls.getSome(*newargs)
        
        else:
            return realkls.getSome(*(tuple(eq)+args), **kwargs)
    return getMany

def ManyToMany(this_side,
               pivot_table,
               this_pivot_side,
               that_pivot_side,
               kls,
               that_side):
    # conversions are already done inside joinTable
    def getMany(self, *args, **kwargs):
        if isinstance(kls, basestring):
            # resolve it to a class
            realkls=string_to_obj(kls)
        else:
            realkls=kls
        return self.joinTable(this_side,
                              pivot_table,
                              this_pivot_side,
                              that_pivot_side,
                              realkls,
                              that_side,                              
                              *args,
                              **kwargs)
    return getMany
                              
        
        


__all__=['PyDO', 'autoschema', 'ForeignKey', 'OneToMany', 'ManyToMany']
