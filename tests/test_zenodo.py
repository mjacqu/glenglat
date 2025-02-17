import pytest

import frictionless
import zenodo


@pytest.mark.slow
def test_renders_zenodo_metadata() -> None:
  """Zenodo metadata renders successfully."""
  zenodo.render_zenodo_metadata()


@pytest.mark.slow
def test_builds_valid_datapackage() -> None:
  """Glenglat release builds successfully."""
  zip_path = zenodo.build_for_zenodo()
  unzipped_path = zip_path.with_suffix('')
  # Validate package (slow)
  report = frictionless.validate(unzipped_path.joinpath('datapackage.json'))
  assert report.valid, report.to_summary()
