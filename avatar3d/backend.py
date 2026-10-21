"""独立Blender进程适配器；Qt不进入渲染器，取消只终止本任务子进程。"""
from pathlib import Path
from dataclasses import dataclass
import json,subprocess,time,os,sys,threading
from .models import atomic_json,digest

@dataclass(frozen=True)
class Runtime:
    blender:Path
    addon:Path

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        runtime=cls(Path(data['blender']),Path(data['addon']))
        if not runtime.blender.is_file() or not (runtime.addon/'io_scene_vrm/__init__.py').is_file():
            raise ValueError('Blender或VRM插件运行环境不完整，请重新执行项目环境准备。')
        return runtime

def child_options():
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}

SPAWN_LOCK=threading.Lock()

def launch_external(command,env,log):
    """冻结版的DLL搜索路径不能污染使用另一Python版本的Blender子进程。"""
    env=dict(env)
    for key in tuple(env):
        if key.startswith('_PYI_') or key in ('PYTHONHOME','PYTHONPATH'):env.pop(key,None)
    if getattr(sys,'frozen',False) and os.name=='nt':
        import ctypes
        base=str(Path(sys._MEIPASS).resolve()).lower()
        env['PATH']=os.pathsep.join(p for p in env.get('PATH','').split(os.pathsep) if not p.lower().startswith(base))
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.SetDllDirectoryW.argtypes=[ctypes.c_wchar_p];kernel.SetDllDirectoryW.restype=ctypes.c_int
        kernel.GetDllDirectoryW.argtypes=[ctypes.c_uint32,ctypes.c_wchar_p];kernel.GetDllDirectoryW.restype=ctypes.c_uint32
        with SPAWN_LOCK:
            previous=ctypes.create_unicode_buffer(32768);kernel.GetDllDirectoryW(len(previous),previous)
            if not kernel.SetDllDirectoryW(None):raise OSError('无法隔离Blender的DLL搜索路径。')
            try:return subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,**child_options())
            finally:kernel.SetDllDirectoryW(previous.value or None)
    return subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,**child_options())

class BlenderBackend:
    def __init__(self,runtime):self.runtime=runtime

    def render(self,request,folder,cancel,progress,timeout=900):
        folder=Path(folder);frames=folder/'frames';frames.mkdir(parents=True,exist_ok=True)
        model=Path(request['model'])
        if digest(model)!=request['model_sha256']:raise ValueError('模型与任务快照不一致。')
        atomic_json(folder/'backend-request.json',dict(request,folder=str(folder.resolve()),addon=str(self.runtime.addon.resolve())))
        entry=Path(__file__).parent/'blender_worker.py'
        command=[str(self.runtime.blender),'--background','--factory-startup','--disable-autoexec','--python-exit-code','23','--python',str(entry),'--',str(folder/'backend-request.json')]
        env=os.environ.copy()
        env['BLENDER_USER_CONFIG']=str(folder/'blender-config');env['BLENDER_USER_SCRIPTS']=str(folder/'blender-scripts')
        with (folder/'blender.log').open('wb') as log:
            process=launch_external(command,env,log)
            started=time.monotonic()
            try:
                while process.poll() is None:
                    if cancel.is_set():raise InterruptedError('已取消三维渲染。')
                    if time.monotonic()-started>timeout:raise TimeoutError('渲染超时，日志已保留。')
                    marker=folder/'progress.json'
                    if marker.exists():
                        try:progress(json.loads(marker.read_text(encoding='utf-8'))['percent'])
                        except (OSError,ValueError,KeyError):pass
                    time.sleep(.1)
                if process.returncode!=0:raise RuntimeError(f'Blender退出码{process.returncode}；查看本任务blender.log。')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(10)
                    except subprocess.TimeoutExpired:process.kill();process.wait(5)
        expected=round(request['duration']*request['fps'])
        files=sorted(frames.glob('*.png'))
        if len(files)!=expected or any(p.name!=f'{i:05}.png' for i,p in enumerate(files)):
            raise RuntimeError('渲染帧序列不完整，未发布成品。')
        return files
