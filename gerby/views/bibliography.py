from flask import render_template

from gerby.application import app
from gerby.database import *
import re

# Helper function to remove HTML tags for sorting purposes
def strip_html(text):
    """Removes HTML tags from a string."""
    if not text:
        return ""
    # Basic regex, sufficient if author HTML is just simple <a> tags
    # Consider libraries like BeautifulSoup for more complex/nested HTML
    return re.sub('<[^>]*>', '', text).strip()

def reformatHowPublished(howpublished_field):
    if (len(re.findall(r"\\url",howpublished_field)) >= 1):
        howpublished_field = re.sub(r"\\url ","",howpublished_field)
        howpublished_field = re.sub("&amp;","&",howpublished_field)
        howpublished_field = re.sub("<span class=\"bibtex-protected\">(.*?)</span>","\g<1>",howpublished_field)
        return howpublished_field
    else:
        return howpublished_field

def reformatNote(note_field):
    if (len(re.findall(r"\\url",note_field)) >= 1):
        note_field = re.sub("&amp;","&",note_field)
        note_field = re.sub(r"\\url ","",note_field)
        note_field = re.sub("<span class=\"bibtex-protected\">(.*?)</span>","\g<1>",note_field)
        return note_field
    else:
        return note_field

def reformatAuthors(author_field, oxford_comma_on=False):
    # Split the authors on ' and '
    authors = author_field.split(" and ")

    # Reformat each author name
    reformatted_authors = []
    for author in authors:
        # Split the last name and first name and reverse them if they exist
        parts = author.split(", ")
        if len(parts) == 2:
            reformatted_author = " ".join(parts[::-1])
        else:
            reformatted_author = parts[0]
        reformatted_authors.append(reformatted_author)

    # Join the reformatted author names with ', ' and 'and' for the last author
    # Include Oxford comma if specified and if there are more than two authors
    if len(reformatted_authors) > 2:
        reformatted_author_field = ", ".join(reformatted_authors[:-1])
        reformatted_author_field += ", and " if oxford_comma_on else " and "
        reformatted_author_field += reformatted_authors[-1]
    elif len(reformatted_authors) == 2:
        reformatted_author_field = " and ".join(reformatted_authors)
    else:
        reformatted_author_field = reformatted_authors[0]

    return reformatted_author_field

def decorateEntries(entries):
  for entry in entries:
    fields = BibliographyField.select().where(BibliographyField.key == entry.key)
    # make the fields accessible in Jinja
    for field in fields:
      if field.field == "author":
        setattr(entry, 'original_author', field.value)
        updated_author = reformatAuthors(field.value)
        setattr(entry, field.field, updated_author)
      else:
        setattr(entry, field.field, field.value)

  return entries

@app.route("/bibliography")
def show_bibliography():
  entries_query = BibliographyEntry.select() # Get the query
  # Execute query and get list, then decorate
  entries_list = decorateEntries(list(entries_query))

  # Sort the list of decorated entry objects using the correct key
  # The key uses the 'author' attribute (set by decorateEntries),
  # strips HTML, and lowercases it for proper sorting.
  # getattr(entry, 'author', '') handles cases where author might be missing.
  entries_sorted = sorted(
      entries_list,
      key=lambda entry: strip_html(getattr(entry, 'author', '')).lower()
  )

  return render_template("bibliography.overview.html", entries=entries_sorted)

@app.route("/bibliography/<string:key>")
def show_entry(key):
  try:
    entry = BibliographyEntry.get(BibliographyEntry.key == key)
  except BibliographyEntry.DoesNotExist:
    return render_template("bibliography.notfound.html", key=key), 404

  # Decorate the single entry to get fields like author etc.
  # We can reuse decorateEntries by passing a list containing the single entry
  decorated_entry_list = decorateEntries([entry])
  if not decorated_entry_list: # Should not happen if entry exists
      return "Error decorating entry", 500
  entry = decorated_entry_list[0] # Get the decorated entry back

  # Populate entry.fields dictionary (as the template seems to expect it)
  entry.fields = {}
  db_fields = BibliographyField.select().where(BibliographyField.key == entry.key)
  for field in db_fields:
    if field.field == "author":
        # Use the already reformatted author from the decorated entry object
        entry.fields[field.field] = getattr(entry, 'author', '') # Use reformatted version
    elif field.field == "howpublished":
        entry.fields[field.field] = reformatHowPublished(field.value)
    elif field.field == "note":
        entry.fields[field.field] = reformatNote(field.value)
    else:
        entry.fields[field.field] = field.value

  # --- Find Neighbours ---
  # Fetch all entries, decorate, and sort them *by author* to find neighbours correctly
  all_entries_query = BibliographyEntry.select()
  all_entries_list = decorateEntries(list(all_entries_query))
  all_entries_sorted = sorted(
      all_entries_list,
      key=lambda e: strip_html(getattr(e, 'author', '')).lower()
  )

  index = -1
  for i, sorted_entry in enumerate(all_entries_sorted):
    # Compare keys, assuming key is the unique identifier
    if getattr(sorted_entry, 'key', None) == entry.key:
      index = i
      break # Found the entry

  neighbours = [None, None]
  if index > 0:
    neighbours[0] = all_entries_sorted[index - 1]
  if index != -1 and index < len(all_entries_sorted) - 1:
    neighbours[1] = all_entries_sorted[index + 1]
  # --- End Find Neighbours ---


  # --- Citations ---
  citations_query = Citation.select().where(Citation.key == entry.key)
  # Decide how citations should be sorted (e.g., by tag or location)
  # Assuming Citation object has relevant attributes like 'tag' or can be sorted by default
  citations = sorted(list(citations_query)) # Using default sort for citations for now
  # --- End Citations ---


  return render_template("bibliography.entry.html",
                         entry=entry, # Pass the decorated entry
                         neighbours=neighbours,
                         citations=citations)
