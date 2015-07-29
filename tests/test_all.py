import datetime as dt
from datetime import datetime
import os
import sys
import unittest

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
        with patch('sys.argv', ['', '--d', dirname]):
            with self.assertRaises(DirectoryNotFoundException):
                hazards.command_line.hzparse()

    def test_basic(self):
        """
        Should be able to read a directory
        """
        dirname = os.path.join('tests', 'data', 'noaaport', 'nwx',
                               'watch_warn', 'svrlcl')
        with patch('sys.argv', ['', '--d', dirname]):
            with patch('sys.stdout', new=StringIO()):
                hazards.command_line.hzparse()

    def test_skip(self):
        """
        Should not error out

        See issues #28, #29
        """
        dirname = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                               'statment')
        with patch('sys.argv', ['', '--d', dirname]):
            with patch('sys.stdout', new=StringIO()):
                hazards.command_line.hzparse()
        self.assertTrue(True)


class TestSuite(unittest.TestCase):
    """
    """

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
                         {'AL': [1, 5, 7, 9, 11, 15, 17, 19,21, 27, 29, 37, 43,
                                 47, 51, 55, 57, 63, 65, 73, 75, 81, 85, 87,
                                 91, 93, 101, 105, 109, 111, 113, 115, 117,
                                 119, 121, 123, 125, 127, 133]})
        self.assertEqual(hzf[-1].segments[0].ugc_format, 'county')


