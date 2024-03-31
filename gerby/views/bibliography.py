from flask import render_template

from gerby.application import app
from gerby.database import *
import re, time

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
        updated_author = reformatAuthors(field.value)
        setattr(entry, field.field, updated_author)
      else:
        setattr(entry, field.field, field.value)

  return entries

@app.route("/bibliography")
def show_bibliography():
  entries = BibliographyEntry.select()
  entries = decorateEntries(entries)
  entries = sorted(entries)

  return render_template("bibliography.overview.html", entries=entries)

@app.route("/bibliography/<string:key>")
def show_entry(key):
  try:
    entry = BibliographyEntry.get(BibliographyEntry.key == key)
  except BibliographyEntry.DoesNotExist:
    return render_template("bibliography.notfound.html", key=key), 404


  fields = BibliographyField.select().where(BibliographyField.key == entry.key)
  entry.fields = dict()
  for field in fields:
    if field.field == "author":
        updated_author = reformatAuthors(field.value)
        entry.fields[field.field] = updated_author
    if field.field == "howpublished":
        updated_howpublished = reformatHowPublished(field.value)
        entry.fields[field.field] = updated_howpublished
    if field.field == "note":
        updated_note = reformatNote(field.value)
        entry.fields[field.field] = updated_note
    else:
        entry.fields[field.field] = field.value

  # it's too unpleasant to sort in SQL so we do it here, but the result might be a bit slow
  entries = BibliographyEntry.select()
  entries = decorateEntries(entries) # we need the author field to be present for sorting to work...
  entries = sorted(entries)

  index = -1
  for i in range(len(entries)):
    if entries[i].key == entry.key:
      index = i

  neighbours = [None, None]
  if index > 0:
    neighbours[0] = entries[index-1]
  if index < len(entries) - 1:
    neighbours[1] = entries[index+1]

  citations = Citation.select().where(Citation.key == entry.key)
  citations = sorted(citations)

  return render_template("bibliography.entry.html",
                         entry=entry,
                         neighbours=neighbours,
                         citations=citations)
