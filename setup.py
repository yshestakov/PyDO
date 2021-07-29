import ez_setup
ez_setup.use_setuptools()

from setuptools import setup

import sys
sys.path.insert(0, 'src')
from pydo import __version__ as version
description='a Python ORM supporting many RDBMS backends'
long_description="""
PyDO is a ORM (Object-Relational Mapper) database access library for
Python that facilitates writing a Python database access layer.  PyDO
attempts to be simple, flexible, extensible, and unconstraining.
""".strip()

platforms="OS Independent"

keywords=['ORM',
          'database',
          'SkunkWeb']
classifiers=[x for x in (line.strip() for line in  open('CLASSIFIERS')) \
             if x and not x.startswith('#')]

setup(author='Drew Csillag',
      author_email='drew_csillag@yahoo.com',
      maintainer='Jacob Smullyan',
      maintainer_email='smulloni@smullyan.org',
      description=description,
      long_description=long_description,
      classifiers=classifiers,
      keywords=keywords,
      platforms=platforms,
      license='GPL/BSD',
      name='PyDO',
      url='http://skunkweb.org/pydo2.html',
      version=version,
      zip_safe=True,
      packages=['pydo', 'pydo.drivers'],
      package_dir={'' : 'src'})
