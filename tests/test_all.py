import datetime as dt
from datetime import datetime
import os
import sys
import unittest
import warnings

if sys.hexversion < 0x03000000:
    import mock
    from mock import patch
    from StringIO import StringIO
else:
    from unittest import mock
    from unittest.mock import patch
    from io import StringIO

import hazards
from hazards import HazardsFile, fetch_events
from hazards.command_line import DirectoryNotFoundException

from . import fixtures


class FakeDatetime(datetime):
    "A fake replacement for datetime that can be mocked for testing"
    def __new__(cls, *args, **kwargs):
        return datetime.__new__(datetime, *args, **kwargs)


class TestHzparser(unittest.TestCase):
    """
    Test command line tool for parsing a directory of bulletins
    """

    def test_directory_not_present(self):
        """
        Should error out gracefully when a directory does not exist.
        """
        dirname = os.path.join('tests', 'data', 'fflood2')
        with patch('sys.argv', ['', dirname]):
            with self.assertRaises(DirectoryNotFoundException):
                hazards.command_line.hzparse()

    def test_basic(self):
        """
        Should be able to read a directory
        """
        dirname = os.path.join('tests', 'data', 'noaaport', 'nwx',
                               'watch_warn', 'svrlcl')
        with patch('sys.argv', ['', dirname]):
            with patch('sys.stdout', new=StringIO()):
                hazards.command_line.hzparse()

    def test_skip(self):
        """
        Should not error out

        See issues #28, #29
        """
        dirname = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                               'statment')
        with patch('sys.argv', ['', dirname]):
            with patch('sys.stdout', new=StringIO()):
                hazards.command_line.hzparse()
        self.assertTrue(True)

    def test_verify_output(self):
        """
        verify output
        """
        dirname = os.path.join('tests', 'data', 'special')
        with patch('sys.argv', ['', dirname]):
            with patch('sys.stdout', new=StringIO()) as fake_stdout:
                hazards.command_line.hzparse()
                actual = fake_stdout.getvalue().strip()
        expected = 'File:  2015062721.special (130 products)'
        self.assertEqual(actual, expected)


