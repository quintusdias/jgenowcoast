"""
References
----------
[1] National Weather Service Instruction 10-1702, November 11, 2010, Operations
and Services, Dissemination Services NWSPD 10-17, Universal Geographic CODE
(UGC), http://www.nws.noaa.gov/directives/sym/pd01017002curr.pdf
"""

import collections
import copy
import datetime as dt
import os
import re
import sys
if sys.hexversion < 0x03000000:
    from StringIO import StringIO
else:
    from io import BytesIO

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

_MONTH = {
    'JAN': 1,
    'FEB': 2,
    'MAR': 3,
    'APR': 4,
    'MAY': 5,
    'JUN': 6,
    'JUL': 7,
    'AUG': 8,
    'SEP': 9,
    'OCT': 10,
    'NOV': 11,
    'DEC': 12
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


TimeMotionLocation = collections.namedtuple('TimeMotionLocation',
                                            ['time', 'direction',
                                             'speed', 'location'])


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
    office : str
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
        self.office = gd['office_id']
        self.phenomena = gd['phenomena']
        self.significance = gd['significance']
        self.event_tracking_id = int(gd['event_tracking_id'])


class NoVtecCodeException(Exception):
    def __init__(self, message):
        self.message = message


class UGCParsingError(Exception):
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

    # exclude if it starts with a "."
    lst = [item for item in lst if not item.startswith('.')]

    if numlast is None:
        fnames = [os.path.join(dirname, item) for item in lst]
    else:
        fnames = [os.path.join(dirname, item) for item in lst[numlast:]]
    hzlst = [HazardsFile(fname) for fname in fnames]

    events = []
    for hazard_file in hzlst:
        for product in hazard_file:
            for segment in product.segments:
                for j, vtec_code in enumerate(segment.vtec):
                    evts = [x for x in events if x.contains(vtec_code)]
                    if len(evts) == 0:
                        # Must create a new event.
                        events.append(Event(vtec_code, segment))
                    else:
                        # The event already exists.  Just add this bulletin to
                        # the sequence of events.
                        assert len(evts) == 1
                        evt = evts[0]
                        evt.append(segment)

    if current is not None and current:
        events = [event for event in events if event.not_expired()]

    return events


class HazardsFile(object):
    """
    Collection of hazard messages.

    Attributes
    ----------
    filename : str
        Path to source file
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

        # Use universal newline support.
        with open(fname, 'rtU') as f:
            txt = f.read()

        # Get the base date from the filename.  The format is
        # YYYYMMDDHH.xxxx
        basename = os.path.basename(fname)
        try:
            file_base_date = dt.datetime(int(basename[0:4]),
                                         int(basename[4:6]),
                                         int(basename[6:8]),
                                         int(basename[8:10]), 0, 0)
        except ValueError:
            # Have not seen this case yet in the wild, but maybe...
            file_base_date = None

        # Split the text into separate events.  Look for the end of product
        # codes juxtaposed with beginning of product codes.
        regex = re.compile('\x03\x01')
        self._items = []
        for j, text_item in enumerate(regex.split(txt)):
            try:
                prod = Product(text_item, base_date=file_base_date)
            except (EmptyProductException, TestMessageException):
                continue

            self._items.append(prod)

    def __str__(self):
        return "Filename:  {}".format(self.filename)

    def __iter__(self):
        """
        Implements iterator protocol.
        """
        return iter(self._items)

    def __len__(self):
        """
        Implements built-in len(), returns number of Product objects.
        """
        return len(self._items)

    def __getitem__(self, idx):
        """
        Implement index lookup.
        """
        if isinstance(idx, slice):
            start = idx.start
            stop = idx.stop
            step = idx.step
            return self._items[start:stop:step]
        if idx >= len(self):
            raise KeyError(str(idx))

        return self._items[idx]


class Product(object):
    """
    Entire segmented or non-segmented message issued to public

    Attributes
    ----------
    segments : list
        Segments contained in this product.  An unsegmented product is treated
        as a product with a single segment.
    """

    def __init__(self, txt, base_date):
        """
        Parameters
        ----------
        txt : str
            Text constituting the entire product
        base_date : datetime.datetime
            Date attached to the file from whence this bulletin came.
        office : str
            ID of issuing office
        wmo_dtype, wmo_geog, wmo_code, wmo_retrans : str, str, int, str
            As defined in [1]
        wmo_issuance_time : datetime.datetime
            product issuance time in UTC
        awips_product, awips_location_id : str, str
            As defined in [1]
        """
        self.txt = txt
        self.base_date = base_date

        self.segments = []
        self.parse_wmo_abbreviated_heading_awips_id()

        # Each segment is delimited by "$$".  The last one is the product
        # trailer, which we will not parse.
        lst = re.split('\$\$', self.txt)
        for j, text_item in enumerate(lst[:-1]):
            try:
                segment = Segment(text_item, base_date)
                self.segments.append(segment)
            except (EmptySegmentException, TestMessageException):
                pass

        # self.parse_forecaster_identifier()

    def parse_forecaster_identifier(self):
        """
        A forecaster identifier at the end of the product is optional.

        If it is there, it follows the last '$$'.
        There are a certain number of newlines,
        then the identier (may have white space inside the identifier),
        then a certain number of newlines,
        possibly some more text we don't care about, like maybe a URL,
        sometimes multiple numbers of these paragraphs,
        then a certain number of newlines,
        then the end of the string.

        Not doing this at the moment, the communications trailer is too
        free-form.
        """
        regex = re.compile(r'''\$\$
                               \n+
                               ((?P<opt_url>HTTP://[A-Z/.]+)(\n\n){2})?
                               (?P<fid>([-\w/]+(\s[-/\w]+)*))?\s?(\.{3})?\n+
                               (?P<extra>[\w\040:/.()]*\n\n[\w\040:/.()]*\n*)
                               (\x03)?\n*$''', re.VERBOSE)
        m = regex.search(self.txt)
        if m is None:
            self.forecaster_identifier = None
        elif m.groupdict()['fid'] == '':
            self.forecaster_identifier = None
        else:
            self.forecaster_identifier = m.groupdict()['fid']

    def parse_wmo_abbreviated_heading_awips_id(self):
        regex = re.compile(r'''(?P<dtype_form>\w{2})
                               (?P<geog>\w{2})
                               (?P<code>\d{2})\s
                               (?P<office>\w{4})\s
                               (?P<dd>\d{2})(?P<hh>\d{2})(?P<mm>\d{2})\s?
                               (\s(?P<retrans>\w{3}))?\n\n
                               (?P<awips_product>\w{3})
                               (?P<awips_loc_id>\w[\w\s]{2})''', re.VERBOSE)
        m = regex.search(self.txt)
        if m is None:
            # Is it all just white space?  Empty products have been found in
            # the past.
            mws = re.search('\n+', self.txt)
            if mws.span()[0] == 0 and mws.span()[1] == len(self.txt):
                raise EmptyProductException()

            mtest = re.search('THIS IS A TEST MESSAGE.', self.txt)
            if mtest is not None:
                raise TestMessageException()
            else:
                raise InvalidProductException()

        self.wmo_dtype = m.group('dtype_form')
        self.wmo_geog = m.group('geog')
        self.wmo_code = int(m.group('code'))
        self.wmo_office = m.group('office')

        day = int(m.group('dd'))
        hour = int(m.group('hh'))
        minute = int(m.group('mm'))

        self.wmo_issuance_time = adjust_to_base_date(self.base_date,
                                                     day, hour, minute)

        self.wmo_retrans = m.group('retrans')
        self.awips_product = m.group('awips_product')
        self.awips_location_id = m.group('awips_loc_id')

    def __str__(self):
        return "Product:  {} segments".format(len(self))

    def __iter__(self):
        """
        Implements iterator protocol.
        """
        return iter(self.segments)

    def __len__(self):
        """
        Implements built-in len(), returns number of segments
        """
        return len(self.segments)


class EmptyProductException(Exception):
    pass


class TestMessageException(Exception):
    """
    Skip test messages.  See Section 7 of [1].
    """
    pass


class InvalidProductException(Exception):
    pass


class EmptySegmentException(Exception):
    pass


class InvalidSegmentException(Exception):
    pass


class EndOfProductException(Exception):
    pass


class Segment(object):

    def __init__(self, txt, base_date=None):
        """
        Parameters
        ----------
        txt : str
            Text constituting the entire bulletin
        base_date : datetime.datetime
            Date attached to the file from whence this bulletin came.
        expiration_date : datetime.datetime
            See [1]
        states : dict
            Maps states to the 3-digit FIPS codes for associated counties /
            parishes / zones.
        ugc_format : str
            Either 'county' or 'zone'
        """
        # Is the segment empty?
        m = re.search('\n+', txt)
        if m.span()[0] == 0 and m.span()[1] == len(txt):
            raise EmptySegmentException()

        # If there is nothing but white space with possibly one alphanumeric
        # token, then we are into the end-of-product block, which is not a
        # segment.  If the block also ends a file, then part of the
        # communications trailer may be in there as well (\x03).
        # regex = re.compile(r'''\n+
        #                        ((?P<opt_url>HTTP://[A-Z/.]+)(\n\n){2})?
        #                        (?P<fid>([-\w/]+(\s[-/\w]+)*))?\s?(\.{3})?\n*
        #                        (?P<extra>[\w\040:/.()]*\n\n[\w\040:/.()]*\n*)
        #                        (\x03)?\n*$''', re.VERBOSE)
        # if regex.match(txt):
        #     raise EndOfProductException()

        # if len(txt) < 10:
        #     raise InvalidSegmentException()

        self.txt = txt
        self.base_date = base_date

        self.parse_mnd_header()
        self.parse_segment_header()
        self.parse_content_block()
        self.parse_communications_trailer()

        # Clean up the text a bit.
        self.txt = self.txt.replace('\n\n', '\n').strip('\x01')

    def parse_content_block(self):
        """
        Parse all text information following the Segment Header Block.
        """
        self.parse_headlines()
        self.parse_narrative()
        self.parse_call_to_action()
        self.parse_lat_lon()
        self.parse_time_motion_location()

    def parse_lat_lon(self):
        """
        Parse the lat/lon polygon from the product content block.

        The section of text might look as follows:

        LAT...LON 4862 10197 4828 10190 4827 10223 4851 10259
              4870 10238
        TIME...MOT...LOC 2108Z 303DEG 38KT 4851 10225
            Content of message.
        """
        self.polygon = []
        self.wkt = None

        # Look for the constant LAT...LON string, and then
        #     at least one space, maybe more
        #     ... followed by indeterminate number of lat/lon pairs
        #     ... terminated by the carriage return sequence
        #     and match this pattern at least one, maybe more
        regex = re.compile(r'''LAT...LON(?P<latlon>(((\s+(\d{4,5}\s\d{4,5}\s?)
                                                         +\n\n)+)))''',
                           re.VERBOSE)
        m = regex.search(self.txt)
        if m is None:
            return

        self.polygon = self._parse_latlon_pairs(m.group('latlon'))
        self.create_wkt()

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

    def parse_time_motion_location(self):
        """
        Parse the time/motion/location info from the product content block.

        The section of text might look as follows:

        LAT...LON 4862 10197 4828 10190 4827 10223 4851 10259
              4870 10238
        TIME...MOT...LOC 2108Z 303DEG 38KT 4851 10225
            Content of message.
        """
        self.time_motion_location = None

        regex = re.compile(r"""TIME...MOT...LOC\s
                               (?P<tml_hh>\d{1,2})
                               (?P<tml_mm>\d{2})Z\s
                               (?P<tml_dir>\d{3})DEG\s
                               (?P<tml_speed>\d{2})KT\s
                               (?P<tml_loc>[\s\r\n\d{4,5}]+\n\n)
                            """, re.VERBOSE)
        m = regex.search(self.txt)
        if m is None:
            return

        # Assemble the time/motion/location information.
        hh = int(m.group('tml_hh'))
        mm = int(m.group('tml_mm'))
        tml_time = dt.datetime(self.base_date.year, self.base_date.month,
                               self.base_date.day, hh, mm, 0)
        tml_dir = int(m.group('tml_dir'))
        tml_speed = int(m.group('tml_speed'))
        tml_latlon = self._parse_latlon_pairs(m.group('tml_loc'))
        self.time_motion_location = TimeMotionLocation(time=tml_time,
                                                       direction=tml_dir,
                                                       speed=tml_speed,
                                                       location=tml_latlon)

    def _parse_latlon_pairs(self, text):
        """
        Parse lon/lat pairs from text.

        Parameters
        ----------
        text : str
            e.g.

            "4862 10197 4828 10190 4827 10223 4851 10259\r\r\n"
            "4870 10238"

            It could be a single point.
        """
        latlon_txt = text.replace('\n', ' ')
        if sys.hexversion < 0x03000000:
            nums = np.genfromtxt(StringIO(unicode(latlon_txt)))
        else:
            nums = np.genfromtxt(BytesIO(latlon_txt.encode()))
        lats = [float(x)/100.0 for x in nums[0::2]]
        lons = [float(x)/100.0 for x in nums[1::2]]

        return [item for item in zip(lons, lats)]

    def parse_narrative(self):
        pass

    def parse_call_to_action(self):
        pass

    def parse_communications_trailer(self):
        pass

    def parse_headlines(self):
        regex = re.compile(r'''\n\n\n\n
                               \.\.\.
                               (?P<header>[0-9\w\s\./\'-]*?)
                               \.\.\.
                               \n\n\n\n''', re.VERBOSE)
        m = regex.search(self.txt)
        if m is not None:
            raw_header = m.group('header')

            # Replace any sequence of newlines with just a space.
            self.headline = re.sub('\n\n', ' ', raw_header)

        else:
            self.headline = None

    def parse_segment_header(self):
        """
        Parse the segment header

        A segment header block consists of:

            a.    a UGC string
            b.    VTEC strings as appropriate
            c.    UGC associated plain language names as appropriate
            d.    an issuing date/time as appropriate
        """
        self.parse_universal_geographic_code()
        self.parse_vtec_code()

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

        # The UGC code can cross multiple lines.
        #
        # The standard doesn't say so, but there can apparently be a space
        # just before the end-of-line delimeter.
        regex = re.compile(r'''(\w{2}[CZ](\d{3}((-|>)\s?(\n\n)?))+)+
                               (?P<day>\d{2})
                               (?P<hour>\d{2})
                               (?P<minute>\d{2})-
                            ''', re.VERBOSE)

        m = regex.search(self.txt)
        if m is None:
            mtest = re.search('THIS IS A TEST MESSAGE.', self.txt)
            if mtest is not None:
                raise TestMessageException()

            msg = 'Could not parse the expiration time.\n\n{}'
            msg = msg.format(self.txt.replace('\n\n', '\n'))
            raise UGCParsingError(msg)

        dd = int(m.group('day'))
        hh = int(m.group('hour'))
        mm = int(m.group('minute'))

        self.expiration_date = adjust_to_base_date(self.base_date, dd, hh, mm)
        assert self.expiration_date > self.base_date

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
        #       counties/zones, which might span multiple lines
        #
        ugc_regex = re.compile(r'''(?P<fips>\w{2})
                                   (?P<format>[CZ])
                                   (?:\d{3}((-|>)(\n\n)?))+
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

        for m in vtec_regex.finditer(self.txt):
            the_vtec_code = m.group()
            _codes.append(the_vtec_code)
            self.vtec.append(VtecCode(m))

    def parse_mnd_header(self):
        """
        parse mass new disseminator header block

        This subsection contains

            a.   a broadcast instruction line
            b.   a product type line
            c.   an issuance office line
            d.   an issuance date/time
        """
        self.parse_mnd_issuance_time()

    def parse_mnd_issuance_time(self):
        """
        Parse the MND issuance Date/Time line.

        Examples look like

        402 PM CDT WED JUN 11 2008
        """
        regex = re.compile(r'''(?P<hh>\d{1,2})(?P<mm>\d{2})\s
                               (?P<meridiem>A|P)M\s
                               (?P<timezone>\w{3,4})\s
                               (?P<day_of_week>SUN|MON|TUE|WED|THU|FRI|SAT)\s
                               (?P<month>\w{3})\s
                               (?P<dd>\d{1,2})\s
                               (?P<year>\d{4})
                            ''', re.VERBOSE)
        m = regex.search(self.txt)
        if m is None:
            issuance_dt = None
        else:
            gd = m.groupdict()
            year = int(gd['year'])
            month = _MONTH[gd['month']]
            day = int(gd['dd'])
            hour = int(gd['hh'])
            minute = int(gd['mm'])
            issuance_dt = dt.datetime(year, month, day, hour, minute, 0)

            if gd['meridiem'] == 'P':
                issuance_dt += dt.timedelta(hours=12)

            issuance_dt -= dt.timedelta(hours=_TIMEZONES[gd['timezone']])

        self.mnd_issuance_time = issuance_dt


def adjust_to_base_date(base_date, day, hour, minute):
    """
    Parameters
    ----------
    base_date : datetime.datetime
        Unambiguous date derived from filename
    day, hour, minute : int
        Parts of date extracted from a 'ddhhmm' string.  Use the base_date
        to construct a complete date.

    Returns
    -------
    the_date : datetime.datetime
        Unambiguous date, possibly an issuance time
    """

    if day < base_date.day:
        if base_date.month == 12:
            # Beginning of next year
            year = base_date.year + 1
            the_time = dt.datetime(year, 1, day, hour, minute, 0)
        else:
            # Beginning of next month
            year = base_date.year
            month = base_date.month + 1
            the_time = dt.datetime(year, month, day, hour, minute, 0)
    else:
        the_time = dt.datetime(base_date.year, base_date.month,
                               day, hour, minute, 0)

    return the_time


class Event(HazardsFile):
    """
    Bulletins for fetime of an event.

    Attributes
    ----------
    vtec_code : str
        Object containing VTEC code.
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
        return '\n-----\n'.join(lst)

    def contains(self, vtec_code):
        """
        Test if a specific vtec code is contained in this bulletin.

        Parameters
        ----------
        vtec_code : VtecCode
            VTEC code object
        """
        if (((self._items[0].vtec[0].product == vtec_code.product) and
             (self._items[0].vtec[0].office == vtec_code.office) and
             (self._items[0].vtec[0].phenomena == vtec_code.phenomena) and
             (self._items[0].vtec[0].event_tracking_id == vtec_code.event_tracking_id))):
            return True
        else:
            return False

    def append(self, bulletin):
        self._items.append(bulletin)

    def not_expired(self):
        """
        Is this event still in progress?
        """
        if not dt.datetime.utcnow() >= self._items[-1].expiration_date:
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
