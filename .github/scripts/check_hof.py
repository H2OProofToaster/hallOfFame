import json, os, re, subprocess, sys
from datetime import date, datetime

PATH = "hall-of-fame.json"
FIELDS = {"name", "github", "date"}
base_sha = os.environ["BASE_SHA"]
author = os.environ["PR_AUTHOR"]
created = datetime.fromisoformat(
    os.environ["PR_CREATED_AT"].replace("Z", "+00:00")
).date()


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def no_dupes(pairs):
    keys = [k for k, _ in pairs]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        fail(f"Duplicate keys in JSON object: {', '.join(sorted(dupes))}")
    return dict(pairs)


def index_by_user(entries, label):
    if not isinstance(entries, list):
        fail(f"{label}: top level must be a JSON array")
    out = {}
    for e in entries:
        if not isinstance(e, dict) or set(e) != FIELDS:
            fail(f"{label}: every entry must be an object with exactly "
                 f"these fields: {', '.join(sorted(FIELDS))}")
        user = str(e["github"]).lower()
        if user in out:
            fail(f"{label}: more than one entry for '{e['github']}'")
        out[user] = e
    return out


# 1. Only the hall of fame file may change
changed = subprocess.check_output(
    ["git", "diff", "--name-only", base_sha, "HEAD"], text=True
).split()
if changed != [PATH]:
    fail(f"PR must only change {PATH}. Changed files: {', '.join(changed)}")

# 2. Load base and PR versions
try:
    base_raw = json.loads(
        subprocess.check_output(["git", "show", f"{base_sha}:{PATH}"], text=True),
        object_pairs_hook=no_dupes,
    )
except subprocess.CalledProcessError:
    base_raw = []

try:
    with open(PATH) as f:
        head_raw = json.load(f, object_pairs_hook=no_dupes)
except json.JSONDecodeError as e:
    fail(f"{PATH} is not valid JSON: {e}")

base = index_by_user(base_raw, "Base file")
head = index_by_user(head_raw, "Your file")

# 3. Nobody else's entry may be removed or modified
for user, entry in base.items():
    if user not in head:
        fail(f"You removed the entry for '{entry['github']}'")
    if head[user] != entry:
        fail(f"You modified the entry for '{entry['github']}'")

# 4. Exactly one new entry, and it must be the PR author's
added = [u for u in head if u not in base]
if len(added) != 1:
    fail(f"Add exactly one entry (found {len(added)})")

entry = head[added[0]]
if added[0] != author.lower():
    fail(f"'github' must be your GitHub username '{author}', "
         f"not '{entry['github']}'")

# 5. Field validation
if not isinstance(entry["name"], str) or not entry["name"].strip():
    fail("'name' must be a non-empty string")

d = entry["date"]
if not isinstance(d, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
    fail("'date' must be a string in YYYY-MM-DD format")
try:
    entry_date = date.fromisoformat(d)
except ValueError:
    fail(f"'{d}' is not a real calendar date")


print(f"OK: {entry['github']} added their entry.")
