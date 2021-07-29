"""

The dbtypes module contains generic type wrapper classes for values
passed into PyDO, to provide type information useful into marshalling
the data into SQL according to the intended datatype.  Some mapping of
datatype can be done solely on the basis of Python type, but at times
it may be necessary to be more specific.

DBAPI-compliant drivers use wrapper classes for this purpose, but they
are specific to the underlying driver; these wrappers can be used
with all drivers.

If you insert or update a wrapped value into a PyDO instance, the
value of the corresponding column in that instance will be the
unwrapped value, not the wrapper itself.

"""

class typewrapper(object):
    __slots__=('value',)
    def __init__(self, value):
        self.value=value

class DATE(typewrapper): pass
class TIMESTAMP(typewrapper): pass
class INTERVAL(typewrapper): pass
class BINARY(typewrapper): pass

def unwrap(val):
    if isinstance(val, typewrapper):
        return val.value
    return val

date_formats=['%m-%d-%Y',
              '%m-%d-%y',
              '%Y-%d-%m',
              '%y-%d-%m',
              '%B %d %Y',
              '%b %d %Y',
              '%d %B %Y',
              '%d %b %Y']

timestamp_formats=['%Y-%m-%d %H:%M:%S',
                   '%Y-%m-%d %H:%M',
                   '%y-%m-%d %H:%M:%S']


__all__=['DATE',
         'TIMESTAMP',
         'INTERVAL',
         'BINARY']


