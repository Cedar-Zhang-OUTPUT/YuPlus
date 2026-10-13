-- Yu+ storage contract v0.1. Design DDL; not an installed production migration.
-- Connections: foreign_keys=ON, recursive_triggers=ON, busy_timeout=5000, synchronous=FULL.
-- Application initialization separately sets and verifies journal_mode=WAL.
PRAGMA foreign_keys = ON;
PRAGMA recursive_triggers = ON;
PRAGMA user_version = 1;

CREATE TABLE projects (
  id TEXT PRIMARY KEY NOT NULL,
  name TEXT NOT NULL CHECK(length(trim(name)) > 0),
  lifecycle TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle IN ('active','archived')),
  working_scene TEXT NOT NULL DEFAULT 'draft' CHECK(working_scene IN ('draft','review')),
  metadata_version INTEGER NOT NULL DEFAULT 1 CHECK(metadata_version > 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT,
  CHECK((lifecycle='archived') = (archived_at IS NOT NULL))
) STRICT;

CREATE TABLE changes (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  project_id TEXT NOT NULL REFERENCES projects(id),
  command TEXT NOT NULL,
  effect TEXT NOT NULL CHECK(effect IN ('changed','noop')),
  request_id TEXT NOT NULL,
  request_hash TEXT NOT NULL CHECK(length(request_hash)=64 AND request_hash NOT GLOB '*[^0-9a-f]*'),
  actor_json TEXT NOT NULL CHECK(json_valid(actor_json) AND json_type(actor_json)='object'),
  reason TEXT NOT NULL,
  causal_change_ids_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(causal_change_ids_json) AND json_type(causal_change_ids_json)='array'),
  changed_refs_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(changed_refs_json) AND json_type(changed_refs_json)='array'),
  result_json TEXT NOT NULL CHECK(json_valid(result_json) AND json_type(result_json)='object'),
  created_at TEXT NOT NULL,
  UNIQUE(project_id,id),
  UNIQUE(project_id,request_id)
) STRICT;

CREATE TABLE sources (
  project_id TEXT NOT NULL REFERENCES projects(id),
  id TEXT NOT NULL,
  provider TEXT NOT NULL CHECK(provider IN ('feishu','local','oral','web')),
  resource_type TEXT NOT NULL,
  provider_key TEXT NOT NULL,
  canonical_url TEXT,
  cached_title TEXT NOT NULL CHECK(length(trim(cached_title))>0),
  latest_snapshot_id TEXT,
  remote_observation_json TEXT CHECK(remote_observation_json IS NULL OR (json_valid(remote_observation_json) AND json_type(remote_observation_json)='object')),
  observation_generation INTEGER NOT NULL DEFAULT 0 CHECK(observation_generation>=0),
  last_checked_at TEXT,
  check_error_json TEXT CHECK(check_error_json IS NULL OR (json_valid(check_error_json) AND json_type(check_error_json)='object')),
  created_at TEXT NOT NULL,
  archived_at TEXT,
  PRIMARY KEY(project_id,id),
  UNIQUE(project_id,provider,resource_type,provider_key),
  FOREIGN KEY(project_id,id,latest_snapshot_id)
    REFERENCES source_versions(project_id,source_id,id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE source_versions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  version INTEGER NOT NULL CHECK(version>0),
  provider_revision TEXT,
  capture_scope_json TEXT NOT NULL CHECK(json_valid(capture_scope_json) AND json_type(capture_scope_json)='object'),
  extraction_profile TEXT NOT NULL,
  content_hash TEXT NOT NULL CHECK(length(content_hash)=64 AND content_hash NOT GLOB '*[^0-9a-f]*'),
  title_at_capture TEXT NOT NULL,
  body_text TEXT,
  body_format TEXT CHECK(body_format IN ('text','markdown','xml','json')),
  provenance_json TEXT NOT NULL CHECK(json_valid(provenance_json) AND json_type(provenance_json)='object'),
  captured_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  change_id TEXT NOT NULL,
  sealed INTEGER NOT NULL DEFAULT 0 CHECK(sealed IN (0,1)),
  PRIMARY KEY(project_id,id),
  UNIQUE(project_id,source_id,id),
  UNIQUE(project_id,source_id,version),
  CHECK((body_text IS NULL)=(body_format IS NULL)),
  FOREIGN KEY(project_id,source_id) REFERENCES sources(project_id,id),
  FOREIGN KEY(project_id,change_id) REFERENCES changes(project_id,id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE blobs (
  sha256 TEXT PRIMARY KEY NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
  size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),
  storage_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  CHECK(storage_key='sha256/' || substr(sha256,1,2) || '/' || sha256)
) STRICT;

CREATE TABLE source_files (
  project_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('original','body','attachment','transcript','preview')),
  display_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  blob_sha256 TEXT REFERENCES blobs(sha256),
  external_path TEXT,
  external_sha256 TEXT CHECK(external_sha256 IS NULL OR (length(external_sha256)=64 AND external_sha256 NOT GLOB '*[^0-9a-f]*')),
  external_size_bytes INTEGER CHECK(external_size_bytes IS NULL OR external_size_bytes>=0),
  original_locator_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(original_locator_json) AND json_type(original_locator_json)='object'),
  PRIMARY KEY(project_id,source_version_id,asset_id),
  CHECK((blob_sha256 IS NOT NULL AND external_path IS NULL AND external_sha256 IS NULL AND external_size_bytes IS NULL)
     OR (blob_sha256 IS NULL AND external_path IS NOT NULL AND external_sha256 IS NOT NULL AND external_size_bytes IS NOT NULL)),
  FOREIGN KEY(project_id,source_version_id) REFERENCES source_versions(project_id,id)
) STRICT;

