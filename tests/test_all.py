from contextlib import closing
import datetime as dt
import os
import sys
import unittest
import urllib

if sys.hexversion < 0x03000000:
    from mock import patch
    from StringIO import StringIO
else:
    from unittest.mock import patch
    from io import StringIO

from hazards import HazardsFile

from . import fixtures


class TestHazards(unittest.TestCase):
    """
    """
    def get_data(self, url):
        with closing(urllib.urlopen(url)) as page:
            txt = page.read()
        return txt

    @unittest.skip('not now')
    def test_full_directory(self):
        """
        Should be able to read an entire directory of statements.
        """
        action_lst = []
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
        # tstrm_warn, wcn doesn't work
        for kind in ['hurr_lcl', 'noprcp', 'severe', 'special', 'state_summ',
                     'svrlcl', 'torn_warn', 'tstrm_warn', 'wcn', 'winter']:
            print(kind)
            path = os.path.join('tests', 'data', 'watch_warn', kind)
            for item in os.listdir(path):
                filename = os.path.join(path, item)
                print(filename)
                hzf = HazardsFile(filename)
                for h in hzf:
                    for vtec in h.vtec:
                        if vtec.action == 'NEW':
                            action_lst.append((filename, vtec.action))
        print(action_lst)

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
        The expiration date MUST always lie in the future from the file date.
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

        self.assertEqual(len(hzf), 36)
        with self.assertRaises(KeyError):
            hzf[36]

        actual = hzf[0].header
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

    def test_basic_print(self):
        """
        Verify that printing a bulletin works as expected.
        """
        hzf = HazardsFile(fixtures.severe_thunderstorm_file)
        with patch('sys.stdout', new=StringIO()) as fake_out:
            print(hzf[0])
            actual = fake_out.getvalue().strip()
        expected = fixtures.tstorm_warning_txt
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
