"""可选的Windows运行期快捷键；默认不注册，关闭时全部注销。"""
import ctypes
import os
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter


class GlobalHotkeys(QAbstractNativeEventFilter):
    def __init__(self,callback):
        super().__init__()
        self.callback=callback
        self.registered={}
        self.user=None
        if os.name=='nt':
            self.user=ctypes.WinDLL('user32',use_last_error=True)
            self.user.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
            self.user.RegisterHotKey.restype=wintypes.BOOL
            self.user.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
            self.user.UnregisterHotKey.restype=wintypes.BOOL

    def enable(self,actions):
        self.disable()
        if not self.user:raise RuntimeError('后台快捷键当前仅支持Windows。')
        try:
            for i,action in enumerate(actions):
                vk=ord(str(i)) if i<10 else ord('A')
                ident=0x4600+i
                if not self.user.RegisterHotKey(None,ident,0x4000|0x0002|0x0001,vk):
                    raise RuntimeError(f'Ctrl+Alt+{chr(vk)}被占用或注册失败；本次快捷键已全部释放。')
                self.registered[ident]=action
        except Exception:
            self.disable()
            raise

    def disable(self):
        if self.user:
            for ident in tuple(self.registered):self.user.UnregisterHotKey(None,ident)
        self.registered.clear()

    def nativeEventFilter(self,event_type,message):
        if self.registered and bytes(event_type) in (b'windows_generic_MSG',b'windows_dispatcher_MSG'):
            msg=wintypes.MSG.from_address(int(message))
            if msg.message==0x0312 and int(msg.wParam) in self.registered:
                self.callback(self.registered[int(msg.wParam)])
                return True,0
        return False,0
