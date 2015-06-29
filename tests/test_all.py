from contextlib import closing
import datetime as dt
import sys
import unittest
import urllib

if sys.hexversion < 0x03000000:
    from mock import patch
    from StringIO import StringIO
else:
    from unittest.mock import patch
    from io import StringIO

from hazards import Hazards, HazardsFile
from hazards import commandline

from . import fixtures

la_url = 'ftp://tgftp.nws.noaa.gov/data/watches_warnings/thunderstorm/la/lac025.txt'

class TestHazards(unittest.TestCase):
    """
    """
    def get_data(self, url):
        with closing(urllib.urlopen(url)) as page:
            txt = page.read()
        return txt

    def test_summary_with_quote(self):
        """
        Should be able to find summaries that contain quote characters.
        """
        hzf = HazardsFile(fixtures.summary_with_quote)

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

        self.assertEqual(hzf[0].ending_time,
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

    def test_hzdump(self):
        with patch('sys.argv', new=['', la_url]):
            with patch('sys.stdout', new=StringIO()):
                commandline.hzdump()

    @unittest.skip('probably do not need')
    def test_thunderstorm(self):
        txt = self.get_data(la_url)
        hz = Hazards(txt)

        expected = ('SEVERE THUNDERSTORM WARNING FOR SOUTHERN FRANKLIN PARISH '
                    'IN NORTHEASTERN LOUISIANA CATAHOULA PARISH IN '
                    'NORTHEASTERN LOUISIANA')
        self.assertEqual(hz.hazard_text, expected)

        self.assertEqual(hz.expires, dt.datetime(2015, 5, 26, 5, 0, 0))
        self.assertEqual(hz.issuance_time, dt.datetime(2015, 5, 26, 4, 15, 0))
        self.assertEqual(hz.polygon,
                         [(92.01, 31.93), (91.91, 31.93), (91.9, 32.0),
                          (91.49, 32.09), (91.58, 31.87), (91.56, 31.73),
                          (91.59, 31.76), (91.64, 31.73), (91.69, 31.74),
                          (91.71, 31.67), (91.82, 31.6), (91.8, 31.49),
                          (91.84, 31.5), (91.87, 31.34), (91.83, 31.27),
                          (91.93, 31.3), (91.95, 31.27), (91.92, 31.23),
                          (91.99, 31.23)])
        expected = ('POLYGON((92.01 31.93, 91.91 31.93, 91.9 32.0, '
                    '91.49 32.09, 91.58 31.87, 91.56 31.73, 91.59 31.76, '
                    '91.64 31.73, 91.69 31.74, 91.71 31.67, 91.82 31.6, '
                    '91.8 31.49, 91.84 31.5, 91.87 31.34, 91.83 31.27, '
                    '91.93 31.3, 91.95 31.27, 91.92 31.23, 91.99 31.23, '
                    '92.01 31.93))')
        self.assertEqual(hz.wkt, expected)

    def test_ga029(self):
        url = 'ftp://tgftp.nws.noaa.gov/data/watches_warnings/tornado/ga/gac029.txt'
        txt = self.get_data(url)
        hz = Hazards(txt)
        self.assertEqual(hz.expires, dt.datetime(2014, 8, 1, 20, 0, 0))

        expected = ('TORNADO WARNING FOR PORTIONS OF LIBERTY COUNTY IN '
                    'SOUTHEAST GEORGIA BRYAN COUNTY IN SOUTHEAST GEORGIA '
                    'MCINTOSH COUNTY IN SOUTHEAST GEORGIA')
        self.assertEqual(hz.hazard_text, expected)

        self.assertEqual(hz.issuance_time, dt.datetime(2014, 8, 1, 19, 18, 0))
        self.assertEqual(hz.polygon,
                         [(81.35, 31.59), (81.39, 31.67), (81.22, 31.74),
                          (81.19, 31.72), (81.17, 31.71), (81.15, 31.69),
                          (81.13, 31.66), (81.13, 31.63), (81.13, 31.62),
                          (81.14, 31.6)])
        expected = ('POLYGON((81.35 31.59, 81.39 31.67, 81.22 31.74, '
                    '81.19 31.72, 81.17 31.71, 81.15 31.69, 81.13 31.66, '
                    '81.13 31.63, 81.13 31.62, 81.14 31.6, 81.35 31.59))')
        self.assertEqual(hz.wkt, expected)


if __name__ == '__main__':
    unittest.main()
