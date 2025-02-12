from glenglat import *


def abbreviate_given_name(name: str) -> str:
  """
  Abbreviate given name.

  Replaces each word (space or hyphen separated) with first letter and period.
  Ignores single letter words, words already ending in a period, or words not in
  Latin or Cyrillic characters.

  Examples
  --------
  >>> abbreviate_given_name('Jane')
  'J.'
  >>> abbreviate_given_name('Jane Doe')
  'J. D.'
  >>> abbreviate_given_name('J. Doe')
  'J. D.'
  >>> abbreviate_given_name('Jane-Doe')
  'J.-D.'
  >>> abbreviate_given_name('J.-Doe')
  'J.-D.'
  >>> abbreviate_given_name('时')
  '时'
  >>> abbreviate_given_name('时银')
  '时银'
  """
  script = infer_script(name)
  return ' '.join(
    '-'.join(
      f"{word[0]}."
      if len(word) > 1 and word[-1] != '.' and script in ('latin', 'cyrillic') else word
      for word in part.split('-')
    )
    for part in name.split(' ')
  )


def render_name_for_essd(name: dict) -> str:
  """
  Render name for ESSD.

  If in Latin or Cyrillic script, renders name as `{family}, {given initials}`.
  """
  given = name['given']
  script = infer_script(name['name'])
  if script in ('latin', 'cyrillic'):
    initials = abbreviate_given_name(given)
    return f"{name['family']}, {initials}"
  return name['name']


def format_author_for_essd(person: dict) -> tuple[dict, str]:
  """
  Format author for ESSD.

  Returns
  -------
  Dictionary with Latin family and given name and an ESSD-rendered name.

  Examples
  --------
  >>> person = parse_person_string('杉山 慎 [Sugiyama Shin]')
  >>> format_author_for_essd(person)
  ({'family': 'Sugiyama', 'given': 'Shin'}, '杉山 慎')
  >>> person = parse_person_string('Emmanuel {Le Meur}')
  >>> format_author_for_essd(person)
  ({'family': 'Le Meur', 'given': 'Emmanuel'}, 'Le Meur, E.')
  """
  key = 'name' if person.get('name') else 'latin'
  return {
    'family': person['latin']['family'],
    'given': person['latin']['given'],
  }, render_name_for_essd(person[key])


def format_authors_for_essd(persons: list[dict]) -> tuple[list[dict], Optional[str]]:
  """
  Format authors for ESSD.

  Returns
  -------
  List of dictionaries with Latin family and given names and an ESSD-rendered name list.

  Examples
  --------
  >>> persons = [parse_person_string('杉山 慎 [Sugiyama Shin]')]
  >>> format_authors_for_essd(persons)
  ([{'family': 'Sugiyama', 'given': 'Shin'}], '杉山 慎')
  >>> persons = [parse_person_string('Emmanuel {Le Meur}')]
  >>> format_authors_for_essd(persons)
  ([{'family': 'Le Meur', 'given': 'Emmanuel'}], None)
  >>> persons = [
  ...   parse_person_string('Emmanuel {Le Meur}'),
  ...   parse_person_string('杉山 慎 [Sugiyama Shin]')
  ... ]
  >>> format_authors_for_essd(persons)[1]
  'Le Meur, E. and 杉山 慎'
  >>> persons = [
  ...   parse_person_string('Emmanuel {Le Meur}'),
  ...   parse_person_string('杉山 慎 [Sugiyama Shin]'),
  ...   parse_person_string('Н. Г. Разумейко [N. G. Razumeiko]')
  ... ]
  >>> format_authors_for_essd(persons)[1]
  'Le Meur, E., 杉山 慎, and Разумейко, Н. Г.'
  """
  results = [format_author_for_essd(person) for person in persons]
  authors = [result[0] for result in results]
  is_latin_only = all(not person.get('name') for person in persons)
  if is_latin_only:
    return authors, None
  names = [result[1] for result in results]
  if len(names) == 1:
    title = names[0]
  elif len(names) == 2:
    title = ' and '.join(names)
  else:
    title = ', '.join(names[:-1]) + ', and ' + names[-1]
  return authors, title


def format_editor_for_essd(person: dict) -> dict:
  """
  Format editor for ESSD.

  Returns
  -------
  Dictionary with either Latin family and given,
  or literal of Latin family, Latin initials, and ESSD-rendered name in parentheses.

  Examples
  --------
  >>> person = parse_person_string('杉山 慎 [Sugiyama Shin]')
  >>> format_editor_for_essd(person)
  {'literal': 'Sugiyama, S. (杉山 慎)'}
  >>> person = parse_person_string('Emmanuel {Le Meur}')
  >>> format_editor_for_essd(person)
  {'family': 'Le Meur', 'given': 'Emmanuel'}
  """
  if person.get('name'):
    title = (
      f"{render_name_for_essd(person['latin'])} "
      f"({render_name_for_essd(person['name'])})"
    )
    return {'literal': title}
  return {
    'family': person['latin']['family'],
    'given': person['latin']['given']
  }


def convert_source_to_csl(source: Dict[str, str]) -> dict:
  """
  Convert source to CSL-JSON (ESSD version).

  Parameters
  ----------
  source
    Dictionary representing a row in the source table.
  """
  # Migrate 'personal-communication' to 'personal_communication'
  # Add a title to personal communications
  source_type = source['type']
  source_title = source['title']
  if source_type == 'personal-communication':
    source_type = 'personal_communication'
    source_title = source_title or 'Personal communication'
  # Format person names
  names = defaultdict(list)
  # Authors
  if source.get('author'):
    strings = source['author'].split(' | ')
    persons = [parse_person_string(string) for string in strings]
    names['author'], names_in_title = format_authors_for_essd(persons)
    if names_in_title:
      source_title = f"({names_in_title}): {source_title}"
  # Editors
  if source.get('editor'):
    strings = source['editor'].split(' | ')
    persons = [parse_person_string(string) for string in strings]
    names['editor'] = [format_editor_for_essd(person) for person in persons]
  # Use DOI instead of URL if available
  doi = None
  if source['url'] and source['url'].startswith('https://doi.org/'):
    doi = source['url'].replace('https://doi.org/', '')
  csl = {
    'id': source['id'],
    'citation-key': source['id'],
    'author': names['author'],
    'issued': {'date-parts': [[int(source['year'])]]},
    'type': source_type,
    'title': source_title,
    'DOI': doi,
    'URL': None if doi else source['url'],
    'language': source['language'],
    'container-title': source['container_title'],
    'volume': source['volume'],
    'issue': source['issue'],
    'page': source['page'],
    'version': source['version'],
    'editor': names['editor'],
    'collection-title': source['collection_title'],
    'collection-number': source['collection_number'],
    'publisher': source['publisher']
  }
  csl['note'] = f"Citation key: {source['id']}"
  # Keep only truthy values
  return {key: value for key, value in csl.items() if value}


def render_sources_as_csl() -> str:
  """Render sources as CSL-JSON."""
  sources = pd.read_csv(DATA_PATH.joinpath('source.csv'), dtype='string')
  sources.replace({pd.NA: None}, inplace=True)
  csl = [
    convert_source_to_csl(source)
    for source in sources.to_dict(orient='records')
  ]
  return json.dumps(csl, indent=2, ensure_ascii=False)


# Generate command line interface
if __name__ == '__main__':
  fire.Fire()