class TestSuiteOld(unittest.TestCase):
    """
    hurr_lcl:  tropical storm / hurricane watch
    noprcp:  heat advisory?
    severe:  severe thunderstorm warning
    special:  significant weather advisory
    state_summ:  weather summary
    svrlcl: severe thunderstorm watch
    torn_warn:  tornado warning
    tstrm_warn:  severe thunderstorm warning
    wcn:  severe thunderstorm watch expiration
    winter: winter weather advisory
    """
    def test_appendix_b_example_one(self):
        """
        non segmented routine product
        """
        path = os.path.join('tests', 'data', 'example1.txt')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 1)
        self.assertEqual(hzf[0].expiration_time,
                         dt.datetime(2008, 6, 12, 11, 15, 0))
        self.assertEqual(hzf[0].headline, 'HEADLINES')

    def test_appendix_b_example_two(self):
        """
        non segmented warning product
        """
        path = os.path.join('tests', 'data', 'example2.txt')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 1)
        self.assertEqual(hzf[0].expiration_time,
                         dt.datetime(2008, 6, 4, 19, 15, 0))
        self.assertIsNone(hzf[0].headline)

        actual = hzf[0].polygon
        expected = [(88.01, 38.94),
                    (88.65, 39.03),
                    (88.7, 39.21),
                    (88.65, 39.22),
                    (88.64, 39.22),
                    (88.48, 39.22),
                    (88.47, 39.28),
                    (88.10, 39.38)]
        self.assertEqual(actual, expected)

        # time, motion, location information
        self.assertEqual(hzf[0].time_motion_location.time,
                         dt.datetime(2008, 6, 4, 18, 15, 0))
        self.assertEqual(hzf[0].time_motion_location.direction, 257)
        self.assertEqual(hzf[0].time_motion_location.speed, 45)
        self.assertEqual(hzf[0].time_motion_location.location,
                         [(88.55, 39.14), ])

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
        self.assertTrue(events[-1].not_expired())
        self.assertEqual(len(events), 17)

        events = fetch_events(dirname, current=True)
        self.assertTrue(events[-1].not_expired())
        self.assertEqual(len(events), 1)

    def test_individual_event(self):
        """
        Split file into individual events.
        """
        dirname = os.path.join('tests', 'data', 'noaaport', 'nwx',
                               'watch_warn', 'svrlcl')
        events = fetch_events(dirname)

        # The first event has four bulletins.
        self.assertEqual(len(events[0]), 4)
        # self.assertFalse(events[0].current())

        # The last event has seventeen bulletins.
        self.assertEqual(len(events[-1]), 9)
        # self.assertTrue(events[-1].current())

    def test_fflood(self):
        path = os.path.join('tests', 'data', 'fflood', 'warn',
                            '2015062713.warn')
        hzf = HazardsFile(path)

        # Flood warnings don't have headlines.
        self.assertIsNone(hzf[0].headline)

        self.assertEqual(hzf[0].txt, fixtures.fflood_txt)
        self.assertEqual(hzf[0].vtec[0].product, 'O')
        self.assertEqual(hzf[0].vtec[0].action, 'NEW')
        self.assertEqual(hzf[0].vtec[0].office_id, 'KIWX')
        self.assertEqual(hzf[0].vtec[0].phenomena, 'FA')
        self.assertEqual(hzf[0].vtec[0].significance, 'W')
        self.assertEqual(hzf[0].vtec[0].event_tracking_id, 15)
        self.assertEqual(hzf[0].vtec[0].event_beginning_time,
                         dt.datetime(2015, 6, 27, 13, 7, 0))
        self.assertEqual(hzf[0].vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 27, 16, 0, 0))
        self.assertEqual(hzf[0].expiration_time,
                         dt.datetime(2015, 6, 27, 16, 0, 0))

    def test_fflood_statment_expiration_time(self):
        """
        Verify parsing the expiration time

        See issue #28
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                            'statment', '2015072314.sttmnt')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[3].expiration_time,
                         dt.datetime(2015, 7, 24, 14, 26, 0))

    def test_fflood_statment(self):
        """
        Should not say there are no bulletins

        See issue #27
        """
        path = os.path.join('tests', 'data', 'noaaport', 'nwx', 'fflood',
                            'statment', '2015072313.sttmnt')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 5)

        # No headline
        self.assertIsNone(hzf[0].headline)

        self.assertEqual(hzf[0].expiration_time,
                         dt.datetime(2015, 7, 24, 13, 2, 0))

        # No VTEC code here
        self.assertEqual(len(hzf[0].vtec), 0)

        # No polygon here
        self.assertEqual(len(hzf[0].polygon), 0)

        # No polygon, so no WKT
        self.assertIsNone(hzf[0].wkt)

        # The UGC line is "MOC099-189-241302-"
        self.assertEqual(hzf[0].ugc_format, 'county')
        self.assertEqual(hzf[0].states, {'MO': [99, 189]})

        # We have text...
        self.assertIsNotNone(hzf[0].txt)

    def test_multiple_vtec_codes(self):
        """
        Multiple VTEC codes are possible.
        """
        path = os.path.join('tests', 'data', 'special', '2015062721.special')
        hzf = HazardsFile(path)

        self.assertEqual(len(hzf), 133)

        self.assertEqual(hzf[11].vtec[0].product, 'O')
        self.assertEqual(hzf[11].vtec[0].action, 'UPG')
        self.assertEqual(hzf[11].vtec[0].office_id, 'KBOI')
        self.assertEqual(hzf[11].vtec[0].phenomena, 'FW')
        self.assertEqual(hzf[11].vtec[0].significance, 'A')
        self.assertEqual(hzf[11].vtec[0].event_tracking_id, 1)
        self.assertEqual(hzf[11].vtec[0].event_beginning_time,
                         dt.datetime(2015, 6, 28, 21, 0, 0))
        self.assertEqual(hzf[11].vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 29, 6, 0, 0))

        self.assertEqual(hzf[11].vtec[1].product, 'O')
        self.assertEqual(hzf[11].vtec[1].action, 'NEW')
        self.assertEqual(hzf[11].vtec[1].office_id, 'KBOI')
        self.assertEqual(hzf[11].vtec[1].phenomena, 'FW')
        self.assertEqual(hzf[11].vtec[1].significance, 'W')
        self.assertEqual(hzf[11].vtec[1].event_tracking_id, 1)
        self.assertEqual(hzf[11].vtec[1].event_beginning_time,
                         dt.datetime(2015, 6, 28, 21, 0, 0))
        self.assertEqual(hzf[11].vtec[1].event_ending_time,
                         dt.datetime(2015, 6, 29, 6, 0, 0))

    def test_expiration_date_exceeding_file_date(self):
        """
        The expiration date should lie in the future from the file date.
        """
        path = os.path.join('tests', 'data', 'noprcp', '2015063017.noprcp')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[0].expiration_time,
                         dt.datetime(2015, 7, 1, 3, 0, 0))

    def test_parse_ugc(self):
        """
        Possible UGC lines are

        GAZ087-088-099>101-114>119-137>141-SCZ040-042>045-047>052-242200-
        """
        path = os.path.join('tests', 'data', 'noprcp', '2015062413.noprcp')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[0].expiration_time,
                         dt.datetime(2015, 6, 24, 22, 0, 0))

        # Verify the geographic information.
        self.assertEqual(hzf[0].states['GA'],
                         [87, 88, 99, 100, 101, 114, 115, 116, 117, 118, 119,
                          137, 138, 139, 140, 141])
        self.assertEqual(hzf[0].states['SC'],
                         [40, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52])
        self.assertEqual(hzf[0].ugc_format, 'zone')

    def test_hurricane_warning_with_no_times_in_vtec_code(self):
        path = os.path.join('tests', 'data', 'hurr_lcl', '2015050805.hurr')
        hzf = HazardsFile(path)
        self.assertEqual(hzf[0].base_date, dt.datetime(2015, 5, 8, 5, 0, 0))
        self.assertIsNone(hzf[0].vtec[0].event_beginning_time)
        self.assertIsNone(hzf[0].vtec[0].event_ending_time)

    def test_summary_with_quote(self):
        """
        Should be able to find summaries that contain quote characters.
        """
        HazardsFile(fixtures.summary_with_quote)

    def test_basic_svs(self):
        hzf = HazardsFile(fixtures.severe_thunderstorm_file)

        self.assertEqual(len(hzf), 74)

        # Make sure that we raise the appropriate error.  Is this is?
        with self.assertRaises(KeyError):
            hzf[74]

        actual = hzf[0].headline
        expected = ('A SEVERE THUNDERSTORM WARNING REMAINS IN EFFECT UNTIL '
                    '530 PM EDT FOR NORTHEASTERN BEAVER AND SOUTH CENTRAL '
                    'LAWRENCE COUNTIES')
        self.assertEqual(actual, expected)

        self.assertEqual(hzf[0].vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 21, 21, 30, 0))

        self.assertEqual(hzf[0].expiration_time,
                         dt.datetime(2015, 6, 21, 21, 30, 0))

        actual = hzf[0].wkt
        expected = ('POLYGON((80.43 40.84, 80.32 40.89, 80.16 40.83, '
                    '80.15 40.69, 80.43 40.84))')
        self.assertEqual(actual, expected)

    def test_print_with_headline(self):
        """
        Verify that printing a bulletin works as expected with headline
        """
        hzf = HazardsFile(fixtures.severe_thunderstorm_file)
        with patch('sys.stdout', new=StringIO()) as fake_out:
            print(hzf[0])
            actual = fake_out.getvalue().strip()
        expected = fixtures.severe_print
        self.assertEqual(actual, expected)

    def test_print_without_headline(self):
        """
        Verify that printing a bulletin works as expected without headlines
        """
        path = os.path.join('tests', 'data', 'fflood', 'warn',
                            '2015062713.warn')
        hzf = HazardsFile(path)

        with patch('sys.stdout', new=StringIO()) as fake_out:
            print(hzf[0])
            actual = fake_out.getvalue().strip()
        expected = fixtures.fflood_print
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
