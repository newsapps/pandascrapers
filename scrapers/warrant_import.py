"""
Example showing how to use intermediate database to import complex
data from a screen scraper.

Imports Cook County, Ill. criminal warrants into PANDA by scraping
HTML pages provided on Sherriff's department website. Stores data
in intermediate SQLite database.

Based on Django-based scraper written by the Chicago Tribune Apps
team.
"""
import json
import requests
import json
from string import lowercase
from lxml.html import parse
from lxml.etree import dump
from lxml.cssselect import CSSSelector
from cStringIO import StringIO
from urlparse import urljoin
import re
import sqlite3
import locale
import os

locale.setlocale(locale.LC_NUMERIC, 'en_US')
BASE_SEARCH_URL = 'http://www4.cookcountysheriff.org/locatename.asp'
PANDA_API = 'http://panda.tribapps.com/api/1.0/'
PANDA_SLUG = 'cook_county_warrants'

class WarrantImportError(Exception):
    def __str__(self):
        return "PANDA_AUTH_EMAIL and PANDA_AUTH_KEY environment variables must be set."

class WarrantImporter():
    def __init__(self):
        if not os.environ.get('PANDA_AUTH_EMAIL') and not os.environ.get('PANDA_AUTH_KEY'):
            raise WarrantImportError   
        else:
            self.auth_params = {
                'email': os.environ['PANDA_AUTH_EMAIL'],
                'api_key': os.environ['PANDA_AUTH_KEY'],
            }

        self.conn = sqlite3.connect('warrants.sqlite3')
        self.cur = self.conn.cursor()
        warrant_sql = """CREATE TABLE IF NOT EXISTS warrants (
            number text unique,
            issue_date date,
            type text,
            offense text,
            bail_amount text,
            fugitive text,
            FOREIGN KEY(fugitive) REFERENCES fugitives(detail_url)
        );"""
        self.cur.execute(warrant_sql)
        self.conn.commit()

        panda_url = "%s/dataset/%s/" % (PANDA_API, PANDA_SLUG)
        req = requests.get(panda_url, params=self.auth_params)
        if (req.status_code == 404):
            meta = {
                'name' : 'Cook County criminal warrants',
                'description' : 'Cook County criminal warrants from http://www4.cookcountysheriff.org/locatename.asp',
            }
            params = {
                'columns': 'name,dob,sex,race,address,warrant_number,issue_date,type,offense,bail_amount',
                'column_types':'unicode,date,unicode,unicode,unicode,unicode,date,unicode,unicode,int',
                'typed_columns' : 'true,false,false,false,false,false,true,true,true,true'
            }
            params.update(self.auth_params)
            req = requests.put(panda_url, json.dumps(meta), params=params, headers={ 'Content-Type' : 'application/json' } )


    ## Main importer
    def warrant_import(self):
        # Get fugitives by alpha search
        urls = self.fetch_detail_urls()

        for detail_url, count in urls.items():
            document = self.document_from_url(detail_url)
            fugitive = self.create_fugitive_from_page(document, detail_url)
            self.update_warrants(fugitive, document)


    def update_warrants(self, fugitive, document):
        panda_url = "%s/dataset/%s/data/" % (PANDA_API, PANDA_SLUG)
        tables = document.xpath(CSSSelector('table').path)
        if len(tables) != 2:
            raise Exception("Expected two tables")

        warrant_table = tables[1]
        rows = warrant_table.xpath('tr')

        if len(rows) % 6 != 0:
            raise Exception("Warrant table isn't evenly divisible into sets of six rows.")

        for start in range(0, len(rows), 6):
            warrant_number = rows[start][-1].text
            issue_date = rows[start+1][-1].text
            issue_date = issue_date.split('/')
            issue_date = '%s-%s-%s' % (issue_date[2],issue_date[0],issue_date[1])
            type = rows[start+2][-1].text.strip()
            offense = rows[start+3][-1].text.strip()
            try:
                bail_amount = locale.atof(rows[start+4][-1].text.strip()[1:])
            except ValueError:
                bail_amount = None # No bond

            sql = "SELECT number FROM warrants WHERE number='%s'" % warrant_number
            warrant = self.cur.execute(sql).fetchone()

            if warrant is None:
                warrant = (warrant_number, issue_date, type, offense, bail_amount, fugitive[0])
                sql = "INSERT INTO warrants (number, issue_date, type, offense, bail_amount, fugitive) VALUES ('%s', '%s', '%s', '%s', '%s', '%s')" % warrant
                self.cur.execute(sql)
                self.conn.commit()

                print "New warrant for %s, %s | #: %s, Date: %s, Type: %s, Offense: %s, Amount: %s" % (fugitive[1], fugitive[2], warrant_number, issue_date, type, offense, bail_amount)

                panda_data = {
                    'objects' : [{
                        'external_id': "%s-%s" % (warrant[0], fugitive[1].replace(',', '-')),
                        'data': fugitive[1:7] + warrant[0:5]
                    }]
                }
                req = requests.put(panda_url, json.dumps(panda_data), params=self.auth_params, headers={ 'Content-Type' : 'application/json' })

    def create_fugitive_from_page(self, document, url):
        """
        Scrape HTML for fugitive info
        """
        tables = document.xpath(CSSSelector("table").path)

        if len(tables) != 2:
            print dump(tables[0])
            raise Exception("Expected two tables on detail page [%s]" % url)

        personal = tables[0]
        name, sex, race, dob, addr, junk = personal.xpath( CSSSelector('tr').path )
        name = name.xpath('td')[-1].text.strip()
        sex = sex.xpath('td')[-1].text.strip()
        race = race.xpath('td')[-1].text.strip()
        addr = addr.xpath('td')[-1].text.strip()
        dob = dob.xpath('td')[-1].text.strip()
        m,d,y = dob.split("/")
        dob = "%s-%s-%s" % (y,m,d)
        fugitive = (url, name, dob, sex, race, addr)
        return fugitive


    def fetch_detail_urls(self):
        """
        Fetch URLs for all fugitives by searching for 'a', 'b', etc
        and extracting links from result pages.
        """
        urls_seen = {}

        for letter in lowercase:
            params= { 'LastName': letter }
            response = requests.post(BASE_SEARCH_URL,params)

            if response.ok:
                print "Fetched '%s' pages" % letter
                document = parse(StringIO(response.content))

                for link in document.xpath(CSSSelector('tr td a').path):
                    if link.attrib['href'].startswith('wanted.asp'):
                        url = urljoin(BASE_SEARCH_URL,link.attrib['href'])
                        url = re.sub('\s+&dob', '&dob', url)
                        url = url.strip()
                        url = url.replace('"','')
                        url = url.replace(' ','%20')

                        try:
                            urls_seen[url] += 1
                        except KeyError:
                            urls_seen[url] = 1
            else:
                response.raise_for_status()

        return urls_seen


    def document_from_url(self, url):
        """
        Create document from a URL
        """
        response = requests.get(url)

        if response.ok:
            return parse(StringIO(response.content))

        response.raise_for_status()

if __name__ == '__main__':
    importer = WarrantImporter()
    importer.warrant_import()
