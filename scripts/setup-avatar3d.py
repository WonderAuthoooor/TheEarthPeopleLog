"""项目内便携Blender与固定VRM插件；不写用户插件／注册表／PATH。"""
from pathlib import Path
import sys,json,hashlib,subprocess,zipfile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from avatar3d.models import digest,atomic_json

def extract(archive,destination,strip_root=False):
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            pieces=Path(item.filename).parts
            if strip_root:pieces=pieces[1:]
            if not pieces:continue
            path=destination.joinpath(*pieces).resolve()
            if not path.is_relative_to(destination):raise ValueError('归档路径超出目标目录。')
            if item.is_dir():path.mkdir(parents=True,exist_ok=True)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                with z.open(item) as source,path.open('wb') as target:
                    import shutil
                    shutil.copyfileobj(source,target)

def main():
    lock=json.loads((ROOT/'avatar3d/assets/runtime-lock.json').read_text(encoding='utf-8'))
    downloads=ROOT/'.runtime/avatar3d-downloads';downloads.mkdir(parents=True,exist_ok=True)
    names={'blender':'blender-4.5.13-windows-x64.zip','addon':'vrm-addon-4.10.2.zip','sample':'Seed-san.vrm'}
    for key,name in names.items():
        path=downloads/name;item=lock[key]
        if not path.exists():
            partial=path.with_suffix(path.suffix+'.download')
            subprocess.run(['curl.exe','-L','--fail','--retry','2','--max-time','600','-o',str(partial),item['url']],check=True)
            if digest(partial)!=item['sha256']:raise ValueError('下载校验失败，保留下载供检查：'+str(partial))
            partial.replace(path)
        if digest(path)!=item['sha256']:raise ValueError('归档哈希不匹配，不覆盖：'+str(path))
    runtime=ROOT/'.runtime/avatar3d'
    blender=runtime/'blender-4.5.13-windows-x64/blender.exe'
    addon=runtime/'plugin'
    if not blender.exists():extract(downloads/names['blender'],runtime)
    if not (addon/'io_scene_vrm/__init__.py').exists():extract(downloads/names['addon'],addon/'io_scene_vrm',True)
    sample=ROOT/'avatar3d/assets/Seed-san.vrm'
    if not sample.exists():
        import shutil
        shutil.copyfile(downloads/names['sample'],sample)
    if digest(sample)!=lock['sample']['sha256']:raise ValueError('测试模型被修改，不覆盖。')
    atomic_json(runtime/'runtime.json',{'schema':1,'blender':str(blender),'addon':str(addon),
        'versions':{k:lock[k]['version'] for k in ('blender','addon')}})
    print(runtime/'runtime.json')

if __name__=='__main__':main()
