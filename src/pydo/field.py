import keyword
import warnings

class Field(object):
    """represents a column in a database table."""

    __slots__=('name', 'sequence', 'unique', 'asname')

    def __getstate__(self):
        return self.name, self.sequence, self.unique, self.asname

    def __setstate__(self, state):
        self.name, self.sequence, self.unique, self.asname=state
    
    def __init__(self,
                 name,
                 sequence=False,
                 unique=False,
                 asname=None):
        self.name=name
        if asname is None:
            asname=name
        self.asname=asname
        # change this if asname makes a difference
        if name in keyword.kwlist:
            warnings.warn('field name "%s" is a Python keyword!' % name)
        self.sequence=sequence
        self.unique=unique

    def get_column_expression(self, qualifier=None):
        if self.asname != self.name:
            name="%s AS %s" % (self.name, self.asname)
        else:
            name=self.name
        if qualifier:
            return ".".join([qualifier, name])
        return name

    def __get__(self, obj, type_):
        """descriptor method"""
        if obj is None:
            return None
        return obj[self.asname]
    
    def __set__(self, obj, value):
        """descriptor method"""
        return obj.update({self.asname: value})

    def __str__(self):
        return self.name

    def __repr__(self):
        if self.asname != self.name:
            name="%s AS %s" % (self.name, self.asname)
        else:
            name=self.name
        return "<%s instance \"%s\" at %x>" % \
               (self.__class__.__name__,
                name,
                id(self))

class Sequence(Field):
    """like a Field, except that sequence defaults to True, and the
    field must be unique.  If a sequence name needs to be specified,
    pass it through the "sequence" parameter.
    
    If for some reason you want a non-unique sequence, whatever that
    is, use the Field class directly
    """
    def __init__(self,
                 name,
                 sequence=None,
                 asname=None):
        if sequence is None:
            sequence=True
        super(Sequence, self).__init__(name,
                                       sequence,
                                       True,
                                       asname)

class Unique(Field):
    """like a Field, except that it must be unique and isn't a
    sequence (use Sequence for that)"""
    def __init__(self,
                 name,
                 asname=None):
        super(Unique, self).__init__(name,
                                     False,
                                     True,
                                     asname)


__all__=['Field', 'Sequence', 'Unique']







        
