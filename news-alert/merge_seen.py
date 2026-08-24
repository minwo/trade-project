import json
import pathlib
import sys

SEEN_LIMIT = 3000

remote_path = pathlib.Path("news-alert/seen_titles.json")
local_path = pathlib.Path(sys.argv[1])

remote = json.loads(remote_path.read_text(encoding="utf-8")) if remote_path.exists() else []
local = json.loads(local_path.read_text(encoding="utf-8"))

remote_set = set(remote)
merged = remote + [t for t in local if t not in remote_set]
merged = merged[-SEEN_LIMIT:]

remote_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
