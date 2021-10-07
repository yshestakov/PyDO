"""
tests for the pydo.guesscache module.
"""

from testingtesting import tag
import config
import pydo as P

alltags=list(config.ALLDRIVERS) + ['guesscache']

# random object to use as a key
#from http.client import HTTPConnection
class HTTPConnection(object):
    def __init__(self):
        self.foo = 'bar'

@tag(*alltags)
def test_guesscache1():
    cache=P.GuessCache()
    cache.store(HTTPConnection, list(range(4)))
    assert cache.retrieve(HTTPConnection)==list(range(4))
    cache.clear(HTTPConnection)
    assert cache.retrieve(HTTPConnection) is None
