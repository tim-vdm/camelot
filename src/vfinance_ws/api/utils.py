import decimal
import json


def to_table_html(document):
    TD_TEMPLATE = u"<td>{0}</td>"
    TR_TEMPLATE = u"<tr>{0}</tr>"
    TABLE_TEMPLATE = u"<table>{0}</table>"

    lines = []
    for k, v in document.iteritems():
        lines.append(
            TR_TEMPLATE.format(u''.join([TD_TEMPLATE.format(k),
                                         TD_TEMPLATE.format(unicode(v))]))
        )
    return TABLE_TEMPLATE.format(u''.join(lines))


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        return super(DecimalEncoder, self).default(o)
