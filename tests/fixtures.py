"""
Fixtures for hazards testing.
"""

import os
import pkg_resources as pkg

relpath = os.path.join('data', 'severe', '2015062121.severe')
severe_thunderstorm_file = pkg.resource_filename(__name__, relpath)
