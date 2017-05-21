#!/usr/bin/python3

# Copyright (C) 2017  Christopher Blay <chris.b.blay@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

'Scrapes rent information about apartments from multiple configured buildings.'

from __future__ import (absolute_import, division, generators, nested_scopes,
                        print_function, unicode_literals, with_statement)

import argparse
import collections
import csv
import json
import re
import sys
import time

import requests

_HEADERS = {
    'user-agent':
        'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
}

class Apartment(object):
    'Information about an apartment.'

    def __init__(self, unit, rent, size, beds):
        self.unit = unit
        self.rent = rent
        self.size = size
        self.beds = beds

    @property
    def per_sq_ft(self):
        'Rent per square foot.'
        return self.rent / self.size

    def __str__(self):
        return ('Unit {0.unit}: rent={0.rent} size={0.size} beds={0.beds}'
                ' per_sq_ft={0.per_sq_ft}'.format(self))

class Avalon(object):
    'Scrapes apartment information for an Avalon building.'

    _URL_TEMPLATE = ('https://api.avalonbay.com/json/reply/ApartmentSearch?'
                     'communityCode={}&_={}')

    def __init__(self, name, community_code):
        self.name = name
        self._community_code = community_code

    @property
    def _url(self):
        return self._URL_TEMPLATE.format(self._community_code,
                                         int(time.time() * 1000))

    @property
    def apartments(self):
        'Yields apartments for this building.'
        info = requests.get(self._url, headers=_HEADERS).json()
        for available_floor_plan_type in \
                info['results']['availableFloorPlanTypes']:
            beds = int(available_floor_plan_type['floorPlanTypeCode'][0])
            for available_floor_plan in \
                    available_floor_plan_type['availableFloorPlans']:
                size = available_floor_plan['estimatedSize']
                for finish_package in available_floor_plan['finishPackages']:
                    for apartment in finish_package['apartments']:
                        yield Apartment(apartment['apartmentNumber'],
                                        apartment['pricing']['effectiveRent'],
                                        size, beds)

class Equity(object):
    'Scrapes apartment information for an Equity building.'

    _INFO_PATTERN = re.compile(
        r'^ *[a-z0-5]+\.unitAvailability = (?P<info>\{.*\})')
    _URL_TEMPLATE = 'http://www.equityapartments.com/{}'

    def __init__(self, name, url_path):
        self.name = name
        self._url_path = url_path

    @property
    def _info(self):
        for line in requests.get(self._url, headers=_HEADERS).text.split('\n'):
            match = self._INFO_PATTERN.search(line)
            if match:
                return json.loads(match.group('info'))
        print('Unable to get info from {}'.format(self._url))

    @property
    def _url(self):
        return self._URL_TEMPLATE.format(self._url_path)

    @property
    def apartments(self):
        'Yields apartments for this building.'
        for bedroom_type in self._info['BedroomTypes']:
            for available_unit in bedroom_type['AvailableUnits']:
                yield Apartment(available_unit['UnitId'],
                                available_unit['BestTerm']['Price'],
                                available_unit['SqFt'],
                                bedroom_type['BedroomCount'])

BUILDINGS = [
    Avalon('Avalon Mission Bay', 'CA067'),
    Avalon('Avalon San Bruno', 'CA583'),
    Equity('La Terraza', 'san-francisco-bay/colma/la-terrazza-apartments'),
    Equity(
        'South City Station',
        'san-francisco-bay/south-san-francisco/south-city-station-apartments'),
]

def _check_beds(args):
    if (args.min_beds is not None and args.max_beds is not None
            and args.min_beds > args.max_beds):
        sys.exit('Error! min_beds={} is greater than max_beds={}'.format(
            args.min_beds, args.max_beds))

def _maybe_print_buildings(args):
    if args.buildings:
        print('# Buildings')
        for building in BUILDINGS:
            print(building.name)
        sys.exit()

def main():
    'Main method for this script.'
    parser = argparse.ArgumentParser(
        description='Scrapes current rental information'
                    ' for configured buildings')
    parser.add_argument('--min_beds', type=int, help='minimum number of beds')
    parser.add_argument('--max_beds', type=int, help='maximum number of beds')
    parser.add_argument('-b', '--buildings', action='store_true',
                        help='show configured buildings and exit')
    parser.add_argument('--csv', action='store_const', const=csv.DictWriter(
        sys.stdout, ('timestamp', 'bldg', 'unit', 'rent', 'size', 'beds')),
                        help='output in CSV format. omits mean rent per apt '
                             'size. does not apply to `--buildings`')
    parser.add_argument('building', nargs='*',
                        help='zero or more buildings to scrape. specifying no'
                             ' buildings scrapes all configured buildings')
    args = parser.parse_args()
    _maybe_print_buildings(args)
    _check_beds(args)
    for building in BUILDINGS:
        if args.building and building.name not in args.building:
            continue
        if not args.csv:
            print('# {}'.format(building.name))
            by_size = collections.defaultdict(list)
        else:
            timestamp = int(time.time())
        for apartment in sorted(building.apartments, key=lambda x: x.unit):
            if args.min_beds is not None and args.min_beds > apartment.beds:
                continue
            if args.max_beds is not None and args.max_beds < apartment.beds:
                continue
            if args.csv:
                args.csv.writerow(dict(
                    timestamp=timestamp, bldg=building.name, **vars(apartment)))
            else:
                print(apartment)
                by_size[apartment.size].append(apartment.rent)
        if args.csv:
            continue
        for size in sorted(by_size.keys()):
            print('Size {}: {}'.format(
                size, sum(by_size[size]) / len(by_size[size]) / size))
        print()

if __name__ == '__main__':
    main()
