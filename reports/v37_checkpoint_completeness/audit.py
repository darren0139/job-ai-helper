"""Read-only source/Git inventory; writes only this diagnostic directory."""
from pathlib import Path
import ast, hashlib, json, os, subprocess, zipfile, io
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
ENV=dict(os.environ,GIT_OPTIONAL_LOCKS='0',PYTHONDONTWRITEBYTECODE='1')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,env=ENV)
def h(b):return hashlib.sha256(b).hexdigest()
def save(name,v): (OUT/name).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
index=ROOT/'.git/index'
start={'head':git('rev-parse','HEAD').decode().strip(),'branch':git('branch','--show-current').decode().strip(),'index_sha256':h(index.read_bytes()),'db_sha256':h((ROOT/'data/applications.db').read_bytes())}
paths=git('ls-tree','-r','--name-only','HEAD').decode().splitlines()
requested=[p for p in paths if p.endswith(('.py','.json','.txt','.toml','.md','.bat','.js','.html'))]
batch=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,env=ENV,input=''.join('HEAD:'+p+'\n' for p in requested).encode(),capture_output=True,check=True).stdout
blobs={}; offset=0
for p in requested:
    end=batch.index(b'\n',offset); header=batch[offset:end].split();size=int(header[-1]);offset=end+1
    blobs[p]=batch[offset:offset+size];offset+=size+1
status=git('status','--porcelain=v1','-z','--untracked-files=all').decode().split('\0')
items=[]
for line in status:
    if not line:continue
    xy=line[:2];p=line[3:];f=ROOT/p
    items.append({'path':p,'status':xy,'tracked':xy!='??','working_sha256':h(f.read_bytes()) if f.is_file() else None,
      'checkpoint_sha256':h(blobs[p]) if p in blobs else None})
commitpaths=git('diff-tree','--no-commit-id','--name-only','-r','HEAD').decode().splitlines()
old=json.loads((ROOT/'reports/v37_release_readiness/checkpoint_commit.json').read_text(encoding='utf-8'))
manifest={r['path']:r['checkpoint_sha256'] for r in old['files']}
def module(p):return p[:-3].replace('/','.') if not p.endswith('/__init__.py') else p[:-12].replace('/','.')
modpaths={module(p):p for p in paths if p.endswith('.py')}
localroots={m.split('.')[0] for m in modpaths}
workingpaths=set(paths)|{r['path'] for r in items}
workingmod={module(p):p for p in workingpaths if p.endswith('.py')}
def scan(path,data,known):
    try: tree=ast.parse(data.decode('utf-8-sig'),filename=path)
    except Exception as e:return [],[{'path':path,'error':str(e)}]
    edges=[]
    for n in ast.walk(tree):
        targets=[]
        if isinstance(n,ast.Import):targets=[a.name for a in n.names]
        elif isinstance(n,ast.ImportFrom):
            base=n.module or ''
            if n.level:
                pkg=module(path).split('.') if path.endswith('/__init__.py') else module(path).split('.')[:-1]
                base='.'.join(pkg[:len(pkg)-n.level+1]+([base] if base else []))
            targets=[base]+[base+'.'+a.name for a in n.names if base+'.'+a.name in workingmod]
        elif isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str):targets=[n.args[0].value]
        for target in targets:
            if target.split('.')[0] not in localroots:continue
            if target in known:edges.append({'from':path,'line':n.lineno,'module':target,'to':known[target],'missing':False})
            elif target in workingmod:edges.append({'from':path,'line':n.lineno,'module':target,'to':workingmod[target],'missing':True})
            elif not any(k.startswith(target+'.') for k in known):edges.append({'from':path,'line':n.lineno,'module':target,'to':None,'missing':True})
    return edges,[]
edges=[];errors=[]
for p,b in blobs.items():
    if p.endswith('.py'):
        e,x=scan(p,b,modpaths);edges+=e;errors+=x
workedges=[]
for p in sorted(workingpaths):
    if p.endswith('.py') and (ROOT/p).is_file():
        e,_=scan(p,(ROOT/p).read_bytes(),workingmod);workedges+=e
incoming={}
for e in workedges:incoming.setdefault(e['to'],[]).append({'path':e['from'],'line':e['line'],'module':e['module']})
for r in items:r['incoming_working_imports']=incoming.get(r['path'],[])
byfrom={}
for e in edges:byfrom.setdefault(e['from'],[]).append(e)
reachable={'app.py'}; todo=['app.py'];missing=[]
while todo:
    p=todo.pop()
    for e in byfrom.get(p,[]):
        if e['missing']:missing.append(e)
        elif e['to'] not in reachable:reachable.add(e['to']);todo.append(e['to'])
save('preflight.json',start);save('inventory_raw.json',items)
save('dependency_graph.json',{'edges':edges,'syntax_errors':errors,'all_missing_local_imports':[e for e in edges if e['missing']],
 'app_transitively_reachable':sorted(reachable),'app_missing_imports':missing})
save('manifest_verification.json',{'expected_count':len(manifest),'actual_count':len(commitpaths),'missing_from_commit':sorted(set(manifest)-set(commitpaths)),
 'unlisted_committed':sorted(set(commitpaths)-set(manifest)),'hash_mismatches':[p for p,v in manifest.items() if h(blobs[p] if p in blobs else git('show','HEAD:'+p))!=v],
 'commit_parent':git('rev-parse','HEAD^').decode().strip(),'master':git('rev-parse','master').decode().strip(),
 'merge_base':git('merge-base','HEAD','master').decode().strip()})
# Verification archive contains exactly committed tree, no uncommitted code/fixtures.
tree=OUT/'committed_tree';tree.mkdir(exist_ok=True)
archive=git('archive','--format=zip','HEAD')
with zipfile.ZipFile(io.BytesIO(archive)) as z:z.extractall(tree)
save('archive.json',{'root':str(tree),'git_archive_sha256':h(archive),'files':len(paths),'private_fixture_present':(tree/'data/bullet_choice_benchmark/v1.json').exists()})
print(json.dumps({'status_paths':len(items),'manifest_paths':len(commitpaths),'app_reachable_modules':len(reachable),'app_missing_imports':missing,'all_missing_local_imports':[e for e in edges if e['missing']],'syntax_errors':errors},indent=2))
