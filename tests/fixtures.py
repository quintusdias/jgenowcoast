"""
Fixtures for hazards testing.
"""

import os
import pkg_resources as pkg

relpath = os.path.join('data', 'severe', '2015062121.severe')
severe_thunderstorm_file = pkg.resource_filename(__name__, relpath)

tstorm_warning_txt = r"""Hazard: A SEVERE THUNDERSTORM WARNING REMAINS IN EFFECT UNTIL 530 PM EDT FOR NORTHEASTERN BEAVER AND SOUTH CENTRAL LAWRENCE COUNTIES
Product: Operational product
Action: Event continued
Office: KPBZ
Phenomena: Severe Thunderstorm
Significance: Warning
Event Tracking Number: 94
Beginning Time: None
Ending Time: 2015-06-21 21:30:00
Well known text: POLYGON((80.43 40.84, 80.32 40.89, 80.16 40.83, 80.15 40.69, 80.43 40.84))"""
