CREATE TABLE case_libraries (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 200),
  url TEXT NOT NULL UNIQUE,
  version INTEGER NOT NULL CHECK(version>0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
) STRICT;
CREATE TABLE case_library_requests (
  request_id TEXT PRIMARY KEY,
  request_hash TEXT NOT NULL,
  command TEXT NOT NULL,
  result_json TEXT NOT NULL CHECK(json_valid(result_json)),
  created_at TEXT NOT NULL
) STRICT;
PRAGMA user_version=4;
