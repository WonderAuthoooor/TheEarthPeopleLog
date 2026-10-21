"""把已验证VRM作为独立副本放入用户指定Warudo的官方Characters目录。"""
from pathlib import Path
import argparse
import json
import os
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from avatar3d.models import inspect_vrm,digest,atomic_json


def prepare_model(install,model,record):
    install=Path(install).resolve();model=Path(model).resolve()
    characters=(install/'Warudo_Data/StreamingAssets/Characters').resolve()
    if not (install/'Warudo.exe').is_file() or not characters.is_dir() or not characters.is_relative_to(install):
        raise ValueError('路径不是含Characters目录的完整Warudo安装。')
    info=inspect_vrm(model)
    target=characters/('AvatarLab_Test_'+info['sha256'][:12]+'.vrm')
    reused=False
    if target.exists():
        if digest(target)!=info['sha256']:raise ValueError('同名目标文件内容不同，保留原件并停止。')
        reused=True
    else:
        temporary=characters/('.avatar-import-'+uuid.uuid4().hex+'.partial')
        try:
            with temporary.open('xb') as output,model.open('rb') as source:
                shutil.copyfileobj(source,output)
                output.flush();os.fsync(output.fileno())
            if digest(temporary)!=info['sha256']:raise ValueError('复制过程中源模型发生变化。')
            # 同卷硬链接原子发布，不覆盖竞态中出现的同名文件；不让运行器看到半份VRM。
            try:os.link(temporary,target)
            except FileExistsError:
                if digest(target)!=info['sha256']:raise ValueError('目标文件在复制期间出现且内容不同，保留原件。')
                reused=True
        finally:temporary.unlink(missing_ok=True)
    result={'schema':1,'install':str(install),'character_path':str(target),'sha256':info['sha256'],
            'vrm_version':info['vrm_version'],'display_name':info['name'],'authors':info['metadata'].get('authors',[]),
            'existing_identical_reused':reused,'file_copy_verified':digest(target)==info['sha256'],
            'warudo_load_verified':False,'camera_enabled':False,
            'note':'仅放入可选模型副本；不修改场景／首选项，不代表运行器已加载，不是正式C'}
    atomic_json(record,result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--record',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare_model(args.install,args.model,args.record),ensure_ascii=False,indent=2))
