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

from hazards import HazardsFile, fetch_events

from . import fixtures


class FakeDatetime(datetime):
    "A fake replacement for datetime that can be mocked for testing"
    def __new__(cls, *args, **kwargs):
        return datetime.__new__(datetime, *args, **kwargs)


class TestHazards(unittest.TestCase):
    """
    """
    @unittest.skip('not now')
    def test_full_directory(self):
        """
        Should be able to read an entire directory of statements.
        """
        # hurr_lcl:  tropical storm / hurricane watch
        # noprcp:  heat advisory?
        # severe:  severe thunderstorm warning
        # special:  significant weather advisory
        # state_summ:  weather summary
        # svrlcl: severe thunderstorm watch
        # torn_warn:  tornado warning
        # tstrm_warn:  severe thunderstorm warning
        # wcn:  severe thunderstorm watch expiration
        # winter: winter weather advisory
        #
        # fflood
        for level1 in ['fflood', 'watch_warn']:
            path1 = os.path.join('tests', 'data', 'external', level1)
            for level2 in os.listdir(path1):
                path2 = os.path.join(path1, level2)
                for path3 in os.listdir(path2):
                    filename = os.path.join(path2, path3)
                    print(filename)
                    hzf = HazardsFile(filename)
                    for h in hzf:
                        pass
                        # for vtec in h.vtec:
                        #     if vtec.action == 'NEW':
                        #         action_lst.append((filename, vtec.action))

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
        FakeDatetime.utcnow = classmethod(lambda cls:  dt.datetime(2015, 7, 24, 8, 0, 0))

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

    def test_multiple_vtec_codes(self):
        """
        Multiple VTEC codes are possible.
        """
        path = os.path.join('tests', 'data', 'special', '2015062721.special')
        hzf = HazardsFile(path)

        self.assertEqual(hzf[0].vtec[0].product, 'O')
        self.assertEqual(hzf[0].vtec[0].action, 'UPG')
        self.assertEqual(hzf[0].vtec[0].office_id, 'KBOI')
        self.assertEqual(hzf[0].vtec[0].phenomena, 'FW')
        self.assertEqual(hzf[0].vtec[0].significance, 'A')
        self.assertEqual(hzf[0].vtec[0].event_tracking_id, 1)
        self.assertEqual(hzf[0].vtec[0].event_beginning_time,
                         dt.datetime(2015, 6, 28, 21, 0, 0))
        self.assertEqual(hzf[0].vtec[0].event_ending_time,
                         dt.datetime(2015, 6, 29, 6, 0, 0))

        self.assertEqual(hzf[0].vtec[1].product, 'O')
        self.assertEqual(hzf[0].vtec[1].action, 'NEW')
        self.assertEqual(hzf[0].vtec[1].office_id, 'KBOI')
        self.assertEqual(hzf[0].vtec[1].phenomena, 'FW')
        self.assertEqual(hzf[0].vtec[1].significance, 'W')
        self.assertEqual(hzf[0].vtec[1].event_tracking_id, 1)
        self.assertEqual(hzf[0].vtec[1].event_beginning_time,
                         dt.datetime(2015, 6, 28, 21, 0, 0))
        self.assertEqual(hzf[0].vtec[1].event_ending_time,
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
