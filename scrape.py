from os import environ, remove
environ['SCRAPERWIKI_DATABASE_NAME'] = 'sqlite:///data.sqlite'
import scraperwiki
import requests
from lxml import html
import re
import csv

OECD_STATS_URL="https://stats.oecd.org/"
CRS_URL="https://stats.oecd.org/viewhtml.aspx?datasetcode=CRS1&lang=en"
CRS_CODES_URL="https://stats.oecd.org/ModalDimWebTree.aspx?DimensionCode=SECTOR&SubSessionId={}&Random=0.2017416214402572"

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
req = s.get(OECD_STATS_URL)
req_crs = s.get(CRS_URL)
doc = html.fromstring(req_crs.text)
jssid = doc.xpath('//input[@name="_ctl0:_ctl0:cphCentre:ContentPlaceHolder1:TBSubSessionId"]')[0].get('value')
req_crs_codes=s.get(CRS_CODES_URL.format(jssid))
doc_crs_codes = html.fromstring(req_crs_codes.text)

class CodesGetter():
    def __init__(self, doc):
        self.doc = doc
        self.top_categories = self.doc.xpath('//div[@id="M_WebTreeDimMembers_1_1"]')[0].xpath("*")
        self.codes = []
        self.iterate_categories(self.top_categories, level=1)

    def clean_name(self, name_text):
        match = re.match("(\d*): (\w*\.\d*\.\w*\.) (.*), Total", name_text)
        if match:
            return match.groups()[2]
        match = re.match("(\d*): (\w*\.?\d*\.) (.*), Total", name_text)
        if match:
            return match.groups()[2]
        match = re.match("(\d*): (.*), Total", name_text)
        return match.groups()[1]

    def clean_sector_name(self, name_text):
        match = re.match("(\d*): (.*)", name_text)
        return match.groups()[1]

    def get_relevant_parent(self, level, parent2_code, parent3_code, highest=True):
        if level == 5:
            if highest:
                return parent3_code
            return parent2_code
        else:
            return parent2_code

    def iterate_categories(self, categories, level, parent_code={}, parent2_code={}, parent3_code={}):
        if parent2_code != {}:
            parent3_code = parent2_code
        if parent_code != {}:
            parent2_code = parent_code
        for category in categories:
            title = category.get("title")
            igtag = category.get("igtag")
            if title == None: continue
            category_id = "M_{}".format(category.get("id"))
            child_categories = self.doc.xpath("//div[@id='{}']/div".format(category_id))
            parent_code = {'code': igtag, 'name': title}
            if len(child_categories)>0:
                self.iterate_categories(child_categories, level+1, parent_code, parent2_code, parent3_code)
            else:
                relevant_parent = self.get_relevant_parent(level, parent2_code, parent3_code)
                category = self.get_relevant_parent(level, parent2_code, parent3_code, False)
                self.codes.append({
                    'group_code': relevant_parent.get('code'),
                    'group_name': self.clean_name(relevant_parent.get('name')),
                    'category_code': category.get('code'),
                    'category_name': self.clean_name(category.get('name')),
                    'code': igtag,
                    'name': self.clean_sector_name(title),
                })

def run():
    codes_groups = CodesGetter(doc_crs_codes).codes
    with open("sectors_groups.csv", 'w') as csv_f:
        csvwriter = csv.DictWriter(csv_f, fieldnames=[
            'group_code', 'group_name',
            'category_code', 'category_name',
            'code', 'name'
        ])
        csvwriter.writeheader()
        for code in codes_groups:
            csvwriter.writerow(code)
        scraperwiki.sqlite.save(unique_keys=['code'], data=codes_groups)

run()
