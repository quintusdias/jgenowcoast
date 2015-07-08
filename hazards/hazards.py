import copy
import datetime as dt
import itertools
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

_VTEC_PRODUCT_CLASS = {
    'O':  'Operational product',
    'T':  'Test product',
    'E':  'Experimental product',
    'X':  'Experimental VTEC in Operational product',
}

_VTEC_ACTION_CODE = {
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

_VTEC_SIGNIFICANCE = {
    'W':  'Warning',
    'A':  'Watch',
    'Y':  'Advisory',
    'S':  'Statement',
}

_VTEC_PHENOMENA = {
    'AF':  'Volcanic Ashfall',
    'AS':  'Air Stagnation',
    'AV':  'Avalanche',
    'BS':  'Blowing/Drifting Snow',
    'BZ':  'Blizzard',
    'CF':  'Coastal Flood',
    'DS':  'Dust Storm',
    'DU':  'Blowing Dust',
    'EC':  'Extreme Cold',
    'EH':  'Excessive Heat',
    'FA':  'Areal Flood',
    'FF':  'Flash Flood',
    'FG':  'Dense Fog',
    'FL':  'Flood',
    'FR':  'Frost',
    'FW':  'Fire Weather (RFW, FWW)',
    'FZ':  'Freeze',
    'GL':  'Gale',
    'HF':  'Hurricane Force Winds',
    'HI':  'Inland Hurricane Wind',
    'HP':  'Heavy Sleet',
    'HS':  'Heavy Snow',
    'HT':  'Heat',
    'HU':  'Hurricane',
    'HW':  'High Wind',
    'IP':  'Sleet',
    'IS':  'Ice Storm',
    'LB':  'Lake Effect Snow & Blowing Snow',
    'LE':  'Lake Effect Snow',
    'LO':  'Low Water',
    'LS':  'Lakeshore Flood',
    'LW':  'Lake Wind',
    'MA':  'Marine',
    'RH':  'Radiological Hazard',
    'SB':  'Snow & Blowing Snow',
    'SC':  'Small Craft',
    'SM':  'Dense Smoke',
    'SN':  'Snow',
    'SR':  'Storm',
    'SU':  'High Surf',
    'SV':  'Severe Thunderstorm',
    'TI':  'Inland Tropical Storm Wind',
    'TO':  'Tornado',
    'TR':  'Tropical Storm',
    'TS':  'Tsunami',
    'TY':  'Typhoon',
    'UP':  'Ice Accretion',
    'VO':  'Volcano',
    'WC':  'Wind Chill',
    'WI':  'Wind',
    'WS':  'Water Storm',
    'WW':  'Winter Weather',
    'ZF':  'Freezing Fog',
    'ZR':  'Freezing Rain',
}

# The general format is
#
# /k.aaa.cccc.pp.s.####.yymmddThhnnZ-yymmddThhnnZ
#
# where:
#
# k : project class
# aaa : action code
# cccc : office ID
# pp : phenomenon
# s : significance
# #### : event ID
# yymmddThhnnZ : UTC time
vtec_pattern = r'''\/
                   (?P<product_class>\w)\.
                   (?P<action_code>\w{3})\.
                   (?P<office_id>\w{4})\.
                   (?P<phenomena>\w{2})\.
                   (?P<significance>\w)\.
                   (?P<event_tracking_id>\d{4})\.
                   (?P<start>\d{6}T\d{4}Z)-
                   (?P<stop>\d{6}T\d{4}Z)
                 '''
vtec_regex = re.compile(vtec_pattern, re.VERBOSE)


class VtecCode(object):
    """
    Attributes
    -----------
    code : str
        Original VTEC code, i.e. something like
        "O.CON.KILM.TR.A.1001.000000T0000Z-000000T0000Z"
    event_beginning_time, event_ending_time : date time objects
        Event beginning and ending times
    product : str
        1-character code tells whether the product is test, experimental, or
        operational
    action : str
        3-character code describes the action being taken with this product
        issuance.  The first time any VTEC event is included, it starts
        as a NEW.   The other action codes are used in followup products,
        except for the last one in the list, ROU (for routine).
    office_id : str
        4-character code identifying the origin of the bulletin
    phenomena : str
        two-character code describes the specific meteorological or hydrologic
        phenomenon included in the product or product segment.  As you
        can see, there is a large list of phenomena codes, and as needs
        arise additional ones will be added to the list.
    significance : str
        This single character, when combined with the phenomenon code,
        describes a specific VTEC event.  For example, a Winter Storm
        Watch would have a Phenomenon code of WS and a Significance code
        of A, while a Winter Storm Warning would have a Phenomenon code
        of WS and a Significance code of W.
    event_tracking_id : int
        Assigned in sequence by a WFO for a phenomena.
    """
    def __init__(self, match):
        """
        Parameters
        ----------
        match : regular expression match object
            Matches vtec code
        """
        self.code = match.group()

        gd = match.groupdict()
        if gd['start'] == '000000T0000Z':
            self.event_beginning_time = None
        else:
            year = 2000 + int(gd['start'][0:2])
            month = int(gd['start'][2:4])
            day = int(gd['start'][4:6])
            hour = int(gd['start'][7:9])
            minute = int(gd['start'][9:11])
            the_time = dt.datetime(year, month, day, hour, minute, 0)
            self.event_beginning_time = the_time

        if gd['stop'] == '000000T0000Z':
            self.event_ending_time = None
        else:
            year = 2000 + int(gd['stop'][0:2])
            month = int(gd['stop'][2:4])
            day = int(gd['stop'][4:6])
            hour = int(gd['stop'][7:9])
            minute = int(gd['stop'][9:11])
            ending_time = dt.datetime(year, month, day, hour, minute, 0)
            self.event_ending_time = ending_time

        self.product = gd['product_class']
        self.action = gd['action_code']
        self.office_id = gd['office_id']
        self.phenomena = gd['phenomena']
        self.significance = gd['significance']
        self.event_tracking_id = int(gd['event_tracking_id'])


class NoVtecCodeException(Exception):
    def __init__(self, message):
        self.message = message


def fetch_events(dirname, numlast=None, current=None):
    """
    Parameters
    ----------
    dirname : str
        Directory of hazard bulletin files
    numlast : int
        Only take this many "most recent" files
    current : bool
        If True, keep only current events, that is, events that have not
        expired
    """
    lst = os.listdir(dirname)
    if numlast is None:
        fnames = [os.path.join(dirname, item) for item in lst]
    else:
        fnames = [os.path.join(dirname, item) for item in lst[numlast:]]
    hzlst = [HazardsFile(fname) for fname in fnames]

    events = []
    for hazard_file in hzlst:
        for bulletin in hazard_file:
            for j, vtec_code in enumerate(bulletin.vtec):
                gen = itertools.ifilter(lambda x: x.contains(vtec_code), events)
                evts = list(gen)
                if len(evts) == 0:
                    # Must create a new event.
                    events.append(Event(vtec_code, bulletin))
                else:
                    # The event already exists.  Just add this bulletin to the
                    # sequence of events.
                    assert len(evts) == 1
                    evt = evts[0]
                    evt.append(bulletin)

    if current is not None and current:
        events = [event for event in events if event.current()]

    return events


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
        self.filename = fname
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
        bulletins_already_seen = []
        for text_item in regex.split(txt)[0:-1]:
            try:
                bltn = Bulletin(text_item, file_base_date)
            except NoVtecCodeException:
                # If a hurricane file, just ignore it?
                continue

            # Is this a repeat of the last message?
            if bltn.id in bulletins_already_seen:
                continue

            bulletins_already_seen.append(bltn.id)
            items.append(bltn)

        self._items = items

    def __str__(self):
        return "Filename:  {}".format(self.filename)

    def __iter__(self):
        """
        Implements iterator protocol.
        """
        return iter(self._items)

    def __len__(self):
        """
        Implements built-in len(), returns number of Bulletin objects.
        """
        return len(self._items)

    def __getitem__(self, idx):
        """
        Implement index lookup.
        """
        if idx >= len(self):
            raise KeyError(str(idx))

        return self._items[idx]


class Bulletin(object):
    """
    Attributes
    ----------
    base_date : datetime
        Base time as indicated by name of hazards file from whence all this
        information comes
    header : str
        Descriptive text
    expiration_time : datetime
        Time at which the product (not the event) expires
    polygon : list
        List of lat/lon pairs
    ugc_format : str
        Either 'county' or 'zone'
    state : dictionary
        The keys consist of FIPS codes, the values consist of a list of
        counties or zones.
    wkt : str
        Well-known text representation of the polygon defining the
        hazard
    """

    def __init__(self, txt, base_date):
        """
        Parameters
        ----------
        txt : str
            Text constituting the entire bulletin
        base_date : datetime.datetime
            Date attached to the file from whence this bulletin came.
        """
        self._message = txt
        self.base_date = base_date
        self.header = None
        self.polygon = []
        self.wkt = None

        self.parse_vtec_code()
        self.parse_hazard_header()
        self.parse_universal_geographic_code()
        self.parse_polygon()
        self.create_wkt()

    def __str__(self):

        # First formulate strings for all the VTEC codes.  Usually, but not
        # always, there is just one.
        lst = ['Product: {}', 'Action: {}', 'Office: {}', 'Phenomena: {}',
               'Significance: {}', 'Event Tracking Number: {}',
               'Beginning Time: {}', 'Ending Time: {}']
        fmt = '\n'.join(lst)

        vtec_strs = []
        for vtec_code in self.vtec:
            txt = fmt.format(_VTEC_PRODUCT_CLASS[vtec_code.product],
                             _VTEC_ACTION_CODE[vtec_code.action],
                             vtec_code.office_id,
                             _VTEC_PHENOMENA[vtec_code.phenomena],
                             _VTEC_SIGNIFICANCE[vtec_code.significance],
                             vtec_code.event_tracking_id,
                             vtec_code.event_beginning_time,
                             vtec_code.event_ending_time)
            vtec_strs.append(txt)

        if len(vtec_strs) > 1:
            vtec_strs.insert(0, '')
            vtec_strs.append('')
        all_vtecs = '\n=====\n'.join(vtec_strs)

        # Now formulate the main informal string representation by adding the
        # header to the top, and the expiration time and wkt to the bottom.
        lst = ['Hazard: {}', '{}', 'Expiration Time: {}',
               'Well Known Text: {}']
        fmt = '\n'.join(lst)
        txt = fmt.format(self.header, all_vtecs, self.expiration_time,
                         self.wkt)

        return txt

    def parse_universal_geographic_code(self):
        """
        Parse the UGC and product expiration time.

        Examples of the UGC line might look like

            PAC007-073-212130-
            GAZ087-088-099>101-114>119-137>141-SCZ040-042>045-047>052-242200-

        Reference
        ---------
        [1] http://www.nws.noaa.gov/directives/sym/pd01017002curr.pdf
        """

        # The event can cross states, so that part can consist of one or more
        # codes.
        #
        # The 2nd element can be present or not, and there can be at least as
        # many items as there are states.
        regex = re.compile(r'''(\w{2}[CZ](\d{3}((-|>)(\r\n)?))+)+
                               (?P<day>\d{2})
                               (?P<hour>\d{2})
                               (?P<minute>\d{2})-
                            ''', re.VERBOSE)

        m = regex.search(self._message)
        if m is None:
            raise RuntimeError("Could not parse expiration time.")

        self._parse_ugc_expiration_date(m.groupdict())
        self._parse_ugc_geography(m.group())

    def _parse_ugc_geography(self, txt):
        """
        Now parse the geographic information.

        The UGC takes the form

            SSFNNN-NNN>NNN-SSFNNN-DDHHMM-

        So capture the 2-char FIPS code, the single char format code,
        and then an indeterminite number of county/zone codes.  Wash, rinse,
        repeat.

        Parameters
        ----------
        txt : str
            UGC string
        """
        # Must match:
        #
        #    1) the two-char FIPS code (state), the single
        #    2) a single-char county or zone code
        #    3) a sequence of numbers and separators identifying the
        #       counties/zones
        #
        ugc_regex = re.compile(r'''(?P<fips>\w{2})
                                   (?P<format>[CZ])
                                   (?:\d{3}((-|>)(\r\n)?))+
                                ''', re.VERBOSE)

        # Within the sequence of counties/zones, must match at least one
        # 3-digit code for a county or zone, but possibly an entire range
        # of zones.  If the separator is '>', that means a range of zones.
        cty_regex = re.compile(r'''(\d{3})(-|>\d{3}-)''', re.VERBOSE)

        states = {}
        for m in ugc_regex.finditer(txt):
            state = m.groupdict()['fips']
            format = m.groupdict()['format']

            codes = []
            for item in cty_regex.findall(m.group()):
                if item[1] == '-':
                    # single county or zone
                    codes.append(int(item[0]))
                else:
                    # multiple zones
                    # The matched string was something like "114>117-"
                    # which means that zones 114, 115, 116, and 117 were
                    # intended.  Can never have a range of counties.
                    for code in range(int(item[0]), int(item[1][1:4]) + 1):
                        codes.append(code)
            states[state] = codes

        self.states = states
        self.ugc_format = 'county' if format == 'C' else 'zone'

    def _parse_ugc_expiration_date(self, gd):
        """
        Construct the expiration date from the UGC.

        Parameters
        -----------
        gd : regular expression match object dictionary
            Has day, hour, minute fields.  The year and month need to be
            inferred.
        """
        exp_day = int(gd['day'])
        exp_hour = int(gd['hour'])
        exp_minute = int(gd['minute'])
        if exp_day < self.base_date.day:
            if self.base_date.month == 12:
                # Beginning of next year
                year = self.base_date.year + 1
                self.expiration_time = dt.datetime(year, 1,
                                                   exp_day, exp_hour,
                                                   exp_minute, 0)
            else:
                # Beginning of next month
                year = self.base_date.year
                month = self.base_date.month + 1
                self.expiration_time = dt.datetime(year, month,
                                                   exp_day, exp_hour,
                                                   exp_minute, 0)
        else:
            self.expiration_time = dt.datetime(self.base_date.year,
                                               self.base_date.month,
                                               exp_day, exp_hour,
                                               exp_minute, 0)

        assert self.expiration_time > self.base_date

    def parse_vtec_code(self):
        """
        Parse the VTEC string from the message.

        Look for text that looks something like

        /O.CON.KPBZ.SV.W.0094.000000T0000Z-150621T2130Z

        There can be more than one.

        Parameters
        ----------
        txt : str
            Content of message.
        """
        self.vtec = []

        _codes = []

        for m in vtec_regex.finditer(self._message):
            the_vtec_code = m.group()
            _codes.append(the_vtec_code)
            self.vtec.append(VtecCode(m))

        if len(self.vtec) == 0:
            msg = "No VTEC codes detected"
            raise NoVtecCodeException(msg)

        self._id = hash(''.join(_codes))

    @property
    def id(self):
        """
        Return unique identifier based upon the vtec codes
        """
        return self._id

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
            warnings.warn('No lat/lon polygon detected.')
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
        if m is not None:
            raw_header = m.groupdict()['header']

            # Replace any sequence of newlines with just a space.
            self.header = re.sub('(\r|\n){2,}', ' ', raw_header)
            return

        if self.vtec[0].phenomena in ['FA', 'FF', 'FL', 'SV', 'TO']:
            # Tornado warning
            # These headers do not seem to have leading and trailing "..."
            # sentinals around the header.
            #
            # Split the message by paragraphs, take all those following the
            # VTEC code stanza.
            lst = re.split(r'''(?:\r\n){2,}''', self._message)
            header_lst = []
            past_vtec = False
            for stanza in lst:

                if past_vtec:
                    if '&&' in stanza:
                        break
                    header_lst.append(stanza)
                    continue

                if vtec_regex.search(stanza) is not None:
                    past_vtec = True
                    continue

            self.header = '\n\n'.join(header_lst)
            self.header = self.header.replace('\r\n', '\n')
            return

        msg = 'Unable to parse hazard summary, phenomena = {}'
        msg = msg.format(self.vtec[0].phenomena)
        raise RuntimeError(msg)


class Event(HazardsFile):
    """
    """
    def __init__(self, vtec_code, bulletin):
        self.vtec_code = vtec_code
        my_bulletin = copy.deepcopy(bulletin)
        if len(bulletin.vtec) > 1:
            my_bulletin.vtec = [vtec_code]

        self._items = [my_bulletin]

    def __str__(self):
        lst = []
        for bulletin in self._items:
            lst.append(str(bulletin))
        return '\n'.join(lst)

    def contains(self, vtec_code):
        if (((self._items[0].vtec[0].product == vtec_code.product) and
             (self._items[0].vtec[0].office_id == vtec_code.office_id) and
             (self._items[0].vtec[0].phenomena == vtec_code.phenomena) and
             (self._items[0].vtec[0].event_tracking_id == vtec_code.event_tracking_id))):
            return True
        else:
            return False

    def append(self, bulletin):
        self._items.append(bulletin)

    def current(self):
        """
        Is this event still in progress?
        """
        if self._items[-1].vtec[0].action != 'EXP':
            return True
        else:
            return False

    def __iter__(self):
        """
        Implements iterator protocol.
        """
        return iter(self._items)

    def __len__(self):
        """
        Implements built-in len(), returns number of bulletins
        """
        return len(self._items)

    def __getitem__(self, idx):
        """
        Implement index lookup.
        """
        if idx >= len(self):
            raise KeyError(str(idx))

        return self._items[idx]
