import markdown
from mdx_bleach.extension import BleachExtension
from mdx_bleach.whitelist import ALLOWED_TAGS
from mdx_bleach.whitelist import ALLOWED_ATTRIBUTES
from mdx_math import MathExtension

from gerby.database import *
import os

def load_ancestors():
    """
    Loads the tag ancestor JSON file once and converts it into an efficient
    {child_tag_id: parent_tag_id} map.
    """
    ancestor_map = {}

    # --- THIS IS THE CORRECTED PATH LOGIC ---
    # Construct the path from this script's location (gerby/views/methods.py)
    # to the tools directory (gerby/tools/).
    try:
        current_dir = os.path.dirname(__file__)
        gerby_dir = os.path.dirname(current_dir)
        filepath = os.path.join(gerby_dir, 'tag_ancestors_2.json')
    except NameError:
        # Fallback in case __file__ is not defined (e.g., in some interactive shells)
        filepath = 'gerby/tag_ancestors_2.json'


    # Regex to find the 4-character tag ID (e.g., 01VM) in a filename.
    tag_id_regex = re.compile(r'-([0-9A-Z]{4})-')

    if not os.path.exists(filepath):
        # If the file doesn't exist, return an empty map and move on.
        print(f"Warning: Ancestor file not found at {filepath}") # Added a warning for easier debugging
        return {}

    with open(filepath) as f:
        data = json.load(f)

    for child_file, parent_file in data.items():
        child_match = tag_id_regex.search(child_file)
        parent_match = tag_id_regex.search(parent_file)

        if child_match and parent_match:
            child_id = child_match.group(1)
            parent_id = parent_match.group(1)
            ancestor_map[child_id] = parent_id

    return ancestor_map

def is_math(tag, name, value):
  return name == "type" and value in ["math/tex", "math/tex; mode=display"]


# Stacks flavored Markdown parser
def sfm(comment):
  attributes = ALLOWED_ATTRIBUTES
  attributes["a"] = ["data-tag", "class", "href"]
  attributes["script"] = is_math

  tags = ALLOWED_TAGS + ["span", "script"]

  bleach = BleachExtension(tags=tags, attributes=attributes)
  math = MathExtension(enable_dollar_delimiter=True)
  md = markdown.Markdown(extensions=[math, bleach])

  # Stacks flavored Markdown: only \ref{tag}, no longer \ref{label}
  references = re.compile(r"\\ref\{([0-9A-Z]{4})\}").findall(comment)
  tags = Tag.select(Tag.tag, Tag.ref).where(Tag.tag << references)
  tags = {tag.tag: tag.ref for tag in tags}

  for reference in references:
    if reference in tags:
      comment = comment.replace("\\ref{" + reference + "}", "<a href=\"/tag/" + reference + "\" data-tag=\"" + reference + "\">" + tags[reference] + "</a>")
    else:
      comment = comment.replace("\\ref{" + reference + "}", "<a href=\"/tag/" + reference + "\" class=\"tag\">" + reference + "</a>")

  comment = md.convert(comment)
  comment = comment.replace("<script>", "<script type=\"text\">")

  return comment


def getBreadcrumb(tag):
  if tag.type == "item":
  #  return [tag]
    # Check if the tag has a parent defined in our explicit map.
    ANCESTOR_MAP = load_ancestors()
    if tag.tag in ANCESTOR_MAP:
      parent_id = ANCESTOR_MAP[tag.tag]
      parent_tag = Tag.get_or_none(Tag.tag == parent_id)
      
      if parent_tag:
        # Recursively get the breadcrumb for the parent and append the current tag.
        parent_breadcrumb = getBreadcrumb(parent_tag)
        return parent_breadcrumb + [tag]

  if tag.type == "part":
    return [tag]

  pieces = tag.ref.split(".")
  refs = [".".join(pieces[0:i]) for i in range(len(pieces) + 1)]
  print(tag)

  tags = Tag.select().where(Tag.ref << refs, ~(Tag.type << ["item", "part"]))
  tags = sorted(tags)

  # if there are parts, we look up the corresponding part and add it
  if Tag.select().where(Tag.type == "part").exists():
    chapter = tags[0]
    part = Part.get(Part.chapter == chapter.tag).part
    tags.insert(0, part)

  return tags
