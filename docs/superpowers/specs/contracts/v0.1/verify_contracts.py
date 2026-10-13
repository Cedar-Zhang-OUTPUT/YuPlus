"""Validate design artifacts only; no real CLI and no persistent database.
Run with Python 3 + requirements-validation.txt: python verify_contracts.py
"""
from pathlib import Path
import copy
import json
import sqlite3
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
passed = []

def check(name, condition):
    assert condition, name
    passed.append(name)

schemas = {}
for name in ('cli-input', 'cli-output'):
    schema = json.loads((ROOT / (name + '.schema.json')).read_text())
    Draft202012Validator.check_schema(schema)
    schemas[name] = Draft202012Validator(schema, format_checker=FormatChecker())
    passed.append(name + ' schema valid')

fixtures = {}
for path in sorted((ROOT / 'examples').glob('*.json')):
    value = json.loads(path.read_text())
    fixtures[path.name] = value
    validator = schemas['cli-input' if '.input.' in path.name else 'cli-output']
    errors = list(validator.iter_errors(value))
    assert not errors, str(path.name) + ': ' + '\n'.join(str(e) for e in errors)
    passed.append(path.name)

def bad_json(name, fixture, mutate):
    value = copy.deepcopy(fixtures[fixture])
    mutate(value)
    check(name, not schemas['cli-input'].is_valid(value))

bad_json('reject unknown request field', '01-source-feishu.input.json', lambda v: v.update(agent_status='reading'))
bad_json('reject undocumented draft field', '04-draft-initial.input.json', lambda v: v['objects'][0]['set_items'][0]['data'].update(anything='x'))
bad_json('reject float money', '04-draft-initial.input.json', lambda v: v['objects'][0]['set_items'][0]['data'].update(min_minor=100.50))
bad_json('reject R05 publication', '06-review-initial.input.json', lambda v: v['documents'][0]['target'].update(type_key='qa'))
bad_json('reject review without dependency', '06-review-initial.input.json', lambda v: v['documents'][0]['set_blocks'][0].update(dependencies=[]))
bad_json('reject missing optimistic revision', '07-draft-budget-update.input.json', lambda v: v['objects'][0].pop('base_revision'))
bad_json('reject empty source', '01-source-feishu.input.json', lambda v: v['snapshot'].pop('body'))
bad_json('reject malformed capture time', '01-source-feishu.input.json', lambda v: v['snapshot'].update(captured_at='yesterday'))

catalog = json.loads((ROOT / 'object-types.json').read_text())
check('all 23 distinct approved types represented', len(catalog['objects']) == len({v['type_key'] for v in catalog['objects']}) == 23)
for entry in catalog['objects'] + catalog['internal_types']:
    fragment = entry['data_schema_ref'].split('#/$defs/')[1]
    check('catalog data schema ' + entry['type_key'], fragment in schemas['cli-input'].schema['$defs'])

cx = sqlite3.connect(':memory:', isolation_level=None)
cx.executescript((ROOT / 'schema.sql').read_text())
check('foreign keys enabled', cx.execute('PRAGMA foreign_keys').fetchone()[0] == 1)
check('recursive triggers enabled', cx.execute('PRAGMA recursive_triggers').fetchone()[0] == 1)
check('13 business tables', cx.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0] == 13)
T = '2026-10-13T02:00:00Z'
H = 'a' * 64

def insert(table, **values):
    # Identifiers are fixed by this validation script; values are always bound.
    cx.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))

def change(cid, project='p1'):
    insert('changes', id=cid, project_id=project, command='fixture', effect='changed', request_id='req_' + cid,
           request_hash=H, actor_json='{}', reason='contract validation fixture', result_json='{}', created_at=T)

def source(sid, project='p1'):
    insert('sources', project_id=project, id=sid, provider='oral', resource_type='statement', provider_key=sid, cached_title='原话', created_at=T)

def snapshot(vid, sid, change_id='c1', project='p1', version=1):
    insert('source_versions', project_id=project, id=vid, source_id=sid, version=version, provider_revision=None,
           capture_scope_json='{"kind":"whole_resource"}', extraction_profile='text-v1', content_hash=H,
           title_at_capture='原话', body_text='预算100万', body_format='text', provenance_json='{}',
           captured_at=T, recorded_at=T, change_id=change_id)

def obj(oid, layer='draft', typ='budget_range', project='p1', scope='project'):
    insert('objects', project_id=project, id=oid, layer=layer, type_key=typ, scope_key=scope, created_at=T)

