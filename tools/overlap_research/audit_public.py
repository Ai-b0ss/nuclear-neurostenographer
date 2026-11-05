"""Read-only primary-source provenance snapshot. Never executes fetched candidate code."""
import json
import urllib.request
from common import LOCAL,owned,write_json

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Issue10-local-research'}),timeout=90) as r:
        return json.load(r)

if __name__=='__main__':
    owned(LOCAL)
    report={}
    for repo in ('BUTSpeechFIT/DiCoP','0xShug0/audio.cpp'):
        try:
            info=get('https://api.github.com/repos/'+repo)
            commit=get('https://api.github.com/repos/'+repo+'/commits/'+info['default_branch'])['sha']
            tree=get('https://api.github.com/repos/'+repo+'/git/trees/'+commit+'?recursive=1')
            paths=[x['path'] for x in tree['tree']]
            report[repo]=dict(commit=commit,url='https://github.com/'+repo+'/tree/'+commit,
                license=info.get('license'),license_files=[p for p in paths if p.lower().split('/')[-1].startswith(('license','copying','notice'))],
                android_paths=[p for p in paths if any(x in p.lower() for x in ('android','jni','ndk'))],
                truncated=tree.get('truncated',False),scope='Live repository metadata/tree only; paths do not prove Android execution')
        except Exception as e:report[repo]=dict(status='BLOCKED',reason=str(e))
    try:
        m=get('https://huggingface.co/api/models/BUT-FIT/DiCoP_v0.1')
        report['dicop_checkpoint']=dict(sha=m.get('sha'),card=m.get('cardData'),storage=m.get('usedStorage'),siblings=[s['rfilename'] for s in m.get('siblings',[])])
    except Exception as e:report['dicop_checkpoint']=dict(status='BLOCKED',reason=str(e))
    write_json(LOCAL/'public-audit.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