class TestSuite(unittest.TestCase):
    """
    """
    def test_events(self):
        path = os.path.join('tests', 'data', 'events', 'noaaport',
                            'nwx', 'fflood', 'warn')
        evts = fetch_events(path)

        # 7 independent events
        self.assertEqual(len(evts), 7)

        # First event has two different messages.
        self.assertEqual(len(evts[0]), 2)

        # The rest have just a single message.
        for j in range(1, 7):
            self.assertEqual(len(evts[j]), 1)

    def test_print_vtec(self):
        path = os.path.join('tests', 'data', 'events', 'noaaport',
                            'nwx', 'fflood', 'warn')
        evts = fetch_events(path)
        evt = evts[-1]
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            print(evt._vtec_code)
            actual = fake_stdout.getvalue().strip()
        self.assertEqual(actual, fixtures.vtec_print)

    def test_print_event(self):
        path = os.path.join('tests', 'data', 'fflood', 'warn')
        evts = fetch_events(path)
        evt = evts[-1]
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            print(evt)
            actual = fake_stdout.getvalue().strip()
        self.assertEqual(actual, fixtures.event_print)

    @unittest.skip('volcano/volcano:  no spec')
    def test_volcano_volcano(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'volcano',
                            'volcano', '2015080210.volc')
        HazardsFile(path)

    @unittest.skip('volcano/volcano:  no spec')
    def test_marine_high_seas(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'marine',
                            'high_sea', '2015073009.high')
        HazardsFile(path)

    def test_firefcst_with_invalid_awips_location_id(self):
        # Also has invalid space after AWIPS retransmission thingy.
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'firewx',
                            'firefcst', '2015072912.firefcst')
        HazardsFile(path)

    def test_firefcst(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'firewx',
                            'firefcst', '2015072919.firefcst')
        HazardsFile(path)

    def test_another_awips_product_with_no_ugc(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'state_summ', '2015072921.stsum')
        HazardsFile(path)

    def test_awips_nwsli_with_newline_instead_of_space(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'state_summ', '2015072919.stsum')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hzf = HazardsFile(path)
        self.assertEqual(hzf[8].awips_location_id, 'WI\n')

    def test_2015072916_sttmnt(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                            'statment', '2015072916.sttmnt')
        HazardsFile(path)

    def test_expiration_date_exceeding_file_time(self):
        """
        this is actually ok
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                            'statment', '2015072709.sttmnt')
        HazardsFile(path)

    def test_parse_fflood_2015073115_sttmnt(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                            'statment', '2015073115.sttmnt')
        HazardsFile(path)

    def test_parse_2015073100_stsum(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'state_summ', '2015073100.stsum')
        HazardsFile(path)

    def test_parse_tstrm_file_for_awips_identifier(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'tstrm_warn', '2015072919.tstrm')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[10].awips_product, 'PTS')
        self.assertEqual(hzf[10].awips_location_id, 'DY1')

    def test_forecaster_id_followed_by_multiple_paragraphs(self):
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'noprcp', '2015072812.noprcp')
        HazardsFile(path)

    def test_url_preceding_forecaster_id(self):
        """
        Parse forecaster identifier preceded by URL
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'special', '2015072803.special')
        HazardsFile(path)

    def test_forecaster_id_with_dash(self):
        """
        Parse forecaster identifier with a dash
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'special', '2015072918.special')
        HazardsFile(path)

    def test_communications_trailer_with_no_id_but_more_info(self):
        """
        Parse forecaster identifier with no ID, but extra info
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'special', '2015072717.special')
        HazardsFile(path)

    def test_special_forecaster_identifier_with_slash(self):
        """
        Parse forecaster identifier with slash
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'special', '2015072700.special')
        HazardsFile(path)

    def test_forecaster_identifier(self):
        """
        Parse out the forecaster identifier
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'wcn', '2015051018.wcn')
        HazardsFile(path)

        # product = hzf[2]
        # self.assertEqual(product.forecaster_identifier, '46')

    def test_2015051018_wcn(self):
        """
        parse without erroring out
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'wcn', '2015051018.part.wcn')
        hzf = HazardsFile(path)
        self.assertEqual(len(hzf), 1)

    def test_wcn_with_test_message(self):
        """
        parse without erroring out
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'wcn', '2015032514.wcn')
        HazardsFile(path)
        self.assertTrue(True)

    def test_state_summ_with_space_after_wmo_issuance_time(self):
        """
        parse without erroring out
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'state_summ', '2015072708.stsum')
        HazardsFile(path)
        self.assertTrue(True)

    def test_state_summ(self):
        """
        parse without erroring out
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'watch_warn',
                            'state_summ', '2015072920.stsum')
        HazardsFile(path)
        self.assertTrue(True)

    def test_summary_with_quote(self):
        """
        Should be able to find summaries that contain quote characters.

        It's enough that it does not error out.
        """
        path = os.path.join('tests', 'data', 'severe', '2015062722.severe')
        HazardsFile(path)
        self.assertTrue(True)

    def test_basic_svs(self):
        path = os.path.join('tests', 'data', 'severe', '2015062121.severe')
        hzf = HazardsFile(path)

        # 68 products, 12 segmented products, 80 segments total
        self.assertEqual(len(hzf), 68)

        # Make sure that we raise the appropriate error.  Is this is?
        with self.assertRaises(KeyError):
            hzf[68]

        actual = hzf[0].segments[0].headline
        expected = ('A SEVERE THUNDERSTORM WARNING REMAINS IN EFFECT UNTIL '
                    '530 PM EDT FOR NORTHEASTERN BEAVER AND SOUTH CENTRAL '
                    'LAWRENCE COUNTIES')
        self.assertEqual(actual, expected)

        self.assertEqual(hzf[0].segments[0].vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 21, 21, 30, 0))

        self.assertEqual(hzf[0].segments[0].expiration_date,
                         dt.datetime(2015, 6, 21, 21, 30, 0))

        actual = hzf[0].segments[0].wkt
        expected = ('POLYGON((80.43 40.84, 80.32 40.89, 80.16 40.83, '
                    '80.15 40.69, 80.43 40.84))')
        self.assertEqual(actual, expected)

    def test_hurricane_warning_with_no_times_in_vtec_code(self):
        path = os.path.join('tests', 'data', 'hurr_lcl', '2015050805.hurr')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[0].segments[0].base_date,
                         dt.datetime(2015, 5, 8, 5, 0, 0))
        self.assertIsNone(hzf[0].segments[0].vtec[0].event_beginning_time)
        self.assertIsNone(hzf[0].segments[0].vtec[0].event_ending_time)

    def test_parse_ugc(self):
        """
        Possible UGC lines are

        GAZ087-088-099>101-114>119-137>141-SCZ040-042>045-047>052-242200-
        """
        path = os.path.join('tests', 'data', 'noprcp', '2015062413.noprcp')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[0].segments[0].expiration_date,
                         dt.datetime(2015, 6, 24, 22, 0, 0))

        # Verify the geographic information.
        self.assertEqual(hzf[0].segments[0].states['GA'],
                         [87, 88, 99, 100, 101, 114, 115, 116, 117, 118, 119,
                          137, 138, 139, 140, 141])
        self.assertEqual(hzf[0].segments[0].states['SC'],
                         [40, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52])
        self.assertEqual(hzf[0].segments[0].ugc_format, 'zone')

    def test_expiration_date_exceeding_file_date(self):
        """
        The expiration date should lie in the future from the file date.
        """
        path = os.path.join('tests', 'data', 'noprcp', '2015063017.noprcp')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[0].segments[0].expiration_date,
                         dt.datetime(2015, 7, 1, 3, 0, 0))

    def test_fflood_statment_has_products(self):
        """
        Should not say there are no products

        See issue #27
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                            'statment', '2015072313.sttmnt')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 5)

    def test_multiple_vtec_codes(self):
        """
        Multiple VTEC codes are possible.
        """
        path = os.path.join('tests', 'data', 'special', '2015062721.special')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 130)

        segment = hzf[11].segments[0]

        self.assertEqual(segment.vtec[0].product, 'O')
        self.assertEqual(segment.vtec[0].action, 'UPG')
        self.assertEqual(segment.vtec[0].office, 'KBOI')
        self.assertEqual(segment.vtec[0].phenomena, 'FW')
        self.assertEqual(segment.vtec[0].significance, 'A')
        self.assertEqual(segment.vtec[0].event_tracking_id, 1)
        self.assertEqual(segment.vtec[0].event_beginning_time,
                         dt.datetime(2015, 6, 28, 21, 0, 0))
        self.assertEqual(segment.vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 29, 6, 0, 0))

        self.assertEqual(segment.vtec[1].product, 'O')
        self.assertEqual(segment.vtec[1].action, 'NEW')
        self.assertEqual(segment.vtec[1].office, 'KBOI')
        self.assertEqual(segment.vtec[1].phenomena, 'FW')
        self.assertEqual(segment.vtec[1].significance, 'W')
        self.assertEqual(segment.vtec[1].event_tracking_id, 1)
        self.assertEqual(segment.vtec[1].event_beginning_time,
                         dt.datetime(2015, 6, 28, 21, 0, 0))
        self.assertEqual(segment.vtec[1].event_ending_time,
                         dt.datetime(2015, 6, 29, 6, 0, 0))

    @mock.patch('hazards.dt.datetime', FakeDatetime)
    def test_still_active(self):
        """
        Verify that not_expired returns True when correct to do so
        """
        fake_utcnow = lambda cls:  dt.datetime(2015, 7, 24, 8, 0, 0)
        FakeDatetime.utcnow = classmethod(fake_utcnow)

        dirname = os.path.join('tests', 'data', 'noaaport', 'nwx',
                               'watch_warn', 'svrlcl')

        events = fetch_events(dirname)
        self.assertEqual(len(events), 17)
        self.assertTrue(events[-1].not_expired())

        events = fetch_events(dirname, current=True)
        self.assertTrue(events[-1].not_expired())
        self.assertEqual(len(events), 1)

    def test_fetch_not_necessarily_active(self):
        """
        Fetch all events, they should all be inactive.
        """
        dirname = os.path.join('tests', 'data', 'noaaport', 'nwx',
                               'watch_warn', 'svrlcl')

        # All these events expired long ago.
        events = fetch_events(dirname)
        for event in events:
            self.assertFalse(event.not_expired())

        # Should result in exactly the same result.
        events = fetch_events(dirname, current=True)
        for event in events:
            self.assertFalse(event.not_expired())

    def test_severe_thunderstorm_watch_segmented(self):
        """
        This file consists of a single segmented event.
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx',
                            'watch_warn', 'svrlcl', '2015072101.svrlcl')

        hzf = HazardsFile(path)
        self.assertEqual(len(hzf), 1)
        self.assertEqual(len(hzf[0].segments), 2)

        segment = hzf[0].segments[0]
        self.assertEqual(segment.states, {'IL': [3, 77, 153, 181, 199],
                                          'MO': [17, 31, 35, 157, 201, 223]})
        self.assertEqual(segment.expiration_date,
                         dt.datetime(2015, 7, 21, 3, 0, 0))

        segment = hzf[0].segments[1]
        self.assertEqual(segment.expiration_date,
                         dt.datetime(2015, 7, 21, 6, 0, 0))

    def test_hurricane_segmented(self):
        """
        This file consists of a single segmented event.
        """
        path = os.path.join('tests', 'data', 'hurr_lcl', '2015050805.hurr')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 1)

        product = hzf[0]

        self.assertEqual(product.wmo_dtype, 'WT')
        self.assertEqual(product.wmo_geog, 'US')
        self.assertEqual(product.wmo_code, 82)
        self.assertEqual(product.wmo_office, 'KILM')
        self.assertEqual(product.wmo_issuance_time,
                         dt.datetime(2015, 5, 8, 5, 59, 0))
        self.assertIsNone(product.wmo_retrans)

        self.assertEqual(product.awips_product, 'TCV')
        self.assertEqual(product.awips_location_id, 'ILM')

        self.assertEqual(len(product.segments), 10)

        # First segment
        segment = product.segments[0]
        self.assertEqual(segment.expiration_date,
                         dt.datetime(2015, 5, 8, 14, 0, 0))
        self.assertEqual(segment.states, {'NC': [106]})
        self.assertEqual(segment.ugc_format, 'zone')

        self.assertIsNone(segment.vtec[0].event_beginning_time)
        self.assertIsNone(segment.vtec[0].event_ending_time)
        self.assertEqual(segment.vtec[0].product, 'O')
        self.assertEqual(segment.vtec[0].action, 'CON')
        self.assertEqual(segment.vtec[0].office, 'KILM')
        self.assertEqual(segment.vtec[0].phenomena, 'TR')
        self.assertEqual(segment.vtec[0].significance, 'A')
        self.assertEqual(segment.vtec[0].event_tracking_id, 1001)

        self.assertEqual(segment.headline,
                         'TROPICAL STORM WATCH REMAINS IN EFFECT')

        # Last segment
        segment = product.segments[-1]
        self.assertEqual(segment.expiration_date,
                         dt.datetime(2015, 5, 8, 14, 0, 0))
        self.assertEqual(segment.states, {'SC': [55]})
        self.assertEqual(segment.ugc_format, 'zone')

        self.assertIsNone(segment.vtec[0].event_beginning_time)
        self.assertIsNone(segment.vtec[0].event_ending_time)
        self.assertEqual(segment.vtec[0].product, 'O')
        self.assertEqual(segment.vtec[0].action, 'CON')
        self.assertEqual(segment.vtec[0].office, 'KILM')
        self.assertEqual(segment.vtec[0].phenomena, 'TR')
        self.assertEqual(segment.vtec[0].significance, 'A')
        self.assertEqual(segment.vtec[0].event_tracking_id, 1001)

        self.assertEqual(segment.headline,
                         'TROPICAL STORM WATCH REMAINS IN EFFECT')

    def test_write_shapefiles(self):
        """
        Verify shapefile creation
        """
        path = os.path.join('tests', 'data', 'torn_warn')
        evts = fetch_events(path)
        self.fail('fail')

    def test_torn_warn_non_segmented(self):
        """
        Verify non-segmented products (torn_warn)
        """
        path = os.path.join('tests', 'data', 'torn_warn', '2015062423.torn')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 6)

        # No headlines
        for product in hzf:
            self.assertIsNone(hzf[0].segments[0].headline)

        # All products have latlon, time/motion/location
        # All of them have the time/direction/motion
        for product in hzf:
            self.assertTrue(len(product.segments[0].polygon) > 0)
            self.assertIsNotNone(product.segments[0].time_motion_location)

        self.assertEqual(hzf[0].segments[0].time_motion_location.time,
                         dt.datetime(2015, 6, 24, 23, 0, 0))
        self.assertEqual(hzf[0].segments[0].time_motion_location.direction,
                         277)
        self.assertEqual(hzf[0].segments[0].time_motion_location.speed,
                         15)
        self.assertEqual(hzf[0].segments[0].time_motion_location.location,
                         [(104.92, 39.70)])
        self.assertEqual(hzf[0].segments[0].polygon,
                         [(105.02, 39.61), (105, 39.74), (104.61, 39.74),
                          (104.68, 39.6)])
        self.assertEqual(hzf[0].segments[0].wkt,
                         'POLYGON((105.02 39.61, 105.0 39.74, 104.61 39.74, '
                         '104.68 39.6, 105.02 39.61))')

    def test_fflood_non_segmented(self):
        """
        Verify non-segmented products (fflood)
        """
        path = os.path.join('tests', 'data', 'fflood', 'warn',
                            '2015062713.warn')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 4)

        # First two products have no headlines, last two do
        self.assertIsNone(hzf[0].segments[0].headline)
        self.assertIsNone(hzf[1].segments[0].headline)
        self.assertEqual(hzf[2].segments[0].headline,
                         "The National Weather Service in Tulsa has issued a "
                         "Flood Warning  for the following rivers in Arkansas")
        self.assertEqual(hzf[3].segments[0].headline,
                         "The National Weather Service in Tulsa has issued a "
                         "Flood Warning  for the following rivers in Arkansas")

        # All products have latlon
        # None of them have the time/direction/motion
        for product in hzf:
            self.assertTrue(len(product.segments[0].polygon) > 0)
            self.assertIsNone(product.segments[0].time_motion_location)

        self.assertEqual(hzf[0].segments[0].txt, fixtures.fflood_txt)
        self.assertEqual(hzf[0].segments[0].vtec[0].product, 'O')
        self.assertEqual(hzf[0].segments[0].vtec[0].action, 'NEW')
        self.assertEqual(hzf[0].segments[0].vtec[0].office, 'KIWX')
        self.assertEqual(hzf[0].segments[0].vtec[0].phenomena, 'FA')
        self.assertEqual(hzf[0].segments[0].vtec[0].significance, 'W')
        self.assertEqual(hzf[0].segments[0].vtec[0].event_tracking_id, 15)
        self.assertEqual(hzf[0].segments[0].vtec[0].event_beginning_time,
                         dt.datetime(2015, 6, 27, 13, 7, 0))
        self.assertEqual(hzf[0].segments[0].vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 27, 16, 0, 0))
        self.assertEqual(hzf[0].segments[0].expiration_date,
                         dt.datetime(2015, 6, 27, 16, 0, 0))

        self.assertEqual(hzf[-1].segments[0].vtec[0].product, 'O')
        self.assertEqual(hzf[-1].segments[0].vtec[0].action, 'NEW')
        self.assertEqual(hzf[-1].segments[0].vtec[0].office, 'KTSA')
        self.assertEqual(hzf[-1].segments[0].vtec[0].phenomena, 'FL')
        self.assertEqual(hzf[-1].segments[0].vtec[0].significance, 'W')
        self.assertEqual(hzf[-1].segments[0].vtec[0].event_tracking_id, 65)
        self.assertEqual(hzf[-1].segments[0].vtec[0].event_beginning_time,
                         dt.datetime(2015, 6, 27, 18, 0, 0))
        self.assertEqual(hzf[-1].segments[0].vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 29, 4, 30, 0))
        self.assertEqual(hzf[-1].segments[0].expiration_date,
                         dt.datetime(2015, 6, 27, 21, 43, 0))

    def test_fflood_statment(self):
        """
        Should not say there are no products
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                            'statment', '2015072313.sttmnt')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 5)

        # Only the last product has a headline.
        for product in hzf[0:4]:
            self.assertIsNone(product.segments[0].headline)
        self.assertEqual(hzf[-1].segments[0].headline,
                         "Daily River Forecast For North And Central Alabama")

        self.assertEqual(hzf[0].segments[0].expiration_date,
                         dt.datetime(2015, 7, 24, 13, 2, 0))

        # No VTEC codes, polygons, wkt
        # All have text, of course.
        for product in hzf:
            self.assertEqual(len(product.segments[0].vtec), 0)
            self.assertEqual(len(product.segments[0].polygon), 0)
            self.assertIsNone(product.segments[0].wkt)
            self.assertIsNotNone(product.segments[0].txt)

        # The last product has a lot of counties.
        self.assertEqual(hzf[-1].segments[0].states,
                         {'AL': [1, 5, 7, 9, 11, 15, 17, 19, 21, 27, 29, 37,
                                 43, 47, 51, 55, 57, 63, 65, 73, 75, 81, 85,
                                 87, 91, 93, 101, 105, 109, 111, 113, 115, 117,
                                 119, 121, 123, 125, 127, 133]})
        self.assertEqual(hzf[-1].segments[0].ugc_format, 'county')


if __name__ == '__main__':
    unittest.main()
