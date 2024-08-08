import datetime
from pathlib import Path
import yaml

import frictionless


# Read package metadata
package = frictionless.Package('datapackage.yaml')


# --- Merge tables: source > borehole by source_id ----
FOREIGN_NAME = 'source'
LOCAL_NAME = 'borehole'
OMIT_LOCAL = ['source_id', 'location_origin', 'elevation_origin', 'curator']

local = package.get_resource(LOCAL_NAME)
# Filter local columns
local.schema.fields = [
  field for field in local.schema.fields
  if field.name not in OMIT_LOCAL
]
# Drop foreign table and key
local.schema.foreign_keys = None
package.resources = [
  resource for resource in package.resources
  if resource.name != FOREIGN_NAME
]
# Customize description of borehole.notes
local.schema.get_field('notes').description = (
  'Additional remarks about the study site, the borehole, or the measurements therein. '
  'Literature references should be formatted as `{url}` or `{author} {year} ({url})`.'
)

# Validate metadata
report = frictionless.Package.validate_descriptor(package.to_descriptor())
assert report.valid


# --- Merge tables: profile > measurement by (profile_id, borehole_id) ----
LOCAL_NAME = 'measurement'
OMIT_LOCAL = ['profile_id']
FOREIGN_NAME = 'profile'
OMIT_FOREIGN = ['id', 'borehole_id', 'source_id', 'measurement_origin', 'notes']

local = package.get_resource(LOCAL_NAME)
foreign = package.get_resource(FOREIGN_NAME)
# Drop primary key
local.schema.primary_key = None
# Replace foreign keys with reference to modified borehole table
local.schema.foreign_keys = [{
  'fields': ['borehole_id'],
  'reference': {'resource': 'borehole', 'fields': ['id']}
}]
# Filter local columns
local.schema.fields = [
  field for field in local.schema.fields
  if field.name not in OMIT_LOCAL
]
# Append foreign columns
local.schema.fields += [
  field for field in foreign.schema.fields
  if field.name not in OMIT_FOREIGN
]
# Drop foreign table
package.resources = [
  resource for resource in package.resources
  if resource.name != FOREIGN_NAME
]

# Validate metadata
report = frictionless.Package.validate_descriptor(package.to_descriptor())
assert report.valid


# ---- Adjust schemas ----

# Expand trueValues, falseValue to defaults
for resource in package.resources:
  for field in resource.schema.fields:
    if field.type == 'boolean':
      field.true_values = ['True', 'true', 'TRUE']
      field.false_values = ['False', 'false', 'FALSE']

# Validate metadata
report = frictionless.Package.validate_descriptor(package.to_descriptor())
assert report.valid


# ---- Adjust resources ----

# Strip path prefix
for resource in package.resources:
  if isinstance(resource.path, list):
    path = resource.path[0]
  else:
    path = resource.path
  resource.path = Path(path).name
  resource.extrapaths = None

# Overwrite package metadata
package.name = 'glenglat-submission'
package.description = 'Submission format for the global englacial temperature database.'
package.created = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
package.title = None
package.licenses = None
package.contributors = None
package.keywords = None
package.custom = {}

# Validate metadata
report = frictionless.Package.validate_descriptor(package.to_dict())
assert report.valid


# ---- Write datapackage.yaml ----

def str_presenter(dumper, data):
  """Configures YAML dumping of multiline strings.

  See https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
  """
  if len(data.splitlines()) > 1:
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
  return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

# Write to YAML
# Remove created property to avoid unnecessary changes
obj = package.to_dict()
del obj['created']
yaml.dump(
  obj,
  open('submission/datapackage.yaml', 'w'),
  indent=2,
  encoding='utf-8',
  allow_unicode=True,
  width=float('inf'),
  sort_keys=False
)
