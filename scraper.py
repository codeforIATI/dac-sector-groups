import os
os.environ['SCRAPERWIKI_DATABASE_NAME'] = 'sqlite:///data.sqlite'
import scraperwiki  # noqa: E402
import requests  # noqa: E402
from lxml import html  # noqa: E402
import re  # noqa: E402
import csv  # noqa: E402

OECD_STATS_URL = "https://stats.oecd.org/"
CRS_URL = "https://stats.oecd.org/viewhtml.aspx?datasetcode=CRS1&lang={}"
CRS_CODES_URL = "https://stats.oecd.org/ModalDimWebTree.aspx?DimensionCode=SECTOR&SubSessionId={}&Random=0.2017416214402572"


class CodesGetter():
    def get_doc(self):
        s = requests.Session()
        s.headers.update({'User-Agent': 'Mozilla/5.0'})
        s.get(OECD_STATS_URL)
        req_crs = s.get(CRS_URL.format(self.lang))
        doc = html.fromstring(req_crs.text)
        jssid = doc.xpath('//input[@name="_ctl0:_ctl0:cphCentre:ContentPlaceHolder1:TBSubSessionId"]')[0].get('value')
        req_crs_codes = s.get(CRS_CODES_URL.format(jssid))
        doc_crs_codes = html.fromstring(req_crs_codes.text)
        return doc_crs_codes

    def __init__(self, lang='en'):
        self.lang = lang
        self.doc = self.get_doc()
        self.top_categories = self.doc.xpath('//div[@id="M_WebTreeDimMembers_1_1"]')[0].xpath("*")
        self.codes = []
        self.iterate_categories(self.top_categories, level=1)

    def clean_name(self, name_text):
        match = re.match(r"(\d*): (\w*\.\d*\.\w*\.) (.*), Total", name_text)
        if match:
            return match.groups()[2]
        match = re.match(r"(\d*): (\w*\.?\d*\.) (.*), Total", name_text)
        if match:
            return match.groups()[2]
        match = re.match(r"(\d*): (.*), Total", name_text)
        return match.groups()[1]

    def clean_sector_name(self, name_text):
        match = re.match(r"(\d*): (.*)", name_text)
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
            if title is None:
                continue
            category_id = "M_{}".format(category.get("id"))
            child_categories = self.doc.xpath("//div[@id='{}']/div".format(category_id))
            parent_code = {'code': igtag, 'name': title}
            if len(child_categories) > 0:
                self.iterate_categories(child_categories, level+1, parent_code, parent2_code, parent3_code)
            else:
                relevant_parent = self.get_relevant_parent(level, parent2_code, parent3_code)
                category = self.get_relevant_parent(level, parent2_code, parent3_code, False)
                self.codes.append({
                    'group_code': relevant_parent.get('code'),
                    'group_name': self.clean_name(relevant_parent.get('name')),
                    'category_code': category.get('code'),
                    'category_name': self.clean_name(category.get('name')),
                    'sector_code': igtag,
                    'sector_name': self.clean_sector_name(title),
                })


def run():
    print("Running scraper...")
    print("Retrieving FR codes...")
    codes_groups_fr = CodesGetter(lang='fr').codes
    dict_groups_fr = dict(map(lambda code: (code['sector_code'], code), codes_groups_fr))
    print("Retrieved FR codes.")
    print("Retrieving EN codes...")
    codes_groups = CodesGetter().codes
    print("Retrieved EN codes.")
    print("Writing output...")
    os.makedirs("output", exist_ok=True)
    with open(os.path.join("output", "sectors_groups.csv"), 'w') as csv_f:
        csvwriter = csv.DictWriter(csv_f, fieldnames=[
            'group_code', 'group_name_en', 'group_name_fr',
            'category_code', 'category_name_en',
            'category_name_fr',
            'code', 'name_en',
            'name_fr'
        ])
        csvwriter.writeheader()
        for code in codes_groups:
            code_fr = dict_groups_fr[code['sector_code']]
            row = {
                'group_code': code['group_code'],
                'group_name_en': code['group_name'],
                'group_name_fr': code_fr['group_name'],
                'category_code': code['category_code'],
                'category_name_en': code['category_name'],
                'category_name_fr': code_fr['category_name'],
                'code': code['sector_code'],
                'name_en': code['sector_name'],
                'name_fr': code_fr['sector_name']
            }
            csvwriter.writerow(row)
        if os.environ.get("GITHUB_PAGES", False) is False:
            scraperwiki.sqlite.save(unique_keys=['sector_code'], data=codes_groups)
    print("Done")


run()
