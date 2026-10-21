"""本机视觉结果与角色参数分离；不读摄像头、不保存帧、不访问网络。"""
from dataclasses import dataclass, asdict
from pathlib import Path
import math
import time

import numpy as np

MODELS = Path(__file__).parent/"assets/tracking"


def bounded(value, low=-1.0, high=1.0):
    value = float(value)
    return min(high,max(low,value)) if math.isfinite(value) else 0.0


@dataclass(frozen=True)
class Observation:
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    jaw: float = 0.0
    eye_left: float = 0.0  # 画面左侧眼；非解剖学左眼。
    eye_right: float = 0.0
    shoulder_roll: float | None = None


@dataclass(frozen=True)
class Motion:
    mouth: float = 0.0
    turn: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    lean: float = 0.0
    blink_left: float = 0.0
    blink_right: float = 0.0

    def kwargs(self):
        return asdict(self)


def rotation_angles(matrix):
    matrix = np.asarray(matrix,dtype=float)
    if matrix.shape != (4,4) or not np.isfinite(matrix).all():
        return 0.0,0.0,0.0
    # 去掉估计矩阵的比例，保留旋转；正面偏置由用户居中校准消除。
    u,_,vt = np.linalg.svd(matrix[:3,:3])
    rotation = u@vt
    if np.linalg.det(rotation) < 0:
        u[:,-1] *= -1
        rotation = u@vt
    yaw = math.asin(bounded(-rotation[2,0]))
    pitch = math.atan2(rotation[2,1],rotation[2,2])
    roll = math.atan2(rotation[1,0],rotation[0,0])
    return tuple(math.degrees(v) for v in (yaw,pitch,roll))


def shoulder_angle(landmarks, aspect=1.0):
    if not landmarks or len(landmarks)<13:
        return None
    left,right = landmarks[11],landmarks[12]
    if min(left.visibility,right.visibility) < .6:
        return None
    dx = (left.x-right.x)*aspect
    dy = left.y-right.y
    if not all(math.isfinite(v) for v in (dx,dy)) or abs(dx)<.03:
        return None
    # 消除左右排序造成的180度差异。
    return math.degrees(math.atan(dy/dx))


class MotionFilter:
    def __init__(self):
        self.neutral = Observation()
        self.latest = None
        self.last_seen = None
        self.last_tick = None
        self.motion = Motion()

    def observe(self,observation,now=None):
        if observation is not None:
            self.latest = observation
            self.last_seen = time.monotonic() if now is None else now

    def calibrate(self,now=None):
        now = time.monotonic() if now is None else now
        if self.latest is None or self.last_seen is None or now-self.last_seen > .5:
            return False
        self.neutral = self.latest
        return True

    def sample(self,now=None,mirror=True):
        now = time.monotonic() if now is None else now
        dt = min(.15,max(.001,now-self.last_tick)) if self.last_tick is not None else 1/20
        self.last_tick = now
        live = self.latest is not None and self.last_seen is not None and now-self.last_seen <= .45
        if live:
            raw,base = self.latest,self.neutral
            sign = -1 if mirror else 1
            lean = ((raw.shoulder_roll-(base.shoulder_roll or 0))/12
                    if raw.shoulder_roll is not None else 0)
            def closure(value,baseline):
                return bounded((value-baseline)/max(.2,1-baseline),0,1)
            left = closure(raw.eye_left,base.eye_left)
            right = closure(raw.eye_right,base.eye_right)
            target = Motion(mouth=bounded((raw.jaw-base.jaw-.025)/.45,0,1),
                turn=sign*bounded((raw.yaw-base.yaw)/25),
                pitch=bounded((raw.pitch-base.pitch)/18),
                roll=sign*bounded((raw.roll-base.roll)/20),lean=sign*bounded(lean),
                blink_left=right if mirror else left,blink_right=left if mirror else right)
        else:
            target = Motion()
        previous = self.motion.kwargs()
        values = {}
        for key,value in target.kwargs().items():
            # 眼／口快速响应；头与肩更平稳。丢失后回正，不维持张嘴闭眼。
            tau = .028 if key.startswith("blink") or key=="mouth" else .10
            alpha = 1-math.exp(-dt/tau)
            values[key] = previous[key]+(value-previous[key])*alpha
        self.motion = Motion(**values)
        return self.motion,live


class MediaPipeEngine:
    """由调用者提供RGB图，按时间戳推理。关闭对象释放原生资源。"""
    def __init__(self,body=True):
        import mediapipe as mp
        self.mp = mp
        vision = mp.tasks.vision
        options = vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=(MODELS/"face_landmarker.task").read_bytes()),
            running_mode=vision.RunningMode.VIDEO,num_faces=1,
            output_face_blendshapes=True,output_facial_transformation_matrixes=True)
        self.face = vision.FaceLandmarker.create_from_options(options)
        self.pose = None
        try:
            if body:
                self.pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_buffer=(MODELS/"pose_landmarker_lite.task").read_bytes()),
                    running_mode=vision.RunningMode.VIDEO,num_poses=1))
        except BaseException:
            self.face.close()
            raise
        self.timestamp = -1
        self.frame_index = 0
        self.last_shoulder = None
        self.last_shoulder_time = -10000

    def detect(self,rgb,timestamp_ms):
        timestamp_ms = max(self.timestamp+1,int(timestamp_ms))
        self.timestamp = timestamp_ms
        data = np.ascontiguousarray(rgb,dtype=np.uint8)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=data)
        face = self.face.detect_for_video(image,timestamp_ms)
        # 身体每两帧推理一次；不积压视频帧。
        if self.pose and self.frame_index%2 == 0:
            pose = self.pose.detect_for_video(image,timestamp_ms)
            self.last_shoulder = shoulder_angle(pose.pose_landmarks[0] if pose.pose_landmarks else None,
                                                data.shape[1]/data.shape[0])
            self.last_shoulder_time = timestamp_ms
        self.frame_index += 1
        if not face.face_landmarks:
            return None
        scores = {c.category_name:c.score for c in face.face_blendshapes[0]} if face.face_blendshapes else {}
        angles = rotation_angles(face.facial_transformation_matrixes[0]) if face.facial_transformation_matrixes else (0,0,0)
        shoulder = self.last_shoulder if timestamp_ms-self.last_shoulder_time<500 else None
        return Observation(*angles,jaw=scores.get("jawOpen",0),eye_left=scores.get("eyeBlinkRight",0),
                           eye_right=scores.get("eyeBlinkLeft",0),shoulder_roll=shoulder)

    def close(self):
        self.face.close()
        if self.pose:
            self.pose.close()
