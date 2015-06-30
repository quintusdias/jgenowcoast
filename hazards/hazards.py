import copy
import datetime as dt
import os
import re
import sys
import warnings

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

_PRODUCT_CLASS = {
    'O':  'Operational product',
    'T':  'Test product',
    'E':  'Experimental product',
    'X':  'Experimental VTEC in Operational product',
}

_ACTION_CODE = {
    'NEW':  'New event',
    'CON':  'Event continued',
    'EXT':  'Event extended (time)',
    'EXA':  'Event extended (area)',
    'EXB':  'Event extended (both time and area)',
    'UPG':  'Event upgraded',
    'CAN':  'Event cancelled',
    'EXP':  'Event expiring',
    'COR':  'Correction',
    'ROU':  'Routine',
}

_SIGNIFICANCE = {
    'W':  'Warning',
    'A':  'Watch',
    'Y':  'Advisory',
    'S':  'Statement',
}

_PHENOMENA = {
    'BZ':  'Blizzard',
    'WS':  'Water Storm',
    'WW':  'Winter Weather',
    'SN':  'Snow',
    'HS':  'Heavy Snow',
    'LE':  'Lake Effect Snow',
    'LB':  'Lake Effect Snow & Blowing Snow',
    'BS':  'Blowing/Drifting Snow',
    'SB':  'Snow & Blowing Snow',
    'IP':  'Sleet',
    'HP':  'Heavy Sleet',
    'ZR':  'Freezing Rain',
    'IS':  'Ice Storm',
    'FZ':  'Freeze',
    'ZF':  'Freezing Fog',
    'FR':  'Frost',
    'WC':  'Wind Chill',
    'EC':  'Extreme Cold',
    'WI':  'Wind',
    'HW':  'High Wind',
    'LW':  'Lake Wind',
    'FG':  'Dense Fog',
    'SM':  'Dense Smoke',
    'HT':  'Heat',
    'EH':  'Excessive Heat',
    'DU':  'Blowing Dust',
    'DS':  'Dust Storm',
    'FL':  'Flood',
    'FF':  'Flash Flood',
    'SV':  'Severe Thunderstorm',
    'TO':  'Tornado',
    'FW':  'Fire Weather (RFW, FWW)',
    'RH':  'Radiological Hazard',
    'VO':  'Volcano',
    'AF':  'Volcanic Ashfall',
    'AS':  'Air Stagnation',
    'AV':  'Avalanche',
    'TS':  'Tsunami',
    'MA':  'Marine',
    'SC':  'Small Craft',
    'GL':  'Gale',
    'SR':  'Storm',
    'HF':  'Hurricane Force Winds',
    'TR':  'Tropical Storm',
    'HU':  'Hurricane',
    'TY':  'Typhoon',
    'TI':  'Inland Tropical Storm Wind',
    'HI':  'Inland Hurricane Wind',
    'LS':  'Lakeshore Flood',
    'CF':  'Coastal Flood',
    'UP':  'Ice Accretion',
    'LO':  'Low Water',
    'SU':  'High Surf',
}


class NoVtecCodeException(Exception):
    pass