CREATE TABLE objects (
  project_id TEXT NOT NULL REFERENCES projects(id),
  id TEXT NOT NULL,
  layer TEXT NOT NULL CHECK(layer IN ('draft','review')),
  type_key TEXT NOT NULL,
  scope_key TEXT NOT NULL,
  current_revision_id TEXT,
  created_at TEXT NOT NULL,
  archived_at TEXT,
  PRIMARY KEY(project_id,id),
  UNIQUE(project_id,layer,type_key,scope_key),
  CHECK((layer='draft' AND type_key IN (
    'bd_context','client_brief','tender_documents','venue','brand_assets','audience',
    'budget_range','budget_allocation','milestones','client_decisions','cooperation_type',
    'competitor_analysis','client_history','client_meetings','qa','project_assessment',
    'lead_strategy','deliverables','resources','responsibilities','project_rating',
    'risks','assessment_decision','expression_guide'))
    OR (layer='review' AND type_key IN ('debrief','advancement','creative_review','creator_brief'))),
  CHECK((layer='draft' AND type_key<>'expression_guide' AND scope_key='project')
     OR (layer='draft' AND type_key='expression_guide' AND length(scope_key)>0)
     OR (layer='review' AND length(scope_key)>0)),
  FOREIGN KEY(project_id,id,current_revision_id)
    REFERENCES object_revisions(project_id,object_id,id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE object_revisions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  object_id TEXT NOT NULL,
  version INTEGER NOT NULL CHECK(version>0),
  schema_version INTEGER NOT NULL CHECK(schema_version>0),
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND json_type(payload_json)='object'),
  content_hash TEXT NOT NULL CHECK(length(content_hash)=64 AND content_hash NOT GLOB '*[^0-9a-f]*'),
  block_lineage_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(block_lineage_json) AND json_type(block_lineage_json)='object'),
  change_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  sealed INTEGER NOT NULL DEFAULT 0 CHECK(sealed IN (0,1)),
  PRIMARY KEY(project_id,id),
  UNIQUE(project_id,object_id,id),
  UNIQUE(project_id,object_id,version),
  FOREIGN KEY(project_id,object_id) REFERENCES objects(project_id,id),
  FOREIGN KEY(project_id,change_id) REFERENCES changes(project_id,id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE revision_sources (
  project_id TEXT NOT NULL,
  revision_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  source_version_id TEXT NOT NULL,
  asset_id TEXT,
  locator_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(locator_json) AND json_type(locator_json)='object'),
  evidence_kind TEXT NOT NULL CHECK(evidence_kind IN ('quote','supports','reported','instruction','contradicts')),
  PRIMARY KEY(project_id,revision_id,item_id,evidence_id),
  FOREIGN KEY(project_id,revision_id) REFERENCES object_revisions(project_id,id),
  FOREIGN KEY(project_id,source_version_id) REFERENCES source_versions(project_id,id),
  FOREIGN KEY(project_id,source_version_id,asset_id) REFERENCES source_files(project_id,source_version_id,asset_id)
) STRICT;

