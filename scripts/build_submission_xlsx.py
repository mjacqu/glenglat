import datetime
from pathlib import Path

import frictionless
import jinja2
import tablecloth.excel


package = frictionless.Package('submission/datapackage.yaml').to_dict()


# ---- Render column comments ----

path = Path(__file__).parent / 'comment.txt.jinja'
template = jinja2.Template(path.read_text())
comments = {
  resource['name']: [
    template.render(**field).strip().replace('\n\n\n', '\n\n')
    for field in resource['schema']['fields']
  ]
  for resource in package['resources']
}


# ---- Render spreadsheet ----
# Excel file is written without a timestamp to avoid spurious changes

book = tablecloth.excel.write_template(
  package,
  path=None,
  header_comments=comments,
  format_comments={'font_size': 11, 'x_scale': 3, 'y_scale': 4}
)
book.set_properties({'created': datetime.datetime(2000, 1, 1)})
book.filename = 'submission/template.xlsx'
book.close()
