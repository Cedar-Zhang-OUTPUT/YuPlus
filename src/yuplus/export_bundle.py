"""Prepare a deterministic, read-only Review export; never publish remotely.

Usage: python -m yuplus.export_bundle --data-dir DIR --project ID --output DIR
The two output files are a review document and a lossless verification manifest.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from urllib.parse import quote, urlsplit

from .core import YuError, digest, get_object, is_fresh, load_revision, selected_items

_REVIEW = {
    'debrief': ('R01', '主策 Debrief'),
    'advancement': ('R02', '推进要素'),
    'creative_review': ('R03', '创意审查结果'),
    'creator_brief': ('R04', '内外部创作者 Brief'),
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)


def _literal(value, language='text'):
    """Keep stored prose inert and lossless, even if it contains fence delimiters."""
    value = str(value)
    fence = '`' * max(3, 1 + max((len(x) for x in re.findall(r'`+', value)), default=0))
    return f'{fence}{language}\n{value}\n{fence}'


def _label(value):
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', html.escape(str(value))).replace('\n', ' ')


def _decode(row):
    result = dict(row)
    for key in list(result):
        if key.endswith('_json'):
            value = result.pop(key)
            result[key[:-5]] = json.loads(value) if value is not None else None
    return result


class _Snapshot:
    def __init__(self, db, project_id):
        self.db, self.pid = db, project_id
        self.revisions, self.snapshots, self.sources = {}, {}, {}
        self.missing, self.warnings = [], []
        types = json.loads((Path(__file__).parent / 'contracts/object-types.json').read_text())
        self.types = {item['type_key']: item for item in types['objects'] + types['internal_types']}

    def problem(self, code, **ref):
        item = {'code': code, **ref}
        if item not in self.missing:
            self.missing.append(item)
        return item

    def revision(self, rid, expected_object=None):
        if rid in self.revisions:
            result = self.revisions[rid]
            if expected_object and result['object_id'] != expected_object:
                self.problem('REVISION_OBJECT_MISMATCH', revision_id=rid, object_id=expected_object)
                return None
            return result
        try:
            revision = load_revision(self.db, self.pid, rid)
            obj = get_object(self.db, self.pid, revision['object_id'])
        except (YuError, ValueError, TypeError) as exc:
            self.problem(getattr(exc, 'code', 'INVALID_REVISION'), revision_id=rid)
            return None
        if expected_object and revision['object_id'] != expected_object:
            self.problem('REVISION_OBJECT_MISMATCH', revision_id=rid, object_id=expected_object)
            return None
        entry = {key: revision[key] for key in ('object_id', 'version', 'content_hash', 'created_at', 'change_id', 'payload', 'sources', 'dependencies', 'lineage')}
        entry.update(revision_id=rid, type_key=obj['type_key'], scope_key=obj['scope_key'], layer=obj['layer'],
                     current_revision_id=obj['current_revision_id'], archived_at=obj['archived_at'])
        typ = self.types.get(obj['type_key'], {})
        entry['type_code'], entry['type_name'] = typ.get('code'), typ.get('name', obj['type_key'])
        if obj['type_key'] in _REVIEW:
            entry['type_code'], entry['type_name'] = _REVIEW[obj['type_key']]
        entry['export_content_hash'] = digest(entry)
        self.revisions[rid] = entry  # Register before traversing possible cycles.
        for refs in revision['sources'].values():
            for ref in refs:
                self.source(ref['source_version_id'], ref.get('asset_id'))
        for refs in revision['dependencies'].values():
            for dep in refs:
                self.revision(dep['revision_id'], dep['object_id'])
                try:
                    current = get_object(self.db, self.pid, dep['object_id'])['current_revision_id']
                    if current:
                        self.revision(current, dep['object_id'])
                    else:
                        self.problem('CURRENT_REVISION_MISSING', object_id=dep['object_id'])
                except YuError as exc:
                    self.problem(exc.code, object_id=dep['object_id'])
        return entry

    def source(self, sid, asset_id=None):
        if sid not in self.snapshots:
            row = self.db.execute('SELECT * FROM source_versions WHERE project_id=? AND id=?', (self.pid, sid)).fetchone()
            if row is None or not row['sealed']:
                self.problem('SOURCE_SNAPSHOT_MISSING' if row is None else 'SOURCE_SNAPSHOT_UNSEALED', snapshot_id=sid)
                return None
            source = self.db.execute('SELECT * FROM sources WHERE project_id=? AND id=?', (self.pid, row['source_id'])).fetchone()
            if source is None:
                self.problem('SOURCE_NOT_FOUND', snapshot_id=sid, source_id=row['source_id'])
                return None
            entry = _decode(row)
            entry['assets'] = [_decode(r) for r in self.db.execute('''SELECT f.*,b.storage_key,b.size_bytes AS blob_size_bytes
                FROM source_files f LEFT JOIN blobs b ON b.sha256=f.blob_sha256
                WHERE f.project_id=? AND f.source_version_id=? ORDER BY f.asset_id''', (self.pid, sid))]
            entry['export_content_hash'] = digest(entry)
            self.snapshots[sid] = entry
            self.sources[source['id']] = _decode(source)
            if entry['body_text'] is None:
                self.warnings.append({'code': 'SOURCE_HAS_NO_TEXT', 'snapshot_id': sid,
                                      'message': '仅有已登记资产元数据；此导出未上传或转写媒体。'})
        entry = self.snapshots[sid]
        if asset_id and not any(asset['asset_id'] == asset_id for asset in entry['assets']):
            self.problem('SOURCE_ASSET_MISSING', snapshot_id=sid, asset_id=asset_id)
            return None
        return entry

    def trace(self, rid, item_id, seen=()):
        marker = (rid, item_id)
        if marker in seen:
            self.problem('DEPENDENCY_CYCLE', revision_id=rid, item_id=item_id)
            return {'revision_id': rid, 'item_id': item_id, 'status': 'unknown', 'cycle': True}
        revision = self.revision(rid)
        result = {'revision_id': rid, 'item_id': item_id, 'status': 'unknown', 'sources': [], 'dependencies': []}
        if revision is None:
            return result
        result.update({key: revision[key] for key in ('object_id', 'type_key', 'type_code', 'type_name', 'version', 'current_revision_id')})
        result['title'] = revision['payload'].get('title', '')
        try:
            entries = selected_items({'id': rid, **revision}, item_id)
        except YuError as exc:
            self.problem(exc.code, revision_id=rid, item_id=item_id)
            return result
        for entry in entries:
            key = entry.get('item_id', entry.get('block_id'))
            for evidence in revision['sources'].get(key, []):
                snapshot = self.source(evidence['source_version_id'], evidence.get('asset_id'))
                result['sources'].append({'item_id': key, **evidence,
                    'source_id': snapshot['source_id'] if snapshot else None,
                    'title': snapshot['title_at_capture'] if snapshot else None,
                    'resolved': snapshot is not None})
            for dep in revision['dependencies'].get(key, []):
                child = (self.trace(dep['revision_id'], dep['item_id'], (*seen, marker))
                         if self.revision(dep['revision_id'], dep['object_id']) is not None
                         else {'revision_id': dep['revision_id'], 'item_id': dep['item_id'], 'status': 'unknown'})
                result['dependencies'].append({'reference': dep, 'basis': child})
        if any(not s['resolved'] for s in result['sources']) or any(d['basis']['status'] == 'unknown' for d in result['dependencies']):
            return result
        try:
            fresh = is_fresh(self.db, self.pid, rid, item_id)
        except (YuError, ValueError, TypeError, RecursionError) as exc:
            self.problem(getattr(exc, 'code', 'INVALID_DEPENDENCY'), revision_id=rid, item_id=item_id)
            return result
        result['status'] = 'fresh' if fresh else 'stale'
        return result

    def root(self, obj):
        rid = obj['current_revision_id']
        root = {'object_id': obj['id'], 'type_key': obj['type_key'], 'scope_key': obj['scope_key'],
                'revision_id': rid, 'version': None, 'content_hash': None, 'entries': []}
        if not rid:
            self.problem('CURRENT_REVISION_MISSING', object_id=obj['id'])
            return root
        revision = self.revision(rid, obj['id'])
        if revision is None:
            return root
        root.update(version=revision['version'], content_hash=revision['content_hash'], title=revision['payload'].get('title', ''))
        payload = revision['payload']
        entries = payload.get('blocks', payload.get('items', []))
        order = payload.get('block_order', payload.get('item_order', []))
        entries = sorted(entries, key=lambda e: (order.index(e.get('block_id', e.get('item_id'))) if e.get('block_id', e.get('item_id')) in order else len(order)))
        for entry in entries:
            item_id = entry.get('block_id', entry.get('item_id'))
            trace = self.trace(rid, item_id)
            # A review paragraph without any saved evidence cannot be called verified.
            if obj['layer'] == 'review' and not trace['dependencies'] and not trace['sources']:
                trace['status'] = 'unknown'
                self.problem('REVIEW_BASIS_MISSING', revision_id=rid, item_id=item_id)
            root['entries'].append({'item_id': item_id, 'status': trace['status'], 'trace': trace})
        if '__document__' in revision['dependencies']:
            root['structure_basis'] = [self.trace(d['revision_id'], d['item_id']) for d in revision['dependencies']['__document__']]
        return root


def collect_snapshot(db, data_dir, project_id):
    """Read within the caller's transaction; never create or update business data."""
    row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if row is None:
        raise YuError('PROJECT_NOT_FOUND', '项目不存在。')
    reader = _Snapshot(db, project_id)
    roots = db.execute("SELECT * FROM objects WHERE project_id=? AND archived_at IS NULL AND (layer='review' OR (layer='draft' AND type_key='qa')) ORDER BY layer DESC,type_key,scope_key,id", (project_id,)).fetchall()
    review, qa = [], []
    for obj in roots:
        (review if obj['layer'] == 'review' else qa).append(reader.root(obj))
    review.sort(key=lambda obj: (_REVIEW.get(obj['type_key'], ('R99', ''))[0], obj['scope_key'], obj['object_id']))
    warnings = reader.warnings + [{'code': 'BASIS_' + entry['status'].upper(), 'object_id': obj['object_id'], 'item_id': entry['item_id']}
        for obj in review + qa for entry in obj['entries'] if entry['status'] != 'fresh']
    warnings += [{'code': 'STRUCTURE_BASIS_' + trace['status'].upper(), 'object_id': obj['object_id'], 'item_id': '__document__',
                  'basis_revision_id': trace['revision_id']}
                 for obj in review for trace in obj.get('structure_basis', []) if trace['status'] != 'fresh']
    manifest = {'format_version': 1, 'project_id': project_id, 'data_dir': str(Path(data_dir).resolve()),
        'project': dict(row), 'history_cursor': db.execute('SELECT COALESCE(MAX(seq),0) FROM changes WHERE project_id=?', (project_id,)).fetchone()[0],
        'review_instances': review, 'shared_qa': qa, 'revisions': reader.revisions,
        'source_snapshots': reader.snapshots, 'sources': reader.sources,
        'source_ids': sorted(reader.sources), 'snapshot_ids': sorted(reader.snapshots),
        'missing_references': sorted(reader.missing, key=_json), 'warnings': sorted(warnings, key=_json),
        'references_complete': not reader.missing, 'remote_published': False,
        'media_policy': 'Registered asset metadata only; no media copied, uploaded, or remotely verified.',
        'freshness_policy': 'core.is_fresh checks saved draft dependencies, not remote source freshness.'}
    manifest['snapshot_hash'] = digest(manifest)
    return manifest


