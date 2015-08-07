from setuptools import setup
import sys

install_requires = ['gdal>=1.10.0', 'numpy>=1.7.1']
if sys.hexversion < 0x03000000:
    install_requires.append('mock>=1.0.1')

kwargs = {'name': 'hazards',
          'author':  'John Evans',
          'description': 'Tools for interrogating NWS hazards messages',
          'entry_points':  {
              'console_scripts': ['hzparse=hazards.command_line:hzparse'],
          },
          'install_requires': install_requires,
          'packages': ['hazards'],
          'version': '0.0.2',}

setup(**kwargs)
