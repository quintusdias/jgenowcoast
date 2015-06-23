from setuptools import setup

kwargs = {'name': 'hazards',
          'description': 'Tools for interrogating NWS hazards messages',
          'version': '0.0.1',
          'install_requires': ['numpy>=1.7.1'],
          'author':  'John Evans',
          'packages': ['hazards']}

setup(**kwargs)
