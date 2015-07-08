from setuptools import setup
import sys

install_requires = ['numpy>=1.7.1']
if sys.hexversion < 0x03000000:
    install_requires.append('mock>=1.0.1')

kwargs = {'name': 'hazards',
          'description': 'Tools for interrogating NWS hazards messages',
          'version': '0.0.1',
          'install_requires': install_requires,
          'author':  'John Evans',
          'packages': ['hazards']}

setup(**kwargs)
