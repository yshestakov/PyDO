import cPickle
import os
import tempfile
import time

from pydo.utils import getuser

class GuessCache(object):
    """
    a cache that stores pickles of data associated with a Python class.
    """
    def __init__(self, cachedir=None):
        if cachedir is None:
            cachedir=os.path.join(tempfile.gettempdir(),
                                  '_'.join(x for x in (getuser(), 'pydoguesscache') if x))
        self.cachedir=cachedir
        if os.path.exists(cachedir):
            if not os.path.isdir(cachedir):
                raise RuntimeException, "not a directory: %s" % cachedir
            if not os.access(cachedir, os.W_OK | os.R_OK | os.X_OK):
                raise RuntimeException, "cannot access directory: %s" % cachedir
        else:
            os.makedirs(cachedir)


    def pathForObj(self, obj, make=False):
        pathElems=[self.cachedir]+obj.__module__.split('.')
        path=os.path.join(*pathElems)
        if make:
            if not os.path.exists(path):
                os.makedirs(path)
        return os.path.join(path, '%s.cache' % obj.__name__)


    def retrieve(self, obj):
        path=self.pathForObj(obj)
        if os.path.exists(path):
            fp=open(path, 'rb')
            data=cPickle.load(fp)
            fp.close()
            return data
        return None

    def clear(self, obj):
        path=self.pathForObj(obj)
        if os.path.exists(path):
            os.remove(path)

    def store(self, obj, data):
        path=self.pathForObj(obj, True)
        tmppath='%s~%d%d' % (path, os.getpid(), int(time.time()))
        fp=open(tmppath, 'wb')
        cPickle.dump(data, fp, 2)
        fp.close()
        os.rename(tmppath, path)


__all__=['GuessCache']        
        
    
    

