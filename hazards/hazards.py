import copy
import datetime as dt
import os
import re
import sys

if sys.hexversion < 0x030000:
    from StringIO import StringIO
else:
    from io import StringIO

import numpy as np


# Dictionary of time zone abbreviations (keys) and their UTC offsets (values)
_TIMEZONES = {
    "AST": -4,
    "EST": -5,
    "EDT": -4,
    "CST": -6,
    "CDT": -5,
    "MST": -7,
    "MDT": -6,
    "PST": -8,
    "PDT": -7,
    "AKST": -9,
    "AKDT": -8,
    "HST": -10,
    "HAST": -10,
    "HADT": -9,
    "SST": -11,
    "SDT": -10,
    "CHST": 10
}


class Hazards(object):
    """
    Attributes
    ----------
    hazard_text : str
        Descriptive text.
    expires : datetime
        Time at which the message expires.
    polygon : list
        List of lat/lon pairs.
    wkt : str
        Well-known text representation of the polygon defining the
        hazard.
    """

    def __init__(self, fname):
        """
        Parameters
        ----------
        fname : file or str
            File for filename to read.
        """
        self.hazard_header = None
        self.expires = None
        self.polygon = []

        if os.path.exists(fname):
            with open(fname, 'rt') as f:
                txt = f.read()
        else:
            txt = fname

        self._parse_hazard_header(txt)
        if self.hazard_text is None:
            return

        self._parse_expires(txt)
        self._parse_issuance_time(txt)
        self._parse_polygon(txt)
        self._create_wkt()

    def __str__(self):

        fmt = 'Hazard:  {}\n'
        fmt += 'Expires:  {}\n'
        fmt += 'Issued:  {}\n'
        fmt += 'WKT:  {}'

        txt = fmt.format(self.hazard_text,
                         self.expires,
                         self.issuance_time,
                         self.wkt)
        return txt

    def _parse_issuance_time(self, txt):
        """
        Parse the "Issuance" timestamp from the message.  This is when the
        warning is issued (?)

        Example:  117 PM EST SAT MAR 3 2012

        Parameters
        ----------
        txt : str
            Content of message.
        """
        regex = re.compile(r'''(?P<hourminute>\d{3,4})\s
                               (?P<am_or_pm>AM|PM)\s
                               (?P<timezone>\w{3,4})\s
                               (?P<nameday>\w{3})\s
                               (?P<namemonth>\w{3})\s
                               (?P<day>\d{1,2})\s
                               (?P<year>\d{4})
                            ''', re.VERBOSE)

        m = regex.search(txt)
        if m is None:
            raise RuntimeError('Could not parse issuance time.')

        if len(m.group('hourminute')) == 3:
            hour = int(m.group('hourminute')[0])
            minute = int(m.group('hourminute')[1:3])
        else:
            hour = int(m.group('hourminute')[0:2])
            minute = int(m.group('hourminute')[2:4])

        if m.group('am_or_pm') == 'PM':
            hour += 12

        datestring = '{} {} {:02d} {}:{}:00'.format(m.group('year'),
                                                    m.group('namemonth'),
                                                    int(m.group('day')),
                                                    hour, minute)
        issuance_time = dt.datetime.strptime(datestring, '%Y %b %d %H:%M:%S')
        delta = dt.timedelta(hours=_TIMEZONES[m.group('timezone')])
        self.issuance_time = issuance_time - delta

    def _parse_expires(self, txt):
        """
        Parse the "Expires" timestamp from the message.

        Parameters
        ----------
        txt : str
            Content of message.
        """
        # Expires is only one the first line.
        line = txt.split('\n')[0]

        # 12 digit date
        regex = re.compile(r'''Expires:(?P<expires>\d{12});
                               Remove:(?P<remove>\d{12});''', re.VERBOSE)
        m = regex.match(line)
        if m is None:
            raise RuntimeError("Could not parse Expires timestamp.")

        year = int(m.group('expires')[0:4])
        month = int(m.group('expires')[4:6])
        day = int(m.group('expires')[6:8])
        hour = int(m.group('expires')[8:10])
        minute = int(m.group('expires')[10:])

        self.expires = dt.datetime(year, month, day, hour, minute, 0)

    def _create_wkt(self):
        """
        Formulate WKT from the polygon.
        """
        # Must include the first point as the last point.
        lst = copy.deepcopy(self.polygon)
        lst.append(lst[0])

        # Build up the inner (and only) ring.
        txt = '{} {}'.format(lst[0][0], lst[0][1])
        for tuple in lst[1:]:
            txt = txt + ', {} {}'.format(tuple[0], tuple[1])

        self.wkt = 'POLYGON(({}))'.format(txt)

    def _parse_polygon(self, txt):
        """
        Parse the lat/lon polygon from the message.

        Parameters
        ----------
        txt : str
            Content of message.
        """
        regex = re.compile(r"""LAT...LON(?P<latlon>(\s+\d{4}){2,})\s
                               """, re.VERBOSE)
        m = regex.search(txt)
        if m is None:
            raise RuntimeError('Failed')

        latlon_txt = m.group('latlon').replace('\n', ' ')
        nums = np.genfromtxt(StringIO(unicode(latlon_txt)))
        lats = [float(x)/100.0 for x in nums[0::2]]
        lons = [float(x)/100.0 for x in nums[1::2]]

        self.polygon = zip(lons, lats)

    def _parse_hazard_header(self, txt):
        """
        Parameters
        ----------
        txt : str
            Content of message.
        """

        # Any hazards?  Look for two consecutive lines ending with "..."
        hazard_possibly_found = False
        lst = txt.split('\n')
        for idx, line in enumerate(lst):
            if line.endswith('...'):
                hazard_possibly_found = True
                break
        if hazard_possibly_found:
            if not lst[idx + 1].endswith('...'):
                # No hazard found.  We're done.
                return
            else:
                hazard_lines = []
                for line in lst[idx:]:
                    if not line.endswith('...'):
                        break
                    hazard_lines.append(line)
        hazard_text = ''.join(hazard_lines)
        hazard_text = re.sub('^\*\s', '', hazard_text)
        hazard_text = re.sub('\.\.\.', '', hazard_text)
        hazard_text = re.sub('\s\s', ' ', hazard_text)
        self.hazard_text = hazard_text
