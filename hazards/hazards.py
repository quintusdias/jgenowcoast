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


class HazardsFile(object):
    """
    """
    def __init__(self, fname):
        """
        Parameters
        ----------
        fname : file or str
            File for filename to read.
        """
        self._items = []

        if os.path.exists(fname):
            with open(fname, 'rt') as f:
                txt = f.read()
        else:
            txt = fname

        # Split the text into separate messages.
        # Use lookahead to preserve information.
        # The first item split off is not a "message".
        regex = re.compile(r'''\d{3}\s+(?=WWUS\d\d)''')
        for message in regex.split(txt)[1:]:
            self._items.append(HazardMessage(message))

    def __len__(self):
        """
        Implements built-in len(), returns number of HazardMessage objects.
        """
        return len(self._items)

    def __getitem__(self, idx):
        """
        Implement index lookup.
        """
        if idx >= len(self):
            raise KeyError(str(idx))

        return self._items[idx]


class HazardMessage(object):
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

    def __init__(self, txt):
        """
        Parameters
        ----------
        fname : file or str
            File for filename to read.
        """
        self._message = txt
        self.hazard_header = None
        self.expires = None
        self.issuance_time = None
        self.polygon = []
        self.wkt = None

        self.parse_hazard_header()
        self.parse_time()
        self.parse_polygon()
        self.create_wkt()

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

    def parse_time(self):
        """
        Parse the timestamps from the message.

        Look for text that looks something like 

        /O.CON.KPBZ.SV.W.0094.000000T0000Z-150621T2130Z

        Parameters
        ----------
        txt : str
            Content of message.
        """
        regex = re.compile(r'''\/O\.\w{3}\.\w{4}\.SV\.\w\.\d{4}\.
                               (?P<start>\d{6}T\d{4}Z)-
                               (?P<stop>\d{6}T\d{4}Z)''', re.VERBOSE)

        m = regex.search(self._message)

        if m.groupdict()['start'] == '000000T0000Z':
            self.start_time = None
        else:
            year = 2000 + int(m.groupdict()['start'][0:2])
            month = int(m.groupdict()['start'][2:4])
            day = int(m.groupdict()['start'][4:6])
            hour = int(m.groupdict()['start'][7:9])
            minute = int(m.groupdict()['start'][9:11])
            self.start_time = dt.datetime(year, month, day, hour, minute, 0)

        year = 2000 + int(m.groupdict()['stop'][0:2])
        month = int(m.groupdict()['stop'][2:4])
        day = int(m.groupdict()['stop'][4:6])
        hour = int(m.groupdict()['stop'][7:9])
        minute = int(m.groupdict()['stop'][9:11])
        stop_time = dt.datetime(year, month, day, hour, minute, 0)

        self.stop_time = dt.datetime(year, month, day, hour, minute, 0)

    def create_wkt(self):
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

    def parse_polygon(self):
        """
        Parse the lat/lon polygon from the message.

        The section of text might look as follows:

        LAT...LON 4862 10197 4828 10190 4827 10223 4851 10259
              4870 10238
        TIME...MOT...LOC 2108Z 303DEG 38KT 4851 10225

        Parameters
        ----------
        txt : str
            Content of message.
        """

        # Use lookahead to match the polyon only if followed by "TIME"
        regex = re.compile(r"""LAT...LON\s
                               (?P<latlon>[\s\r\n\d{4,5}]*?)
                               (?=TIME)""", re.VERBOSE)
        m = regex.search(self._message)
        if m is None:
            raise RuntimeError('Failed')

        latlon_txt = m.group('latlon').replace('\n', ' ')
        nums = np.genfromtxt(StringIO(unicode(latlon_txt)))
        lats = [float(x)/100.0 for x in nums[0::2]]
        lons = [float(x)/100.0 for x in nums[1::2]]

        self.polygon = zip(lons, lats)

    def parse_hazard_header(self):
        """
        Parameters
        ----------
        txt : str
            Text of severe weather message.
        """
        # At least two newlines followed by "..." and the message.
        # The message can contain the "..." pattern, but the end of the
        # message must be terminated by "..." followed by at least two
        # end-of-line characters.
        regex = re.compile(r'''(\r\n|\r|\n){2,}
                               \.\.\.
                               (?P<header>[0-9\w\s\./]*?)
                               \.\.\.
                               (\r\n|\r|\n){2,}''', re.VERBOSE)
        m = regex.search(self._message)
        raw_header = m.groupdict()['header']

        # Replace any sequence of newlines with just a space.
        self.header = re.sub('(\r|\n){2,}', ' ', raw_header)

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

