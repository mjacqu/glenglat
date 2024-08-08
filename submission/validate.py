from pathlib import Path
import sys

import frictionless


# Load arguments
data_basepath = sys.argv[1]
package_path = Path(__file__).parent.joinpath('datapackage.yaml')

# Inject basepath into resource paths
package = frictionless.Package(package_path)
detector = frictionless.Detector(schema_sync=True)
for resource in package.resources:
  resource.basepath = data_basepath
  resource.path = Path(resource.path).name
  resource.detector = detector

# Validate and report
report = package.validate()
print(report.to_summary())
