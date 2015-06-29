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
        fname : file or str
            File for filename to read.
        """
        self._items = []

        if os.path.exists(fname):
            with open(fname, 'rt') as f:
                txt = f.read()
        else:
            txt = fname

        # Split the text into separate messages.  "$$" seems to be a delimeter
        # that gives us all the messages.  The last item split off is not
        # a valid message, though.
        regex = re.compile(r'''\$\$''')

	items = []
	vtec_codes = []
        for text_item in regex.split(txt)[0:-1]:
            try:
                message = HazardMessage(text_item)
            except NoVtecCodeException:
                # If a hurricane file, just ignore it?
                pass
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
        self.header = None
        self.polygon = []
        self.wkt = None

        self.parse_vtec_code()
        self.parse_hazard_header()
        self.parse_expiration()
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

    def parse_expiration(self):
        """
        Parse the product expiration time.

        If the P-VTEC string looks something like what's below...

            PAC007-073-212130-
            /O.CON.KPBZ.SV.W.0094.000000T0000Z-150621T2130Z/
            BEAVER PA-LAWRENCE PA-
            503 PM EDT SUN JUN 21 2015

        the product expiration is at 21:30 on the 21st.  The expiration date
        should be parsed after the VTEC code.
        """

        # The event can cross states, so that part can consist of one or more
        # codes.
        #
        # The 2nd element can be present or not, and there can be at least as
        # many items as there are states.
        regex = re.compile(r'''
                            (\w{2}\w\d{3}-)+(\d\d\d-)*
                            (?P<day>\d{2})
                            (?P<hour>\d{2})
                            (?P<minute>\d{2})-
                            ''', re.VERBOSE)
        m = regex.search(self._message)
        if m is None:
            import pdb; pdb.set_trace()
            raise RuntimeError("Could not parse expiration time.")

        # It is possible that either the start or ending time is not specified.
        if self.beginning_time is None:
            reference_time = self.ending_time
        else:
            reference_time = self.beginning_time

        self.expiration_time = dt.datetime(reference_time.year,
                                           reference_time.month,
                                           int(m.groupdict()['day']),
                                           int(m.groupdict()['hour']),
                                           int(m.groupdict()['minute']), 0)


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
            stop_time = dt.datetime(year, month, day, hour, minute, 0)
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
            if self.phenomena == 'TR':
                warnings.warn('No lat/lon polygon detected for tropical storm')
                self.polygon = None
                return
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
        regex = re.compile(r'''(\s|\r|\n){2,}
                               \.\.\.
                               (?P<header>[0-9\w\s\./\']*?)
                               \.\.\.
                               (\s|\r|\n){2,}''', re.VERBOSE)
        m = regex.search(self._message)
        if m is None:
            raise RuntimeError('Unable to parse hazard summary')
        raw_header = m.groupdict()['header']

        # Replace any sequence of newlines with just a space.
        self.header = re.sub('(\r|\n){2,}', ' ', raw_header)

#class Hazards(object):
#    """
#    Attributes
#    ----------
#    hazard_text : str
#        Descriptive text.
#    expires : datetime
#        Time at which the message expires.
#    polygon : list
#        List of lat/lon pairs.
#    wkt : str
#        Well-known text representation of the polygon defining the
#        hazard.
#    """
#
#    def __init__(self, fname):
#        """
#        Parameters
#        ----------
#        fname : file or str
#            File for filename to read.
#        """
#        self.hazard_header = None
#        self.expires = None
#        self.polygon = []
#
#        if os.path.exists(fname):
#            with open(fname, 'rt') as f:
#                txt = f.read()
#        else:
#            txt = fname
#
#        self._parse_hazard_header(txt)
#        if self.hazard_text is None:
#            return
#
#        self._parse_expires(txt)
#        self._parse_issuance_time(txt)
#        self._parse_polygon(txt)
#        self._create_wkt()
#
#    def __str__(self):
#
#        fmt = 'Hazard:  {}\n'
#        fmt += 'Expires:  {}\n'
#        fmt += 'Issued:  {}\n'
#        fmt += 'WKT:  {}'
#
#        txt = fmt.format(self.hazard_text,
#                         self.expires,
#                         self.issuance_time,
#                         self.wkt)
#        return txt
#
#    def _parse_issuance_time(self, txt):
#        """
#        Parse the "Issuance" timestamp from the message.  This is when the
#        warning is issued (?)
#
#        Example:  117 PM EST SAT MAR 3 2012
#
#        Parameters
#        ----------
#        txt : str
#            Content of message.
#        """
#        regex = re.compile(r'''(?P<hourminute>\d{3,4})\s
#                               (?P<am_or_pm>AM|PM)\s
#                               (?P<timezone>\w{3,4})\s
#                               (?P<nameday>\w{3})\s
#                               (?P<namemonth>\w{3})\s
#                               (?P<day>\d{1,2})\s
#                               (?P<year>\d{4})
#                            ''', re.VERBOSE)
#
#        m = regex.search(txt)
#        if m is None:
#            raise RuntimeError('Could not parse issuance time.')
#
#        if len(m.group('hourminute')) == 3:
#            hour = int(m.group('hourminute')[0])
#            minute = int(m.group('hourminute')[1:3])
#        else:
#            hour = int(m.group('hourminute')[0:2])
#            minute = int(m.group('hourminute')[2:4])
#
#        if m.group('am_or_pm') == 'PM':
#            hour += 12
#
#        datestring = '{} {} {:02d} {}:{}:00'.format(m.group('year'),
#                                                    m.group('namemonth'),
#                                                    int(m.group('day')),
#                                                    hour, minute)
#        issuance_time = dt.datetime.strptime(datestring, '%Y %b %d %H:%M:%S')
#        delta = dt.timedelta(hours=_TIMEZONES[m.group('timezone')])
#        self.issuance_time = issuance_time - delta
#
#    def _parse_expires(self, txt):
#        """
#        Parse the "Expires" timestamp from the message.
#
#        Parameters
#        ----------
#        txt : str
#            Content of message.
#        """
#        # Expires is only one the first line.
#        line = txt.split('\n')[0]
#
#        # 12 digit date
#        regex = re.compile(r'''Expires:(?P<expires>\d{12});
#                               Remove:(?P<remove>\d{12});''', re.VERBOSE)
#        m = regex.match(line)
#        if m is None:
#            raise RuntimeError("Could not parse Expires timestamp.")
#
#        year = int(m.group('expires')[0:4])
#        month = int(m.group('expires')[4:6])
#        day = int(m.group('expires')[6:8])
#        hour = int(m.group('expires')[8:10])
#        minute = int(m.group('expires')[10:])
#
#        self.expires = dt.datetime(year, month, day, hour, minute, 0)
#
#    def _create_wkt(self):
#        """
#        Formulate WKT from the polygon.
#        """
#        # Must include the first point as the last point.
#        lst = copy.deepcopy(self.polygon)
#        lst.append(lst[0])
#
#        # Build up the inner (and only) ring.
#        txt = '{} {}'.format(lst[0][0], lst[0][1])
#        for tuple in lst[1:]:
#            txt = txt + ', {} {}'.format(tuple[0], tuple[1])
#
#        self.wkt = 'POLYGON(({}))'.format(txt)
#
#    def _parse_polygon(self, txt):
#        """
#        Parse the lat/lon polygon from the message.
#
#        Parameters
#        ----------
#        txt : str
#            Content of message.
#        """
#        regex = re.compile(r"""LAT...LON(?P<latlon>(\s+\d{4}){2,})\s
#                               """, re.VERBOSE)
#        m = regex.search(txt)
#        if m is None:
#            raise RuntimeError('Failed')
#
#        latlon_txt = m.group('latlon').replace('\n', ' ')
#        nums = np.genfromtxt(StringIO(unicode(latlon_txt)))
#        lats = [float(x)/100.0 for x in nums[0::2]]
#        lons = [float(x)/100.0 for x in nums[1::2]]
#
#        self.polygon = zip(lons, lats)
#
#    def _parse_hazard_header(self, txt):
#        """
#        Parameters
#        ----------
#        txt : str
#            Content of message.
#        """
#
#        # Any hazards?  Look for two consecutive lines ending with "..."
#        hazard_possibly_found = False
#        lst = txt.split('\n')
#        for idx, line in enumerate(lst):
#            if line.endswith('...'):
#                hazard_possibly_found = True
#                break
#        if hazard_possibly_found:
#            if not lst[idx + 1].endswith('...'):
#                # No hazard found.  We're done.
#                return
#            else:
#                hazard_lines = []
#                for line in lst[idx:]:
#                    if not line.endswith('...'):
#                        break
#                    hazard_lines.append(line)
#        hazard_text = ''.join(hazard_lines)
#        hazard_text = re.sub('^\*\s', '', hazard_text)
#        hazard_text = re.sub('\.\.\.', '', hazard_text)
#        hazard_text = re.sub('\s\s', ' ', hazard_text)
#        self.hazard_text = hazard_text
#
