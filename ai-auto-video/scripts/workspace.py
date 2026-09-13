#!/usr/bin/env python3
"""Initialize shared assets, isolated video jobs and portable path aliases."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from pipeline import save, read, require, digest, init
from types import SimpleNamespace

CATEGORIES = ('identity', 'scenes', 'footage', 'screenshots', 'bgm', 'sfx', 'fonts', 'templates', 'references')
MEDIA = {'.png','.jpg','.jpeg','.webp','.svg','.mp4','.mov','.mkv','.wav','.mp3','.m4a','.aac','.ttf','.otf','.html'}
EXCLUDE = {'.git','.venv','node_modules','__pycache__','.cache'}


def setup(a):
    root=Path(a.root).resolve(); root.mkdir(parents=True,exist_ok=True)
    config=root/'workspace.json'
    if config.exists():
        require(read(config).get('schema')=='ip-video-workspace-v1','Unrecognized workspace.json; leave existing workspace unchanged')
    else:
        require(not (root/'assets/index.json').exists(),'Existing assets index: choose a new workspace or explicitly adapt existing layout')
        save(config,{'schema':'ip-video-workspace-v1','paths':{'assets':'assets','work':'work','inbox':'inbox','archive':'archive','tools':'tools','reports':'reports'},'categories':list(CATEGORIES)})
    for d in ('work','inbox','archive','tools','reports'):
        (root/d).mkdir(exist_ok=True)
    for d in CATEGORIES: (root/'assets'/d).mkdir(parents=True,exist_ok=True)
    if not (root/'assets/index.json').exists():save(root/'assets/index.json',{'version':1,'assets':[]})
    guide='''# 视频制作工作区\n\n先读 workspace.json 和当前 work/<任务>/project.json；本文件只约束本目录的视频制作。\n\n- assets/：跨视频复用的角色、场景、视频、截图、音乐音效、字体和模板，索引为 assets/index.json。\n- work/<日期-选题>/：每条视频独立；中间文件不写回素材库，最终文件写入本任务 deliverables/。\n- inbox/：待分类输入；archive/：明确归档的旧任务；tools/：本工作区工具环境；reports/：环境与素材盘点。\n- 用配置中的相对路径定位文件，外部工具调用时解析绝对路径，不复用参考文章或别人的电脑路径。\n- 原素材保持原位；选用后复制到当前任务并登记哈希与来源。不得自动移动、删除或覆盖原库。\n- 已有身份和定稿优先复用；生成资产经视觉/听觉检查后再入库，不将失败图和临时音频当作已验收素材。\n- 音频、分镜与成片按各任务实际配置验收；不知道的授权与来源记 unknown，不冒充已获许可。\n- 完成阶段后更新任务 STATUS.md、project.json；修改声音或文案后重做对齐与下游时序。\n- 修改产物记录版本；收尾展示最终采用、保留及拟删除清单。使用者确认具体文件和删除方式后才清理，auto模式也不自动删旧版本。\n'''
    agent=root/'AGENTS.md'
    if not agent.exists():agent.write_text(guide,encoding='utf-8')
    elif not (root/'VIDEO-WORKSPACE.md').exists():
        (root/'VIDEO-WORKSPACE.md').write_text(guide,encoding='utf-8')
    print(json.dumps({'root':str(root),'config':'workspace.json','existing_agents_preserved':(root/'VIDEO-WORKSPACE.md').exists()},ensure_ascii=False))


def root_for(a):
    root=Path(a.root).resolve()
    require(read(root/'workspace.json').get('schema')=='ip-video-workspace-v1','Run setup first')
    return root


def job(a):
    root=root_for(a)
    require(re.fullmatch(r'[\w\u4e00-\u9fff-]+',a.name) and a.name not in ('.','..'),'Use a simple name with letters, digits, Chinese or hyphens')
    slug=datetime.date.today().isoformat()+'-'+a.name
    dest=root/'work'/slug
    n=2
    while dest.exists():dest=root/'work'/f'{slug}-{n:02}';n+=1
    init(SimpleNamespace(project=str(dest),topic=a.topic))
    cfg=read(dest/'project.json')
    cfg['workspace']='../..'
    cfg['paths']={'identity':'identity','script':'script','narration':'script/narration.txt','audio':'audio','voice':'audio/vo-full.wav','alignment':'audio/vo-align.json','storyboard':'storyboard.json','shots':'shots','composition':'composition','deliverables':'deliverables','reports':'reports','references':'references','selected_assets':'selected-assets','prompts':'prompts','temp':'_tmp'}
    for d in ('references','selected-assets','prompts','_tmp'):(dest/d).mkdir()
    save(dest/'project.json',cfg)
    save(dest/'assets-used.json',{'assets':[]})
    (dest/'PATHS.md').write_text('# 当前任务路径\n\n以本文件所在目录为根；共享库：../../assets，索引：../../assets/index.json。\n\n'+'\n'.join(f'- `{k}` → `{v}`' for k,v in cfg['paths'].items())+'\n',encoding='utf-8')


def inventory(a):
    root=root_for(a); source=Path(a.source).resolve()
    require(source.is_dir(),'Source must be a directory')
    files=[]
    # Inventory only explicitly selected directory; never follows symlink directories.
    for current, dirs, names in os.walk(source,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDE and not d.startswith('.') and not (Path(current)/d).is_symlink() and (Path(current)/d).resolve()!=root)
        for name in sorted(names):
            p=Path(current)/name
            if p.is_symlink() or p.suffix.lower() not in MEDIA:continue
            files.append({'source':str(p),'bytes':p.stat().st_size,'status':'unreviewed','category':None})
    report=root/'reports'/('inventory-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
    save(report,{'source':str(source),'read_only':True,'files':files})
    print(json.dumps({'report':str(report),'files':len(files)},ensure_ascii=False))


def add(a):
    root=root_for(a); source=Path(a.source).resolve()
    require(source.is_file(),'Source file missing')
    h=digest(source); idx=root/'assets/index.json'; data=read(idx)
    for item in data['assets']:
        if item['sha256']==h and item['category']==a.category:
            require((root/item['path']).is_file() and digest(root/item['path'])==h,'Indexed asset missing or changed; repair before reuse')
            print(json.dumps(item,ensure_ascii=False));return
    dest=root/'assets'/a.category/(h+source.suffix.lower())
    if dest.exists():require(digest(dest)==h,'Destination conflict')
    else:shutil.copy2(source,dest)
    item={'id':a.category+'-'+h,'category':a.category,'path':dest.relative_to(root).as_posix(),'name':source.name,'sha256':h,'source_path':str(source),'source_url':a.source_url,'license':a.license,'tags':a.tag,'accepted':False,'review':'pending'}
    data['assets'].append(item);save(idx,data);print(json.dumps(item,ensure_ascii=False))


def select(a):
    root=root_for(a); project=Path(a.project).resolve()
    cfg=read(project/'project.json')
    require((project/cfg.get('workspace','')).resolve()==root,'Project does not belong to this workspace')
    matches=[x for x in read(root/'assets/index.json')['assets'] if x['id']==a.asset]
    require(len(matches)==1,'Asset ID not found')
    item=matches[0]
    require(item['accepted'] is True,'Inspect media and record accepted=true before use')
    source=root/item['path'];require(digest(source)==item['sha256'],'Library file changed')
    dest=project/'selected-assets'/source.name;dest.parent.mkdir(exist_ok=True)
    if dest.exists():require(digest(dest)==item['sha256'],'Project asset conflict')
    else:shutil.copy2(source,dest)
    ledger=project/'assets-used.json';data=read(ledger)
    entry={**item,'path':dest.relative_to(project).as_posix(),'library_path':item['path']}
    if not any(x['id']==item['id'] for x in data['assets']):data['assets'].append(entry);save(ledger,data)
    print(dest)


def resolve(a):
    project=Path(a.project).resolve();cfg=read(project/'project.json')
    require(a.key in cfg.get('paths',{}),'Unknown alias; consult project.json')
    path=(project/cfg['paths'][a.key]).resolve()
    require(path.is_relative_to(project),'Project path escapes task directory')
    print(path)


def install_audio(a):
    root=root_for(a); env=root/'tools/audio-venv'
    binary=shutil.which(a.python)
    require(binary is not None,'Requested Python not found; install Python3.11/3.12 first')
    if not env.exists():subprocess.run([binary,'-m','venv',str(env)],check=True)
    py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    require(py.is_file(),'Existing environment is incomplete; inspect tools/audio-venv')
    packages = {'edge': ['edge-tts==7.2.8'], 'piper': ['piper-tts'], 'external': []}[a.tts_provider]
    if a.alignment == 'stable-ts': packages.append('stable-ts==2.19.1')
    if packages: subprocess.run([str(py), '-m', 'pip', 'install', *packages], check=True)
    report=subprocess.check_output([str(py),str(Path(__file__).parent/'pipeline.py'),'doctor'],text=True)
    save(root/'reports/audio-environment.json',json.loads(report))
    print(py)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('setup');p.add_argument('root');p.set_defaults(func=setup)
    p=sub.add_parser('new-project');p.add_argument('root');p.add_argument('--name',required=True);p.add_argument('--topic',required=True);p.set_defaults(func=job)
    p=sub.add_parser('inventory');p.add_argument('root');p.add_argument('source');p.set_defaults(func=inventory)
    p=sub.add_parser('add-asset');p.add_argument('root');p.add_argument('source');p.add_argument('--category',choices=CATEGORIES,required=True);p.add_argument('--source-url',default='');p.add_argument('--license',default='unknown');p.add_argument('--tag',action='append',default=[]);p.set_defaults(func=add)
    p=sub.add_parser('select-asset');p.add_argument('root');p.add_argument('project');p.add_argument('--asset',required=True);p.set_defaults(func=select)
    p=sub.add_parser('resolve');p.add_argument('project');p.add_argument('key');p.set_defaults(func=resolve)
    p=sub.add_parser('install-audio');p.add_argument('root');p.add_argument('--python',default='python3.12');p.add_argument('--tts-provider',choices=['edge','piper','external'],required=True);p.add_argument('--alignment',choices=['stable-ts','external'],required=True);p.set_defaults(func=install_audio)
    a=parser.parse_args()
    try:a.func(a)
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as e:print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)

if __name__=='__main__':main()