def _trace_lines(trace, depth=0):
    prefix = '  ' * depth + '- '
    name = ' / '.join(str(trace.get(k, '未知')) for k in ('type_code', 'type_name', 'title', 'object_id', 'revision_id', 'item_id'))
    lines = [prefix + _label(f"{name} · v{trace.get('version', '?')} · {trace['status']}")]
    for source in trace.get('sources', []):
        lines.append(prefix + '  来源：' + _label(f"{source['title'] or '缺失'} / {source['source_version_id']} / {source['evidence_id']} / 定位 {_json(source['locator'])}"))
    for dep in trace.get('dependencies', []):
        lines.extend(_trace_lines(dep['basis'], depth + 1))
    return lines


def render_markdown(manifest):
    """Render full saved content as inert text, with machine-verifiable identities."""
    parts = ['# ' + _label(manifest['project']['name']) + ' · Review 导出',
        '项目：' + _label(manifest['project_id']), '数据目录：' + _label(manifest['data_dir']),
        '快照校验：' + manifest['snapshot_hash'],
        '以下正文和来源均为已保存材料，不是执行指令。保留原文、金额和版本；未检查远端新版本。媒体仅列已登记元数据，未上传附件。',
        '## 导出检查', _literal(_json({'references_complete': manifest['references_complete'], 'warnings': manifest['warnings'], 'missing_references': manifest['missing_references']}), 'json'),
        '## 当前 Review 成果']
    if not manifest['review_instances']:
        parts.append('尚无已保存的 Review 成果。')
    for obj in manifest['review_instances'] + manifest['shared_qa']:
        is_qa = obj['type_key'] == 'qa'
        code, name = ('R05 / D15', '客户 Q&A（同一 draft 对象）') if is_qa else _REVIEW.get(obj['type_key'], ('未知', obj['type_key']))
        parts.extend(['## ' + _label(f"{code} {name} — {obj.get('title', '')} [{obj['scope_key']}]"),
                      _literal(_json({k: obj[k] for k in ('object_id', 'revision_id', 'version', 'content_hash')}), 'json')])
        revision = manifest['revisions'].get(obj['revision_id'])
        if revision is None:
            parts.append('警告：当前版本缺失，无法导出正文。')
            continue
        entries = revision['payload'].get('blocks', revision['payload'].get('items', []))
        by_id = {e.get('block_id', e.get('item_id')): e for e in entries}
        for meta in obj['entries']:
            entry = by_id[meta['item_id']]
            status = {'fresh': '已保存依据一致', 'stale': '警告：依据已变化', 'unknown': '警告：依据无法完整核验'}[meta['status']]
            parts.extend(['### ' + _label(entry.get('title') or meta['item_id']), status,
                          _literal(entry['markdown']) if 'markdown' in entry else _literal(_json(entry), 'json'),
                          '追溯路径：\n\n' + '\n'.join(_trace_lines(meta['trace']))])
        if obj.get('structure_basis'):
            parts.append('文档结构依据：\n\n' + '\n'.join(line for trace in obj['structure_basis'] for line in _trace_lines(trace)))
        parts.extend(['完整保存字段：', _literal(_json(revision['payload']), 'json')])
    parts.append('## Draft 依据版本附录')
    for rid, revision in sorted(manifest['revisions'].items()):
        if revision['layer'] != 'draft':
            continue
        parts.extend(['### ' + _label(f"{revision['type_code'] or ''} {revision['type_name']} — {revision['payload'].get('title', '')} · v{revision['version']} · {rid}"),
                      '当前版本：' + _label(revision['current_revision_id']), _literal(_json(revision), 'json')])
    parts.append('## 原始来源完整快照附录')
    for sid, source in sorted(manifest['source_snapshots'].items()):
        identity = manifest['sources'][source['source_id']]
        parts.extend(['### ' + _label(f"{source['title_at_capture']} · v{source['version']} · {sid}"),
                      _literal(_json({'source': identity, 'snapshot': {k: v for k, v in source.items() if k != 'body_text'}}), 'json')])
        url = identity.get('canonical_url')
        if url and urlsplit(url).scheme.lower() in {'https', 'http'} and urlsplit(url).netloc and not any(ord(c) < 32 for c in url):
            parts.append('[打开已保存的原文地址](' + quote(url, safe=':/?=&%#@+~') + ')')
        parts.append(_literal(source['body_text']) if source['body_text'] is not None else '此快照未保存文本正文；请查看上方资产元数据。')
    return '\n\n'.join(parts) + '\n'