CREATE TABLE revision_dependencies (
  project_id TEXT NOT NULL,
  consumer_revision_id TEXT NOT NULL,
  consumer_item_id TEXT NOT NULL,
  dependency_id TEXT NOT NULL,
  producer_object_id TEXT NOT NULL,
  producer_revision_id TEXT NOT NULL,
  producer_item_id TEXT NOT NULL, -- '*' means whole object; stable user IDs cannot equal '*'.
  fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
  dependency_kind TEXT NOT NULL CHECK(dependency_kind IN ('fact','derivation','expression')),
  PRIMARY KEY(project_id,consumer_revision_id,consumer_item_id,dependency_id),
  FOREIGN KEY(project_id,consumer_revision_id) REFERENCES object_revisions(project_id,id),
  FOREIGN KEY(project_id,producer_object_id,producer_revision_id)
    REFERENCES object_revisions(project_id,object_id,id)
) STRICT;

CREATE TABLE decisions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  change_id TEXT NOT NULL,
  statement TEXT NOT NULL CHECK(length(trim(statement))>0),
  decided_by TEXT NOT NULL CHECK(length(trim(decided_by))>0),
  user_instruction_source_version_id TEXT NOT NULL,
  rationale TEXT NOT NULL,
  affected_refs_json TEXT NOT NULL CHECK(json_valid(affected_refs_json) AND json_type(affected_refs_json)='array' AND json_array_length(affected_refs_json)>0),
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,id),
  CHECK(supersedes_id IS NULL OR supersedes_id<>id),
  FOREIGN KEY(project_id,change_id) REFERENCES changes(project_id,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(project_id,user_instruction_source_version_id) REFERENCES source_versions(project_id,id),
  FOREIGN KEY(project_id,supersedes_id) REFERENCES decisions(project_id,id)
) STRICT;

