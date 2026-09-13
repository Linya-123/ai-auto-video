#!/usr/bin/env python3
"""Read-only publication audit. Reports rule/path/line, never matched secrets."""
import argparse
import fnmatch
import json
import re
import subprocess
from pathlib import Path

ALLOW = ['.gitignore', 'README.md', 'LICENSE', 'AGENTS.md', 'scripts/*.py',
         'ai-auto-video/SKILL.md', 'ai-auto-video/agents/openai.yaml',
         'ai-auto-video/references/*.md', 'ai-auto-video/scripts/*.py',
         'ai-auto-video/scripts/requirements*.txt']
RULES = {
    'private-key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'credential-token': r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)',
    'literal-secret': r'''(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*["']?\s*[:=]\s*["'][^"'\n]{12,}["']''',
    'personal-path': r'(?:/Users/[A-Za-z0-9_\u4e00-\u9fff.-]+/|/home/[A-Za-z0-9_.-]+/|[A-Z]:\\Users\\)',
    'private-voice-id': r'\bmyVoice\w*\d{6,}\w*',
    'signed-url': r'(?i)https?://[^\s"<>]+[?&](?:token|signature|x-amz-signature|api_key)=',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
}

def allowed(name):
    parts = Path(name).parts
    if any(x.startswith('.env') or x.endswith('.env') or 'credentials' in x.lower() or 'secrets' in x.lower() for x in parts): return False
    return any(fnmatch.fnmatchcase(name, pattern) and len(parts) == len(Path(pattern).parts) for pattern in ALLOW)

def scan(name, data):
    findings=[]
    try: text=data.decode('utf-8')
    except UnicodeDecodeError: return [{'file':name,'rule':'non-text'}]
    for key, pattern in RULES.items():
        for match in re.finditer(pattern,text):
            findings.append({'file':name,'line':text.count('\n',0,match.start())+1,'rule':key})
    return findings

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args();root=args.root.resolve();findings=[];excluded=[];count=0
    for p in root.rglob('*'):
        name=p.relative_to(root).as_posix()
        if '.git' in p.relative_to(root).parts: continue
        if p.is_symlink(): findings.append({'file':name,'rule':'symlink'});continue
        if not p.is_file():continue
        if allowed(name): findings.extend(scan(name,p.read_bytes()));count+=1
        else:excluded.append(name)
    history='not-a-git-repository'
    if (root/'.git').exists():
        def git(*args):return subprocess.check_output(['git','-C',str(root),*args])
        for name in git('ls-files','-z').decode().split('\0'):
            if not name:continue
            if not allowed(name):findings.append({'file':name,'rule':'tracked-forbidden-file'})
            else:findings.extend(scan(name,git('show',':'+name)))
        revisions=git('rev-list','--all').decode().split()
        for rev in revisions:
            for row in git('ls-tree','-r','-z',rev).split(b'\0'):
                if not row:continue
                metadata,name=row.split(b'\t',1);name=name.decode();mode,kind,oid=metadata.split()
                if kind!=b'blob':continue
                # Historical releases used the former Skill directory; apply the same source-only rules.
                audit_name = 'ai-auto-video/' + name[len('ip-video-pipeline/'):] if name.startswith('ip-video-pipeline/') else name
                if not allowed(audit_name):findings.append({'file':name,'rule':'history-forbidden-file','commit':rev[:12]})
                else:findings.extend(scan(name,git('cat-file','blob',oid.decode())))
        history=f'checked {len(revisions)} commits'
    print(json.dumps({'ok':not findings,'public_files_checked':count,'excluded_local_files':excluded,
        'findings':findings,'history':history,'scope':'Pattern audit, not proof of absence of all private information. Review staged diff before publishing.'},ensure_ascii=False,indent=2))
    raise SystemExit(bool(findings))

if __name__=='__main__':main()
