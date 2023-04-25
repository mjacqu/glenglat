from pathlib import Path
import sys

import frictionless


# Load arguments
data_basepath = sys.argv[1]
package_path = 'contribute/datapackage.yaml'
if len(sys.argv) > 2 and sys.argv[2]:
  package_path = sys.argv[2]

# Inject basepath into resource paths
package = frictionless.Package(package_path)
detector = frictionless.Detector(schema_sync=True)
for resource in package.resources:
  resource.basepath = data_basepath
  resource.path = Path(resource.path).name
  resource.detector = detector

# Validate and report
report = frictionless.validate(package)
print(report.to_summary())