CREATE TABLE review_checks (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  review_revision_id TEXT NOT NULL,
  covered_blocks_json TEXT NOT NULL CHECK(json_valid(covered_blocks_json) AND json_type(covered_blocks_json)='array' AND json_array_length(covered_blocks_json)>0),
  verdict TEXT NOT NULL CHECK(verdict IN ('accepted','changes_requested','noted')),
  instruction_source_version_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  note TEXT NOT NULL,
  change_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,id),
  FOREIGN KEY(project_id,review_revision_id) REFERENCES object_revisions(project_id,id),
  FOREIGN KEY(project_id,instruction_source_version_id) REFERENCES source_versions(project_id,id),
  FOREIGN KEY(project_id,change_id) REFERENCES changes(project_id,id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE exports (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  review_revision_id TEXT,
  view_basis_json TEXT CHECK(view_basis_json IS NULL OR (json_valid(view_basis_json) AND json_type(view_basis_json)='array' AND json_array_length(view_basis_json)>0)),
  destination TEXT NOT NULL CHECK(destination IN ('feishu','local')),
  external_source_id TEXT,
  local_path TEXT,
  exported_at TEXT NOT NULL,
  change_id TEXT NOT NULL,
  PRIMARY KEY(project_id,id),
  CHECK((review_revision_id IS NOT NULL AND view_basis_json IS NULL) OR (review_revision_id IS NULL AND view_basis_json IS NOT NULL)),
  CHECK((destination='feishu' AND external_source_id IS NOT NULL AND local_path IS NULL) OR (destination='local' AND external_source_id IS NULL AND local_path IS NOT NULL)),
  FOREIGN KEY(project_id,review_revision_id) REFERENCES object_revisions(project_id,id),
  FOREIGN KEY(project_id,external_source_id) REFERENCES sources(project_id,id),
  FOREIGN KEY(project_id,change_id) REFERENCES changes(project_id,id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE INDEX changes_project_seq ON changes(project_id,seq);
CREATE INDEX sources_project_provider ON sources(project_id,provider);
CREATE INDEX revisions_change ON object_revisions(project_id,change_id);
CREATE INDEX evidence_reverse ON revision_sources(project_id,source_version_id);
CREATE INDEX dependencies_reverse ON revision_dependencies(project_id,producer_object_id,producer_item_id);
CREATE INDEX decisions_change ON decisions(project_id,change_id);
CREATE UNIQUE INDEX decisions_one_successor ON decisions(project_id,supersedes_id) WHERE supersedes_id IS NOT NULL;
CREATE INDEX checks_revision ON review_checks(project_id,review_revision_id);

-- Membership and publication guards. Sealing is internal to one CLI transaction,
-- not an Agent processing status, and is never exposed in the UI.
CREATE TRIGGER source_initial_head BEFORE INSERT ON sources
WHEN NEW.latest_snapshot_id IS NOT NULL BEGIN
  SELECT RAISE(ABORT,'HEAD_MUST_START_NULL');
END;
CREATE TRIGGER object_initial_head BEFORE INSERT ON objects
WHEN NEW.current_revision_id IS NOT NULL BEGIN
  SELECT RAISE(ABORT,'HEAD_MUST_START_NULL');
END;
CREATE TRIGGER source_head_guard BEFORE UPDATE OF latest_snapshot_id ON sources
WHEN NEW.latest_snapshot_id IS NOT OLD.latest_snapshot_id BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM source_versions v WHERE v.project_id=NEW.project_id AND v.source_id=NEW.id AND v.id=NEW.latest_snapshot_id AND v.sealed=1)
    THEN RAISE(ABORT,'INVALID_SOURCE_HEAD') END;
  SELECT CASE WHEN OLD.latest_snapshot_id IS NOT NULL AND
    (SELECT version FROM source_versions WHERE project_id=NEW.project_id AND id=NEW.latest_snapshot_id) <=
    (SELECT version FROM source_versions WHERE project_id=OLD.project_id AND id=OLD.latest_snapshot_id)
    THEN RAISE(ABORT,'HEAD_CANNOT_MOVE_BACKWARD') END;
END;
CREATE TRIGGER object_head_guard BEFORE UPDATE OF current_revision_id ON objects
WHEN NEW.current_revision_id IS NOT OLD.current_revision_id BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM object_revisions v WHERE v.project_id=NEW.project_id AND v.object_id=NEW.id AND v.id=NEW.current_revision_id AND v.sealed=1)
    THEN RAISE(ABORT,'INVALID_OBJECT_HEAD') END;
  SELECT CASE WHEN OLD.current_revision_id IS NOT NULL AND
    (SELECT version FROM object_revisions WHERE project_id=NEW.project_id AND id=NEW.current_revision_id) <=
    (SELECT version FROM object_revisions WHERE project_id=OLD.project_id AND id=OLD.current_revision_id)
    THEN RAISE(ABORT,'HEAD_CANNOT_MOVE_BACKWARD') END;
END;
CREATE TRIGGER evidence_guard BEFORE INSERT ON revision_sources BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM object_revisions r JOIN objects o ON o.project_id=r.project_id AND o.id=r.object_id WHERE r.project_id=NEW.project_id AND r.id=NEW.revision_id AND r.sealed=0 AND o.layer='draft')
    THEN RAISE(ABORT,'EVIDENCE_REQUIRES_OPEN_DRAFT_REVISION') END;
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM source_versions WHERE project_id=NEW.project_id AND id=NEW.source_version_id AND sealed=1)
    THEN RAISE(ABORT,'EVIDENCE_REQUIRES_SEALED_SOURCE') END;
