"""只读取VRM数据，不执行模型脚本；按内容哈希复制到工作区。"""
from pathlib import Path
import hashlib,json,os,struct,time,uuid

REQUIRED=('hips','spine','head','leftUpperArm','leftLowerArm','leftHand','rightUpperArm','rightLowerArm','rightHand',
          'leftUpperLeg','leftLowerLeg','leftFoot','rightUpperLeg','rightLowerLeg','rightFoot')

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('w',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        # Windows短暂打开进度文件时会阻止替换；有限重试仍保留原子发布语义。
        for attempt in range(8):
            try:
                os.replace(temporary,path)
                break
            except PermissionError:
                if os.name != 'nt' or attempt == 7:raise
                time.sleep(.05)
    finally:temporary.unlink(missing_ok=True)

def inspect_vrm(path):
    path=Path(path)
    if path.suffix.lower()!='.vrm':raise ValueError('只接受VRM；不加载可包含脚本的第三方.blend工程。')
    if not 20<=path.stat().st_size<=256*1024*1024:raise ValueError('模型大小须小于256MB且包含完整数据。')
    with path.open('rb') as f:
        header=f.read(20)
        magic,version,total,length,kind=struct.unpack('<4sIIII',header)
        if magic!=b'glTF' or version!=2 or total!=path.stat().st_size or kind!=0x4E4F534A or not 2<=length<=16*1024*1024:
            raise ValueError('VRM／GLB头或JSON区块损坏。')
        doc=json.loads(f.read(length).decode('utf-8'))
    for collection in ('buffers','images'):
        for item in doc.get(collection,[]):
            if item.get('uri') and not item['uri'].startswith('data:'):raise ValueError('模型引用外部资源，请先导出自包含VRM。')
    nodes=doc.get('nodes',[])
    if not 1<=len(nodes)<=10000:raise ValueError('模型节点异常。')
    ext=doc.get('extensions',{})
    if 'VRMC_vrm' in ext:
        vrm=ext['VRMC_vrm'];bones={k:v['node'] for k,v in vrm['humanoid']['humanBones'].items()};version='1.0'
    elif 'VRM' in ext:
        vrm=ext['VRM'];bones={b['bone']:b['node'] for b in vrm['humanoid']['humanBones']};version='0.x'
    else:raise ValueError('缺少标准VRM骨骼扩展。')
    missing=[k for k in REQUIRED if k not in bones]
    if missing:raise ValueError('缺少人形骨骼：'+', '.join(missing))
    if any(type(n)!=int or not 0<=n<len(nodes) for n in bones.values()) or len(set(bones.values()))!=len(bones):
        raise ValueError('人形骨骼节点映射无效或重复。')
    if not doc.get('skins'):raise ValueError('模型没有蒙皮骨架。')
    meta=vrm.get('meta',{})
    return {'name':str(meta.get('name',meta.get('title',path.stem)))[:120],'vrm_version':version,
            'bones':{k:nodes[v].get('name','') for k,v in bones.items()},'metadata':meta,
            'sha256':digest(path),'bytes':path.stat().st_size,'node_count':len(nodes)}

def import_model(workspace,source):
    source=Path(source).resolve();info=inspect_vrm(source)
    root=Path(workspace)/'models';root.mkdir(parents=True,exist_ok=True)
    target=root/(info['sha256']+'.vrm')
    if target.exists():
        if digest(target)!=info['sha256']:raise ValueError('工作区模型已损坏，保留文件供检查。')
    else:
        temporary=target.with_suffix('.'+uuid.uuid4().hex+'.partial')
        try:
            import shutil
            shutil.copyfile(source,temporary)
            if digest(temporary)!=info['sha256']:raise ValueError('导入期间源模型发生变化，请重试。')
            os.replace(temporary,target)
        finally:temporary.unlink(missing_ok=True)
    atomic_json(target.with_suffix('.json'),info)
    return info