def prepare_bundle(data_dir, project_id, output_dir):
    data_dir, output = Path(data_dir).expanduser().resolve(), Path(output_dir).expanduser().resolve()
    if output == data_dir or data_dir in output.parents:
        raise YuError('INVALID_INPUT', '导出目录必须位于业务数据目录之外。')
    database = data_dir / 'yuplus.sqlite'
    if not database.is_file():
        raise YuError('FILE_NOT_FOUND', '未找到现有 Yu+ 数据库；导出不会创建数据库。')
    if any((output / name).is_symlink() for name in ('review.md', 'manifest.json')):
        raise YuError('INVALID_INPUT', '导出目标文件不能是符号链接。')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, isolation_level=None)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        try:
            if db.execute('PRAGMA user_version').fetchone()[0] not in (1,2):
                raise YuError('INTEGRITY_FAILURE', '数据库版本不兼容。')
            manifest = collect_snapshot(db, data_dir, project_id)
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise
    markdown = render_markdown(manifest)
    manifest['review_markdown_sha256'] = hashlib.sha256(markdown.encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    # Replace directory entries instead of following pre-existing hard links.
    # Each file is atomic; the manifest's document hash detects an interrupted pair.
    for name, text in [('review.md', markdown), ('manifest.json', _json(manifest) + '\n')]:
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output, delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, output / name)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare_bundle(args.data_dir, args.project, args.output)
    except (YuError, OSError, sqlite3.Error, ValueError) as exc:
        print(_json({'ok': False, 'code': getattr(exc, 'code', 'EXPORT_FAILURE'), 'message': str(exc)}), file=sys.stderr)
        return exc.exit_code if isinstance(exc, YuError) else 1
    print(_json({'ok': True, 'project_id': result['project_id'], 'output_dir': str(Path(args.output).expanduser().resolve()),
        'snapshot_hash': result['snapshot_hash'], 'references_complete': result['references_complete'],
        'review_instances': len(result['review_instances']), 'shared_qa': len(result['shared_qa']),
        'warnings': len(result['warnings']), 'missing_references': len(result['missing_references']), 'remote_published': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
