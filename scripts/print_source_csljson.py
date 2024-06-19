import json
from typing import Dict

import pandas as pd


def convert_source_to_csl(source: Dict[str, str]) -> dict:
  """
  Convert source to CSL-JSON.

  Names of people are currently represented with their full names only:
  `{"literal": "Name"}`.
  Extracting given and family names could be achieved with the following heuristics,
  depending on the writing system:

  * Latin: Assume last word is the family name
    (e.g. "Jakob F. Steiner" -> {"family": "Steiner", "given": "Jakob F."}).
    Although this assumption is valid in most cases, it is wrong when
    particles (e.g. "Ward J. J. Van Pelt", "Roderik S. W. van de Wal"),
    suffixes (e.g. "E. Calvin Alexander Jr."),
    or double family names ("Guillermo Cobos Campos") are present.
  * Cyrillic: Assume last word of the original and transliteration is the
    family name (e.g. "Н. Г. Разумейко [N. G. Razumeiko]" ->
    {"family": "Иванов [Razumeiko]", "given": "Н. Г. [N. G.]"}).
  * Chinese: Assume first character and word of the original and
    transliteration, respectively, is the family name (e.g. "孙维君 [Sun Weijun]" ->
    "family": "孙 [Sun]", "given": "Weijun [维君]").
  * Hangul: Same as for Chinese (e.g. "안진호 [Ahn Jinho]" ->
    {"family": "안 [Ahn]", "given": "진호 [Jinho]"}).
  """
  csl = {
    'id': source['id'],
    'author': [
      {'literal': author}
      for author in source['author'].split(' | ')
    ],
    'issued': {'date-parts': [[int(source['year'])]]},
    'type': source['type'],
    'title': source['title'],
    'URL': source['url'],
    'language': source['language'],
    'container-title': source['container_title'],
    'volume': source['volume'],
    'issue': source['issue'],
    'page': source['page'],
    'version': source['version'],
    'editor': [
      {'literal': editor}
      for editor in source['editor'].split(' | ')
    ] if source['editor'] else None,
    'collection-title': source['collection_title'],
    'collection-number': source['collection_number'],
    'publisher': source['publisher']
  }
  # Remove None values
  return {key: value for key, value in csl.items() if value is not None}


# ---- Convert source table to CSL-JSON ----

sources = pd.read_csv('data/source.csv', dtype='string').replace({pd.NA: None})
csl = [convert_source_to_csl(source) for source in sources.to_dict(orient='records')]
print(json.dumps(csl, indent=2, ensure_ascii=False))