def rev(rid, oid, version=1, project='p1', change_id='c1'):
    insert('object_revisions', project_id=project, id=rid, object_id=oid, version=version, schema_version=1,
           payload_json='{}', content_hash=H, change_id=change_id, created_at=T)

def seal(table, rid, project='p1'):
    cx.execute(f'UPDATE {table} SET sealed=1 WHERE project_id=? AND id=?', (project,rid))

def edge(consumer, producer='d1', producer_rev='dr1', project='p1', key='dep'):
    insert('revision_dependencies', project_id=project, consumer_revision_id=consumer, consumer_item_id='budget',
           dependency_id=key, producer_object_id=producer, producer_revision_id=producer_rev,
           producer_item_id='budget', fingerprint=H, dependency_kind='fact')

def expect_error(name, operation, token):
    cx.execute('SAVEPOINT probe')
    try:
        operation()
    except sqlite3.IntegrityError as exc:
        check(name, token in str(exc))
    else:
        raise AssertionError(name + ': unexpectedly accepted')
    finally:
        cx.execute('ROLLBACK TO probe')
        cx.execute('RELEASE probe')

cx.execute('BEGIN')
for p in ('p1','p2'):
    insert('projects', id=p, name=p, created_at=T, updated_at=T)
source('s1'); snapshot('sv1','s1')
insert('blobs', sha256=H, size_bytes=10, storage_key='sha256/aa/' + H, created_at=T)
insert('source_files', project_id='p1', source_version_id='sv1', asset_id='original', role='original', display_name='原件', mime_type='text/plain', blob_sha256=H)
seal('source_versions','sv1')
cx.execute("UPDATE sources SET latest_snapshot_id='sv1' WHERE project_id='p1' AND id='s1'")
obj('d1');rev('dr1','d1')
insert('revision_sources', project_id='p1', revision_id='dr1', item_id='budget', evidence_id='ev', source_version_id='sv1', asset_id='original', evidence_kind='supports')
seal('object_revisions','dr1')
cx.execute("UPDATE objects SET current_revision_id='dr1' WHERE project_id='p1' AND id='d1'")
obj('r1','review','debrief');rev('rr1','r1');edge('rr1');seal('object_revisions','rr1')
cx.execute("UPDATE objects SET current_revision_id='rr1' WHERE project_id='p1' AND id='r1'")
# These rows referenced the deferred change FK before the receipt existed.
change('c1')
cx.execute('COMMIT')
check('source -> draft -> review transaction commits', not list(cx.execute('PRAGMA foreign_key_check')))

expect_error('source bytes immutable', lambda: cx.execute("UPDATE source_versions SET body_text='changed' WHERE id='sv1'"), 'IMMUTABLE_REVISION')
expect_error('draft content immutable', lambda: cx.execute("UPDATE object_revisions SET payload_json='{" + '"x":1' + "}' WHERE id='dr1'"), 'IMMUTABLE_REVISION')
expect_error('sealed revision cannot unseal', lambda: cx.execute("UPDATE object_revisions SET sealed=0 WHERE id='rr1'"), 'IMMUTABLE_REVISION')
expect_error('old evidence cannot mutate', lambda: cx.execute("UPDATE revision_sources SET evidence_kind='quote'"), 'APPEND_ONLY')
expect_error('old dependency cannot mutate', lambda: cx.execute("UPDATE revision_dependencies SET producer_item_id='other'"), 'APPEND_ONLY')
expect_error('history cannot delete', lambda: cx.execute("DELETE FROM object_revisions WHERE id='rr1'"), 'HISTORY_RETAINED')
expect_error('receipt cannot mutate', lambda: cx.execute("UPDATE changes SET reason='rewritten'"), 'APPEND_ONLY')
expect_error('replace cannot overwrite receipt', lambda: cx.execute("INSERT OR REPLACE INTO changes SELECT * FROM changes WHERE id='c1'"), 'HISTORY_RETAINED')
expect_error('cannot add dependency after seal', lambda: edge('rr1',key='later'), 'DEPENDENCY_REQUIRES_OPEN_REVISION')
expect_error('cannot add file after seal', lambda: insert('source_files', project_id='p1', source_version_id='sv1', asset_id='late', role='attachment', display_name='late', mime_type='text/plain',blob_sha256=H), 'FILE_REQUIRES_OPEN_SOURCE_VERSION')
expect_error('project type scope unique', lambda: obj('duplicate'), 'UNIQUE constraint')
expect_error('source identity unique', lambda: insert('sources',project_id='p1',id='sdup',provider='oral',resource_type='statement',provider_key='s1',cached_title='other',created_at=T), 'UNIQUE constraint')
expect_error('R05 has no separate persisted review', lambda: obj('qa_review','review','qa'), 'CHECK constraint')
expect_error('identity cannot move project', lambda: cx.execute("UPDATE objects SET project_id='p2' WHERE id='d1'"), 'IMMUTABLE_IDENTITY')
expect_error('version numbers cannot skip', lambda: rev('dr3','d1',3), 'INVALID_REVISION_SEQUENCE')
expect_error('head must refer own object', lambda: cx.execute("UPDATE objects SET current_revision_id='dr1' WHERE id='r1'"), 'INVALID_OBJECT_HEAD')
expect_error('referenced bytes cannot garbage collect', lambda: cx.execute('DELETE FROM blobs'), 'FOREIGN KEY constraint')
expect_error('storage key matches bytes', lambda: insert('blobs',sha256='b'*64,size_bytes=1,storage_key='arbitrary',created_at=T), 'CHECK constraint')

