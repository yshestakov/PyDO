"""
utility functions imported by other PyDO modules.
"""

import getpass
import sys
from pydo.log import debug


def _tupleize(item):
    """ turns an atom into a tuple with one element,
    and a non-atom into a tuple"""
    if isinstance(item, tuple):
        return item
    if isinstance(item, (set, frozenset, list)):
        return tuple(item)
    return (item,)

def _setize(item):
    """ turns an atom into a frozenset with one element,
    and a non-atom into a frozenset"""
    if isinstance(item, frozenset):
        return item
    if isinstance(item, (tuple, set, list)):
        return frozenset(item)
    return frozenset((item,))


def _strip_tablename(colname):
    i=colname.rfind('.')
    if i==-1:
        return colname
    return colname[i+1:]

def getall(modlist):
    all=[]
    for m in modlist:
        try:
            __all__=_import_a_class('%s.__all__' % m)
        except ValueError:
            continue
        else:
            all.extend(__all__)
    return sorted(all)
                             

def _import_a_class(fqcn):
    lastDot=fqcn.rfind('.')   
    if lastDot==0:
        raise ValueError, "unable to import %s" %fqcn
    if lastDot>0:
        modName=fqcn[:lastDot]
        className=fqcn[lastDot+1:]
        try:
            module=__import__(modName, globals(), locals(), [className])
            return getattr(module, className)
        except (ImportError, AttributeError):
            raise ValueError, "impossible to import: %s" % fqcn
    else:
        raise ValueError, "impossible to import: %s" % fqcn


def string_to_obj(s, numframes=0):
    while 1:
        try:
            f=sys._getframe(numframes)
        except ValueError:
            break
        else:
            l=f.f_locals
            g=f.f_globals
            try:
                return l.get(s, g[s])
            except KeyError:
                numframes+=1
               
    return _import_a_class(s)

    
def every(val, iter):
    for i in iter:
        if i != val:
            return False
    return True

def any(val, iter):
    for i in iter:
        if i==val:
            return True
    return False

def iflatten(*l):
    for i in l:
        if isinstance(i, (list, tuple)):
            for i2 in flatten(*i):
                yield i2
        else:
            yield i

def flatten(*l):
    return list(iflatten(*l))

def formatTexp(o, a):
    if o.getTable()==a:
        return a
    return '%s %s' % (o.getTable(), a)


def getuser():
    user=getpass.getuser()
    if user:
        return user
    try:
        from win32api import GetUserName
    except ImportError:
        debug("can't find username, returning empty string")
        return ''
    else:
        return GetUserName()

        
        
def moduleize(module, kls, safe=True):
    """
    This can associate a dynamically created class
    with a module so that it can be pickled properly.
    That doesn't mean it can necessarily be unpickled;
    the code that created and moduleized the class needs
    to run before unpickling can succeed.
    """
    name=kls.__name__
    if hasattr(module, name):
        thing=getattr(module, name)
        if kls is thing:
            # no problem
            return
        elif safe:
            raise ValueError, \
                  "name already in use in module: %s.%s)" \
                  % (module.__name__, name)
    setattr(module, name, kls)
    kls.__module__=module.__name__

    
    
