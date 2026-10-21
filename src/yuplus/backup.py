"""Self-contained, verified directory backups. Restore never overwrites data."""
from contextlib import closing
import hashlib
import json
import re
from pathlib import Path
import shutil
import sqlite3

from .core import YuError, canonical, now
from .browser_view import open_verified_asset
from .source import _assets_from_db


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024 * 1024): h.update(chunk)
    return h.hexdigest()


def safe_file(root, name):
    p = root / name
    if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts or p.is_symlink() or p.resolve() != p or not p.is_file():
        raise YuError('INTEGRITY_FAILURE', '备份包含无效文件路径。')
    return p


def check_db(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] not in (1,2) or db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise YuError('INTEGRITY_FAILURE', '备份数据库校验失败。')


def verify_backup(directory):
    root = Path(directory).expanduser().resolve()
    manifest = json.loads(safe_file(root, 'backup.json').read_text())
    if manifest.get('format_version') != 1 or not isinstance(manifest.get('files'), dict) or not {'yuplus.sqlite','restored-assets.json'} <= set(manifest['files']):
        raise YuError('INTEGRITY_FAILURE', '不是可识别的 Yu+ 备份。')
    for name, info in manifest['files'].items():
        if not re.fullmatch(r'(yuplus\.sqlite|restored-assets\.json|objects/sha256/[0-9a-f]{2}/[0-9a-f]{64}|external-files/[0-9a-f]{64})',name):
            raise YuError('INTEGRITY_FAILURE', '备份含非材料库文件。')
        p = safe_file(root, name)
        if p.stat().st_size != info['size'] or file_hash(p) != info['sha256']:
            raise YuError('FILE_HASH_MISMATCH', '备份文件校验失败。', details=[{'file': name}])
    check_db(root / 'yuplus.sqlite')
    # Ensure database references cannot be omitted from a superficially valid manifest.
    with closing(sqlite3.connect((root/'yuplus.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        for r in db.execute('SELECT project_id,id FROM source_versions'):
            for a in _assets_from_db(db, r['project_id'], r['id']):
                if a['storage'] == 'copy': rel = 'objects/' + a['storage_key']
                else:
                    mapping = json.loads(safe_file(root, 'restored-assets.json').read_text())
                    rel = mapping.get(a['local_path'] + ':' + a['sha256'])
                    if rel != 'external-files/'+a['sha256']:raise YuError('INTEGRITY_FAILURE','外部材料映射无效。')
                if not rel or rel not in manifest['files'] or manifest['files'][rel] != {'sha256': a['sha256'], 'size': a['size_bytes']}:
                    raise YuError('INTEGRITY_FAILURE', '备份缺少已登记的材料。')
    return manifest


def create_backup(data_dir, output):
    source, dest = Path(data_dir).expanduser().resolve(), Path(output).expanduser().resolve()
    if dest == source or source in dest.parents or dest in source.parents:
        raise YuError('INVALID_INPUT', '备份目录须与业务目录分开。')
    database = source / 'yuplus.sqlite'
    if not database.is_file(): raise YuError('FILE_NOT_FOUND', '数据目录不存在。')
    dest.mkdir(parents=True, exist_ok=False)
    try:
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as original, closing(sqlite3.connect(dest/'yuplus.sqlite')) as snapshot:
            original.backup(snapshot)
        mappings = {}
        with closing(sqlite3.connect(dest/'yuplus.sqlite')) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute('SELECT project_id,id FROM source_versions'):
                for asset in _assets_from_db(db,row['project_id'],row['id']):
                    rel = 'objects/'+asset['storage_key'] if asset['storage']=='copy' else 'external-files/'+asset['sha256']
                    if asset['storage']=='external': mappings[asset['local_path']+':'+asset['sha256']] = rel
                    target=dest/rel
                    if target.exists(): continue
                    stream,_=open_verified_asset(source,asset)
                    with stream:
                        target.parent.mkdir(parents=True,exist_ok=True)
                        with target.open('xb') as out: shutil.copyfileobj(stream,out)
                    if file_hash(target)!=asset['sha256']: raise YuError('FILE_HASH_MISMATCH','备份过程中材料发生变化。')
        (dest/'restored-assets.json').write_text(canonical(mappings),encoding='utf-8')
        files={str(p.relative_to(dest)):{'sha256':file_hash(p),'size':p.stat().st_size} for p in dest.rglob('*') if p.is_file() and p.name not in {'yuplus.sqlite-wal','yuplus.sqlite-shm'}}
        manifest={'format_version':1,'created_at':now(),'source_data_dir':str(source),'files':files}
        (dest/'backup.json').write_text(canonical(manifest),encoding='utf-8')
        verify_backup(dest)
        return {'backup_dir':str(dest),'files':len(files),'verified':True}
    except BaseException:
        shutil.rmtree(dest)
        raise


def restore_backup(directory, destination):
    root, dest=Path(directory).expanduser().resolve(),Path(destination).expanduser().resolve()
    if root == dest or root in dest.parents or dest in root.parents:
        raise YuError('INVALID_INPUT','恢复目录须与备份目录分开。')
    manifest=verify_backup(root)
    dest.mkdir(parents=True,exist_ok=False)
    try:
        for name,info in manifest['files'].items():
            p=dest/name; p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe_file(root,name),p)
            if p.stat().st_size!=info['size'] or file_hash(p)!=info['sha256']: raise YuError('FILE_HASH_MISMATCH','恢复过程中备份发生变化。')
        check_db(dest/'yuplus.sqlite')
        with closing(sqlite3.connect(dest/'yuplus.sqlite')) as restored:
            if restored.execute('PRAGMA user_version').fetchone()[0] == 2:
                restored.execute("UPDATE chat_monitors SET status=CASE WHEN status='removed' THEN 'removed' ELSE 'paused' END,schedule_json='{}',version=version+1")
                restored.execute('DELETE FROM monitor_leases')
                restored.commit()
        return {'data_dir':str(dest),'verified':True,'files':len(manifest['files'])}
    except BaseException:
        shutil.rmtree(dest)
        raise
