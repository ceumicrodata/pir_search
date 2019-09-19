import attr
import datetime
import json
from typing import Set


@attr.s(auto_attribs=True)
class PirDetails:
    pir: str = None
    tax_id: str = None
    start_date: datetime.date = None
    end_date: datetime.date = None
    names: Set[str] = attr.Factory(set)
    settlements: Set[str] = attr.Factory(set)

    def is_valid_at(self, date: datetime.date) -> bool:
        born_later = self.start_date and self.start_date > date
        died_earlier = self.end_date and self.end_date < date
        return not (born_later or died_earlier)


def load_pir_to_details(path):
    with open(path) as f:
        raw_pir_to_details = json.load(f)

    def make_pir_details(details_dict):
        d = dict(details_dict)
        def todate(d, key):
            if d[key]:
                d[key] = datetime.date.fromisoformat(d[key])
        todate(d, 'start_date')
        todate(d, 'end_date')
        def convert(d, key, type):
            d[key] = type(d[key])
        convert(d, 'pir', int)
        convert(d, 'settlements', set)
        convert(d, 'names', set)
        return PirDetails(**d)

    pir_to_details = {
        int(k): make_pir_details(v)
        for k, v in raw_pir_to_details.items()}

    return pir_to_details
