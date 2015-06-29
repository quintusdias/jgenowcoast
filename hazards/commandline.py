from contextlib import closing
import argparse
import urllib

#from . import Hazards
#
#
#def hzdump():
#    description = 'Print hazards metadata.'
#    parser = argparse.ArgumentParser(description=description)
#
#    parser.add_argument('url')
#
#    args = parser.parse_args()
#    url = args.url
#
#    with closing(urllib.urlopen(url)) as page:
#        txt = page.read()
#
#    hz = Hazards(txt)
#    print(hz)
