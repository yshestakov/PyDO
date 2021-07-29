"""
tests for the pydo.guesscache module.
"""

from testingtesting import tag
import config
import pydo as P

alltags=config.ALLDRIVERS + ['guesscache']

# random object to use as a key
from httplib import HTTPConnection

@tag(*alltags)
def test_guesscache1():
    cache=P.GuessCache()
    cache.store(HTTPConnection, range(4))
    assert cache.retrieve(HTTPConnection)==range(4)
    cache.clear(HTTPConnection)
    assert cache.retrieve(HTTPConnection) is None