END;
CREATE TRIGGER dependency_guard BEFORE INSERT ON revision_dependencies BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM object_revisions WHERE project_id=NEW.project_id AND id=NEW.consumer_revision_id AND sealed=0)
    THEN RAISE(ABORT,'DEPENDENCY_REQUIRES_OPEN_REVISION') END;
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM object_revisions r JOIN objects o ON o.project_id=r.project_id AND o.id=r.object_id WHERE r.project_id=NEW.project_id AND r.id=NEW.producer_revision_id AND r.object_id=NEW.producer_object_id AND r.sealed=1 AND o.layer='draft')
    THEN RAISE(ABORT,'DEPENDENCY_REQUIRES_SEALED_DRAFT') END;
END;
CREATE TRIGGER source_file_guard BEFORE INSERT ON source_files
WHEN NOT EXISTS(SELECT 1 FROM source_versions WHERE project_id=NEW.project_id AND id=NEW.source_version_id AND sealed=0) BEGIN
  SELECT RAISE(ABORT,'FILE_REQUIRES_OPEN_SOURCE_VERSION');
END;
CREATE TRIGGER review_check_guard BEFORE INSERT ON review_checks
WHEN NOT EXISTS(SELECT 1 FROM object_revisions r JOIN objects o ON o.project_id=r.project_id AND o.id=r.object_id WHERE r.project_id=NEW.project_id AND r.id=NEW.review_revision_id AND r.sealed=1 AND o.layer='review') BEGIN
  SELECT RAISE(ABORT,'CHECK_REQUIRES_REVIEW_REVISION');
END;
CREATE TRIGGER export_review_guard BEFORE INSERT ON exports
WHEN NEW.review_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM object_revisions r JOIN objects o ON o.project_id=r.project_id AND o.id=r.object_id WHERE r.project_id=NEW.project_id AND r.id=NEW.review_revision_id AND r.sealed=1 AND o.layer='review') BEGIN
  SELECT RAISE(ABORT,'EXPORT_REQUIRES_REVIEW_REVISION');
END;

-- Additional append-only and identity guards are defined below.

