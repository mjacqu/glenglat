import os
from pathlib import Path

import frictionless
import jinja2


class RelativeEnvironment(jinja2.Environment):
  """Override join_path() to enable relative template paths."""

  def join_path(self, template, parent):
    return os.path.normpath(os.path.join(os.path.dirname(parent), template))


def render_template(path: str, data: dict, encoding: str = "utf-8") -> str:
  dir = os.path.dirname(os.path.abspath(path))
  file = os.path.split(path)[1]
  environment = RelativeEnvironment(
    loader=jinja2.FileSystemLoader(dir, encoding=encoding),
    lstrip_blocks=True,
    trim_blocks=True,
  )
  template = environment.get_template(file)
  return template.render(**data)


# ---- Render template ----

package = frictionless.Package('contribute/datapackage.yaml')
docs = render_template(Path(__file__).parent / 'package.md.jinja', {'package': package})


# ---- Inject into README.md ----
# Between <!-- <contributor-format> --> and <!-- </contributor-format> -->

start = '<!-- <contributor-format> -->'
end = '<!-- </contributor-format> -->'
path = Path('README.md')
text = path.read_text()
start_index = text.index(start) + len(start)
end_index = text.index(end)
text = text[:start_index] + '\n' + docs.strip() + '\n' + text[end_index:]
path.write_text(text)
