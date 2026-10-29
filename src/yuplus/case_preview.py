"""Disposable, bounded board preview cache. Remote reads only; no project writes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sqlite3
import sys
import tempfile
import time
import zlib
from contextlib import contextmanager
from .core import YuError, now
from .feishu import run_lark

MAX_IMAGE=20*1024*1024


def image_type(raw):
    if not 16 <= len(raw) <= MAX_IMAGE: raise YuError('INVALID_PREVIEW','画板预览大小无效。')
    width=height=0
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        pos=8; ended=False
        while pos+12<=len(raw):
            n=struct.unpack('>I',raw[pos:pos+4])[0]; kind=raw[pos+4:pos+8]; end=pos+12+n
            if end>len(raw) or zlib.crc32(raw[pos+4:end-4])&0xffffffff != struct.unpack('>I',raw[end-4:end])[0]: break
            if kind==b'IHDR' and n==13: width,height=struct.unpack('>II',raw[pos+8:pos+16])
            if kind==b'IEND': ended=end==len(raw);break
            pos=end
        if not ended: raise YuError('INVALID_PREVIEW','PNG 预览不完整。')
        mime='image/png'
    elif raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9'):
        pos=2
        while pos+4<=len(raw):
            if raw[pos]!=255: break
            marker=raw[pos+1];pos+=2
            if marker==255:pos-=1;continue
            if marker in (0xDA,0xD9):break
            n=int.from_bytes(raw[pos:pos+2],'big')
            if n<2 or pos+n>len(raw):break
            if marker in (0xC0,0xC1,0xC2) and n>=8:
                height,width=struct.unpack('>HH',raw[pos+3:pos+7]);break
            pos+=n
        mime='image/jpeg'
    else: raise YuError('INVALID_PREVIEW','飞书未返回 PNG/JPEG 预览。')
    if not width or not height or width>32768 or height>32768 or width*height>100_000_000:
        raise YuError('INVALID_PREVIEW','画板预览尺寸无效或过大。')
    return mime


class PreviewCache:
    def __init__(self,data_dir,*,root=None,runner=run_lark):
        self.data_dir=Path(data_dir).resolve();self.runner=runner
        base=Path.home()/('Library/Caches' if sys.platform=='darwin' else '.cache')/'yuplus/case-previews'
        self.root=Path(root) if root else base/hashlib.sha256(str(self.data_dir).encode()).hexdigest()
        if self.root.is_relative_to(self.data_dir): raise YuError('INVALID_INPUT','预览缓存必须位于业务数据目录之外。')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.root,0o700)

    def prefix(self,row):
        return hashlib.sha256((row['project_id']+':'+row['id']+':'+str(row['board_token'])).encode()).hexdigest()

    def cached(self,row):
        if not row.get('board_token'): return None
        try:
            item=json.loads((self.root/(self.prefix(row)+'.json')).read_text())
            key=item['key']
            if not re.fullmatch(self.prefix(row)+r'_[a-f0-9]{64}',key) or not (self.root/key).is_file():return None
            return {'version_id':row['id'],'image_url':'/api/case-finding/images/'+key,'fetched_at':item['fetched_at']}
        except (OSError,ValueError,KeyError,TypeError):return None

    @contextmanager
    def lock(self):
        # Cross-process lock also covers CLI preview and multiple local gateways.
        with (self.root/'cache.lock').open('a') as f:
            deadline=time.monotonic()+26
            while True:
                try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()>deadline: raise YuError('PREVIEW_BUSY','预览正在刷新，请稍后重试。')
                    time.sleep(.05)
            try:yield
            finally:fcntl.flock(f,fcntl.LOCK_UN)

    def refresh(self,row):
        if not row.get('board_token'): raise YuError('BOARD_NOT_READY','本轮尚未关联飞书画板。')
        started=time.time()
        with self.lock():
            # A gateway may have read the row just before the project was purged.
            # Check again under the same cache lock used by permanent cleanup.
            db=sqlite3.connect((self.data_dir/'yuplus.sqlite').as_uri()+'?mode=ro',uri=True)
            try:
                live=db.execute('SELECT 1 FROM case_research WHERE id=? AND project_id=? AND board_token=?',
                                (row['id'],row['project_id'],row['board_token'])).fetchone()
            finally:db.close()
            if not live:raise YuError('TARGET_NOT_FOUND','研究记录已移除，不能刷新预览。')
            manifest=self.root/(self.prefix(row)+'.json');cached=self.cached(row)
            if cached and manifest.stat().st_mtime>=started-2:return cached
            with tempfile.TemporaryDirectory(prefix='export-',dir=self.root) as tmp:
                try:
                    self.runner(['whiteboard','+export','--whiteboard-token',row['board_token'],'--output-type','preview','--output','preview','--as','user','--format','json'],cwd=tmp,timeout=24)
                except YuError as exc:
                    detail=exc.details[0] if exc.details else {}
                    kind=str(detail.get('type','')); subtype=str(detail.get('subtype',''))
                    if kind in ('authentication','authorization') or 'scope' in subtype or 'permission' in subtype:
                        code='FORBIDDEN' if 'scope' in subtype or 'permission' in subtype else 'AUTH_REQUIRED'
                        raise YuError(code,'飞书登录或访问权限需要处理；保留上次预览。') from None
                    raise
                files=[p for p in Path(tmp).glob('preview*') if p.is_file() and not p.is_symlink()]
                if len(files)!=1 or files[0].stat().st_size>MAX_IMAGE: raise YuError('INVALID_PREVIEW','未得到有效画板预览文件。')
                raw=files[0].read_bytes();image_type(raw)
                key=self.prefix(row)+'_'+hashlib.sha256(raw).hexdigest()
                target=self.root/key
                if not target.exists():
                    temp=Path(tmp)/'validated';temp.write_bytes(raw);temp.replace(target)
                item={'key':key,'fetched_at':now()}
                temp=Path(tmp)/'manifest';temp.write_text(json.dumps(item));temp.replace(manifest)
            self.prune(keep=key)
            return self.cached(row)

    def prune(self,keep):
        images=sorted((p for p in self.root.iterdir() if re.fullmatch(r'[a-f0-9]{64}_[a-f0-9]{64}',p.name)),key=lambda p:p.stat().st_mtime,reverse=True)
        total=0
        for i,p in enumerate(images):
            total+=p.stat().st_size
            if p.name!=keep and (i>=32 or total>128*1024*1024 or p.stat().st_mtime<time.time()-7*86400):p.unlink(missing_ok=True)
        for p in self.root.glob('*.json'):
            try:
                key=json.loads(p.read_text())['key']
                if not re.fullmatch(r'[a-f0-9]{64}_[a-f0-9]{64}',key) or not (self.root/key).exists():p.unlink(missing_ok=True)
            except (ValueError,KeyError,TypeError):p.unlink(missing_ok=True)

    def image(self,db,key):
        if not re.fullmatch(r'[a-f0-9]{64}_[a-f0-9]{64}',key):raise YuError('IMAGE_NOT_FOUND','预览不存在。')
        rows=db.execute("SELECT r.* FROM case_research r JOIN projects p ON p.id=r.project_id WHERE p.lifecycle='active'")
        if not any(self.prefix(dict(r))==key[:64] for r in rows):raise YuError('IMAGE_NOT_FOUND','预览不存在。')
        try:
            p=self.root/key
            if p.is_symlink() or p.stat().st_size>MAX_IMAGE:raise OSError()
            raw=p.read_bytes()
        except OSError:raise YuError('IMAGE_NOT_FOUND','预览缓存已过期，请刷新。') from None
        if hashlib.sha256(raw).hexdigest()!=key[65:]:raise YuError('INVALID_PREVIEW','预览校验失败。')
        return raw,image_type(raw)