CREATE TRIGGER source_versions_start_open BEFORE INSERT ON source_versions WHEN NEW.sealed<>0 BEGIN SELECT RAISE(ABORT,'REVISION_MUST_START_OPEN'); END;
CREATE TRIGGER source_versions_seal_only BEFORE UPDATE ON source_versions WHEN OLD.sealed<>0 OR NEW.sealed<>1 OR NEW.project_id IS NOT OLD.project_id OR NEW.id IS NOT OLD.id OR NEW.source_id IS NOT OLD.source_id OR NEW.version IS NOT OLD.version OR NEW.provider_revision IS NOT OLD.provider_revision OR NEW.capture_scope_json IS NOT OLD.capture_scope_json OR NEW.extraction_profile IS NOT OLD.extraction_profile OR NEW.content_hash IS NOT OLD.content_hash OR NEW.title_at_capture IS NOT OLD.title_at_capture OR NEW.body_text IS NOT OLD.body_text OR NEW.body_format IS NOT OLD.body_format OR NEW.provenance_json IS NOT OLD.provenance_json OR NEW.captured_at IS NOT OLD.captured_at OR NEW.recorded_at IS NOT OLD.recorded_at OR NEW.change_id IS NOT OLD.change_id BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER source_versions_sequence BEFORE INSERT ON source_versions WHEN NEW.version <> (SELECT COALESCE(MAX(version),0)+1 FROM source_versions WHERE project_id=NEW.project_id AND source_id=NEW.source_id) BEGIN SELECT RAISE(ABORT,'INVALID_REVISION_SEQUENCE'); END;
CREATE TRIGGER object_revisions_start_open BEFORE INSERT ON object_revisions WHEN NEW.sealed<>0 BEGIN SELECT RAISE(ABORT,'REVISION_MUST_START_OPEN'); END;
CREATE TRIGGER object_revisions_seal_only BEFORE UPDATE ON object_revisions WHEN OLD.sealed<>0 OR NEW.sealed<>1 OR NEW.project_id IS NOT OLD.project_id OR NEW.id IS NOT OLD.id OR NEW.object_id IS NOT OLD.object_id OR NEW.version IS NOT OLD.version OR NEW.schema_version IS NOT OLD.schema_version OR NEW.payload_json IS NOT OLD.payload_json OR NEW.content_hash IS NOT OLD.content_hash OR NEW.block_lineage_json IS NOT OLD.block_lineage_json OR NEW.change_id IS NOT OLD.change_id OR NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER object_revisions_sequence BEFORE INSERT ON object_revisions WHEN NEW.version <> (SELECT COALESCE(MAX(version),0)+1 FROM object_revisions WHERE project_id=NEW.project_id AND object_id=NEW.object_id) BEGIN SELECT RAISE(ABORT,'INVALID_REVISION_SEQUENCE'); END;
CREATE TRIGGER changes_no_update BEFORE UPDATE ON changes BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER source_files_no_update BEFORE UPDATE ON source_files BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER revision_sources_no_update BEFORE UPDATE ON revision_sources BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER revision_dependencies_no_update BEFORE UPDATE ON revision_dependencies BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER decisions_no_update BEFORE UPDATE ON decisions BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER review_checks_no_update BEFORE UPDATE ON review_checks BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER exports_no_update BEFORE UPDATE ON exports BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER blobs_no_update BEFORE UPDATE ON blobs BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER projects_no_delete BEFORE DELETE ON projects BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER sources_no_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER objects_no_delete BEFORE DELETE ON objects BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER changes_no_delete BEFORE DELETE ON changes BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER source_versions_no_delete BEFORE DELETE ON source_versions BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER source_files_no_delete BEFORE DELETE ON source_files BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER object_revisions_no_delete BEFORE DELETE ON object_revisions BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER revision_sources_no_delete BEFORE DELETE ON revision_sources BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER revision_dependencies_no_delete BEFORE DELETE ON revision_dependencies BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER decisions_no_delete BEFORE DELETE ON decisions BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER review_checks_no_delete BEFORE DELETE ON review_checks BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER exports_no_delete BEFORE DELETE ON exports BEGIN SELECT RAISE(ABORT,'HISTORY_RETAINED'); END;
CREATE TRIGGER projects_identity_immutable BEFORE UPDATE ON projects WHEN NEW.id IS NOT OLD.id BEGIN SELECT RAISE(ABORT,'IMMUTABLE_IDENTITY'); END;
CREATE TRIGGER sources_identity_immutable BEFORE UPDATE ON sources WHEN NEW.project_id IS NOT OLD.project_id OR NEW.id IS NOT OLD.id OR NEW.provider IS NOT OLD.provider OR NEW.resource_type IS NOT OLD.resource_type OR NEW.provider_key IS NOT OLD.provider_key OR NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT,'IMMUTABLE_IDENTITY'); END;
CREATE TRIGGER objects_identity_immutable BEFORE UPDATE ON objects WHEN NEW.project_id IS NOT OLD.project_id OR NEW.id IS NOT OLD.id OR NEW.layer IS NOT OLD.layer OR NEW.type_key IS NOT OLD.type_key OR NEW.scope_key IS NOT OLD.scope_key OR NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT,'IMMUTABLE_IDENTITY'); END;
