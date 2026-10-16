#!/usr/bin/env python3
"""Install Yu+ and its two Codex Skills from a trusted local checkout (macOS first)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='installation.json'}


def install(args):
    repo=Path(__file__).resolve().parents[1]
    prefix=Path(args.prefix).expanduser().resolve()
    previous=json.loads((prefix/'installation.json').read_text()) if (prefix/'installation.json').is_file() else {}
    skills=Path(args.skills_dir or previous.get('skills_dir') or str(Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills')).expanduser().resolve()
    data=Path(args.data_dir or previous.get('data_dir') or '~/.local/share/yuplus').expanduser().resolve()
    probe=subprocess.run([args.python,'-c','import sys,sqlite3,json; print(json.dumps({"python":list(sys.version_info[:3]),"sqlite":list(sqlite3.sqlite_version_info)}))'],check=True,capture_output=True,text=True)
    runtime=json.loads(probe.stdout)
    if tuple(runtime['python'])<(3,12) or tuple(runtime['sqlite'])<(3,51,3):raise RuntimeError('需要 Python >=3.12 且链接 SQLite >=3.51.3；请用 --python 指定合适解释器。')
    names=['yuplus','yuplus-visualization']
    for name in names:
        target=skills/name
        if target.is_symlink():raise RuntimeError(f'{target} 已存在符号链接；请保留并自行决定如何替换。')
        if (skills/(name+'.previous')).exists() or (skills/(name+'.installing')).exists():raise RuntimeError(f'{name} 上次安装未完成，请先检查 .previous/.installing 保留内容。')
        if target.exists():
            receipt=target/'installation.json'
            if not receipt.is_file() or json.loads(receipt.read_text()).get('managed_files')!=hashes(target):raise RuntimeError(f'{target} 含非本安装器管理或已修改的文件，拒绝覆盖。')
    prefix.mkdir(parents=True,exist_ok=True)
    env=prefix/'venv'
    if not env.exists():subprocess.run([args.python,'-m','venv',str(env)],check=True)
    python=env/'bin/python';cli=env/'bin/yu'
    subprocess.run([str(python),'-m','pip','install',str(repo)],check=True,stdout=sys.stderr)
    subprocess.run([str(cli),'--data-dir',str(data),'doctor','--json'],check=True,stdout=sys.stderr)
    skills.mkdir(parents=True,exist_ok=True)
    for name in names:
        target=skills/name; temp=skills/(name+'.installing')
        if temp.exists():raise RuntimeError(f'{temp} 已存在；上次安装可能被中断，请先检查。')
        shutil.copytree(repo/'skills'/name,temp,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        receipt={'cli':str(cli),'python':str(python),'data_dir':str(data),'managed_files':hashes(temp)}
        (temp/'installation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
        old=skills/(name+'.previous')
        if old.exists():raise RuntimeError(f'{old} 已存在；请保留旧版并检查。')
        if target.exists():target.rename(old)
        try:temp.rename(target)
        except BaseException:
            if old.exists():old.rename(target)
            raise
        if old.exists():shutil.rmtree(old)
    health={'available':False,'message':'未找到 lark-cli；本地材料可正常使用。'}
    if shutil.which('lark-cli'):
        try:
            res=subprocess.run(['lark-cli','auth','status','--verify','--json'],capture_output=True,text=True,timeout=30)
            # Do not persist auth output or account details.
            identity=json.loads(res.stdout).get('identities',{}).get('user',{}) if res.returncode==0 else {}
            verified=res.returncode==0 and identity.get('available') is True and identity.get('verified') is True
            health={'available':verified,'message':'飞书环境检查已执行；具体可访问资源仍以实际读取结果为准。' if verified else '飞书认证检查未通过；按 lark-shared 完成登录。'}
        except (OSError,ValueError,AttributeError,subprocess.TimeoutExpired):health={'available':False,'message':'飞书环境检查未完成；请按 lark-shared 检查环境。'}
    result={'ok':True,'cli':str(cli),'data_dir':str(data),'skills_dir':str(skills),'feishu':health,'start':[str(cli),'--data-dir',str(data),'start','--json']}
    (prefix/'installation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--managed-python',action='store_true',help='由 install.sh 准备独立 Python')
    parser.add_argument('--python',default=sys.executable)
    parser.add_argument('--prefix',default=os.environ.get('YUPLUS_INSTALL_PREFIX','~/.local/share/yuplus-app'))
    parser.add_argument('--skills-dir')
    parser.add_argument('--data-dir')
    try:print(json.dumps(install(parser.parse_args()),ensure_ascii=False,indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print(json.dumps({'ok':False,'message':str(exc)},ensure_ascii=False),file=sys.stderr);sys.exit(1)