class HazardsFile(object):
    """
    Collection of hazard messages.
    """
    def __init__(self, fname):
        """
        Parameters
        ----------
        fname : filename
            File for filename to read.
        """
        self._items = []

        with open(fname, 'rt') as f:
            txt = f.read()

        # Get the base date from the filename.  The format is
        # YYYYMMDDHH.xxxx
        basename = os.path.basename(fname)
        file_base_date = dt.datetime(int(basename[0:4]),
                                     int(basename[4:6]),
                                     int(basename[6:8]),
                                     int(basename[8:10]), 0, 0)

        # Split the text into separate messages.  "$$" seems to be a delimeter
        # that gives us all the messages.  The last item split off is not
        # a valid message, though.
        regex = re.compile(r'''\$\$''')

        items = []
        vtec_codes = []
        for text_item in regex.split(txt)[0:-1]:
            try:
                message = HazardMessage(text_item, file_base_date)
            except NoVtecCodeException:
                # If a hurricane file, just ignore it?
                continue

            if message._vtec_code not in vtec_codes:
                items.append(message)
            vtec_codes.append(message._vtec_code)

        self._items = items

    def __iter__(self):
        """
        Implements iterator protocol.
        """
        return iter(self._items)

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
    base_date : datetime
        Base time as indicated by name of hazards file from whence all this
        information comes.
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

    def __init__(self, txt, base_date):
        """
        Parameters
        ----------
        fname : file or str
            File for filename to read.
        """
        self._message = txt
        self.base_date = base_date
        self.header = None
        self.polygon = []
        self.wkt = None

        self.parse_vtec_code()
        self.parse_hazard_header()
        self.parse_ugc_expiration()
        self.parse_polygon()
        self.create_wkt()

    def __str__(self):

        lst = ['Hazard: {}', 'Product: {}', 'Action: {}', 'Office: {}',
               'Phenomena: {}', 'Significance: {}',
               'Event Tracking Number: {}', 'Beginning Time: {}',
               'Ending Time: {}', 'Well known text: {}']
        fmt = '\n'.join(lst)

        txt = fmt.format(self.header,
                         _PRODUCT_CLASS[self.product],
                         _ACTION_CODE[self.action],
                         self.office_id,
                         _PHENOMENA[self.phenomena],
                         _SIGNIFICANCE[self.significance],
                         self.event_tracking_number,
                         self.beginning_time, self.ending_time,
                         self.wkt)
        return txt

    def parse_ugc_expiration(self):
        """
        Parse the UGC and product expiration time.

        Examples of the UGC line might look like

            PAC007-073-212130-
            GAZ087-088-099>101-114>119-137>141-SCZ040-042>045-047>052-242200-

        """

        # The event can cross states, so that part can consist of one or more
        # codes.
        #
        # The 2nd element can be present or not, and there can be at least as
        # many items as there are states.
        regex = re.compile(r'''(\w{3}(\d{3}((-|>)(\r\n)?))+)+
                               (?P<day>\d{2})
                               (?P<hour>\d{2})
                               (?P<minute>\d{2})-
                            ''', re.VERBOSE)

        m = regex.search(self._message)
        if m is None:
            import ipdb; ipdb.set_trace()
            raise RuntimeError("Could not parse expiration time.")

        self.expiration_time = dt.datetime(self.base_date.year,
                                           self.base_date.month,
                                           int(m.groupdict()['day']),
                                           int(m.groupdict()['hour']),
                                           int(m.groupdict()['minute']), 0)

        assert self.expiration_time > self.base_date

    def parse_vtec_code(self):
        """
        Parse the VTEC string from the message.

        Look for text that looks something like

        /O.CON.KPBZ.SV.W.0094.000000T0000Z-150621T2130Z

        The general format is

        /k.aaa.cccc.pp.s.####.yymmddThhnnZ-yymmddThhnnZ

        where:

            k : project class
            aaa : action code
            cccc : office ID
            pp : phenomenon
            s : significance
            #### : event ID
            yymmddThhnnZ : UTC time

        Parameters
        ----------
        txt : str
            Content of message.
        """
        regex = re.compile(r'''\/
                           (?P<product_class>\w)\.
                           (?P<action_code>\w{3})\.
                           (?P<office_id>\w{4})\.
                           (?P<phenomena>\w{2})\.
                           (?P<significance>\w)\.
                           (?P<event_tracking_number>\d{4})\.
                           (?P<start>\d{6}T\d{4}Z)-
                           (?P<stop>\d{6}T\d{4}Z)
                           ''', re.VERBOSE)

        m = regex.search(self._message)
        if m is None:
            raise NoVtecCodeException()

        idx = slice(m.span()[0], m.span()[1])
        self._vtec_code = self._message[idx]

        self.product = m.groupdict()['product_class']
        self.action = m.groupdict()['action_code']
        self.office_id = m.groupdict()['office_id']
        self.phenomena = m.groupdict()['phenomena']
        self.significance = m.groupdict()['significance']
        evt = int(m.groupdict()['event_tracking_number'])
        self.event_tracking_number = evt

        if m.groupdict()['start'] == '000000T0000Z':
            self.beginning_time = None
        else:
            year = 2000 + int(m.groupdict()['start'][0:2])
            month = int(m.groupdict()['start'][2:4])
            day = int(m.groupdict()['start'][4:6])
            hour = int(m.groupdict()['start'][7:9])
            minute = int(m.groupdict()['start'][9:11])
            the_time = dt.datetime(year, month, day, hour, minute, 0)
            self.beginning_time = the_time

        if m.groupdict()['stop'] == '000000T0000Z':
            self.ending_time = None
        else:
            year = 2000 + int(m.groupdict()['stop'][0:2])
            month = int(m.groupdict()['stop'][2:4])
            day = int(m.groupdict()['stop'][4:6])
            hour = int(m.groupdict()['stop'][7:9])
            minute = int(m.groupdict()['stop'][9:11])
            ending_time = dt.datetime(year, month, day, hour, minute, 0)
            self.ending_time = ending_time

    def create_wkt(self):
        """
        Formulate WKT from the polygon.
        """
        if self.polygon is None:
            self.wkt = None
            return

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
            msg = 'No lat/lon polygon detected for {} advisory'
            warnings.warn(msg.format(_PHENOMENA[self.phenomena]))
            self.polygon = None
            return

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
        regex = re.compile(r'''(\s|\r|\n){2,}
                               \.\.\.
                               (?P<header>[0-9\w\s\./\'-]*?)
                               \.\.\.
                               (\s|\r|\n){2,}''', re.VERBOSE)
        m = regex.search(self._message)
        if m is None:
            import ipdb; ipdb.set_trace()
            raise RuntimeError('Unable to parse hazard summary')
        raw_header = m.groupdict()['header']

        # Replace any sequence of newlines with just a space.
        self.header = re.sub('(\r|\n){2,}', ' ', raw_header)
