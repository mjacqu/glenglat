from load import glenglat


def test_submission_files_are_current() -> None:
  """Submission files are current (not changed by glenglat.write_submission)."""
  # Read current file contents
  files = [
    glenglat.README_PATH,
    glenglat.SUBMISSION_DATAPACKAGE_PATH,
    glenglat.SUBMISSION_SPREADSHEET_PATH
  ]
  bytes = [file.read_bytes() for file in files]
  # Update submission files
  glenglat.write_submission()
  # Compare to old file contents and restore
  changed = []
  for file, old in zip(files, bytes):
    new = file.read_bytes()
    if new != old:
      changed.append(str(file))
      file.write_bytes(old)
  if changed:
    raise AssertionError(f"glenglat.write_submission would make changes: {changed}")