cx.execute('BEGIN')
rev('dr2','d1',2)
expect_error('head cannot expose unfinished revision', lambda: cx.execute("UPDATE objects SET current_revision_id='dr2' WHERE id='d1'"), 'INVALID_OBJECT_HEAD')
expect_error('review cannot produce draft dependency', lambda: edge('dr2','r1','rr1'), 'DEPENDENCY_REQUIRES_SEALED_DRAFT')
obj('p2_d','draft','budget_range','p2');rev('p2_dr','p2_d',project='p2',change_id='c2')
expect_error('cross-project dependency rejected', lambda: edge('p2_dr',project='p2'), 'DEPENDENCY_REQUIRES_SEALED_DRAFT')
expect_error('cross-project evidence rejected', lambda: insert('revision_sources',project_id='p2',revision_id='p2_dr',item_id='budget',evidence_id='ev',source_version_id='sv1',evidence_kind='supports'), 'EVIDENCE_REQUIRES_SEALED_SOURCE')
expect_error('attachment must belong to snapshot', lambda: insert('revision_sources',project_id='p1',revision_id='dr2',item_id='budget',evidence_id='bad_asset',source_version_id='sv1',asset_id='missing',evidence_kind='supports'), 'FOREIGN KEY constraint')
seal('object_revisions','dr2');cx.execute("UPDATE objects SET current_revision_id='dr2' WHERE id='d1'")
expect_error('head cannot move backward', lambda: cx.execute("UPDATE objects SET current_revision_id='dr1' WHERE id='d1'"), 'HEAD_CANNOT_MOVE_BACKWARD')
change('c2','p2');seal('object_revisions','p2_dr');cx.execute('COMMIT')

insert('decisions',project_id='p1',id='decision1',change_id='c1',statement='采用100万',decided_by='user',user_instruction_source_version_id='sv1',rationale='',affected_refs_json='[{"object_id":"d1","revision_id":"dr1","item_id":"budget"}]',created_at=T)
def decision(did):
    insert('decisions',project_id='p1',id=did,change_id='c1',statement='采用60万',decided_by='user',user_instruction_source_version_id='sv1',rationale='',affected_refs_json='[{"object_id":"d1","revision_id":"dr2","item_id":"budget"}]',supersedes_id='decision1',created_at=T)
decision('decision2')
expect_error('decision history immutable', lambda: cx.execute("UPDATE decisions SET statement='changed'"), 'APPEND_ONLY')
expect_error('decision supersession cannot fork', lambda: decision('decision3'), 'UNIQUE constraint')
expect_error('review check cannot attach to draft', lambda: insert('review_checks',project_id='p1',id='check1',review_revision_id='dr1',covered_blocks_json='["budget"]',verdict='accepted',instruction_source_version_id='sv1',reviewer='user',note='',change_id='c1',created_at=T), 'CHECK_REQUIRES_REVIEW_REVISION')
insert('review_checks',project_id='p1',id='check1',review_revision_id='rr1',covered_blocks_json='["budget"]',verdict='accepted',instruction_source_version_id='sv1',reviewer='user',note='',change_id='c1',created_at=T)
check('confirmation pins exact review version', cx.execute('SELECT review_revision_id FROM review_checks').fetchone()[0] == 'rr1')
expect_error('request identity unique', lambda: change('c1'), 'UNIQUE constraint')
check('final foreign keys clean', not list(cx.execute('PRAGMA foreign_key_check')))
check('integrity check clean', cx.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
print(f'PASS: {len(passed)} contract checks; SQLite {sqlite3.sqlite_version}; in-memory only.')
print('Scope: JSON schemas/examples and SQL constraints. CLI semantic rules and real execution are outside THIS script; see the application tests.')
