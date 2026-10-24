"""VRM1 aa绑定适配；只拥有嘴形键，保留骨骼和眨眼。"""
from .audio_mouth import at, validate_track


class MouthPose:
    def __init__(self, arm, track):
        import bpy
        self.track = validate_track(track)
        ext = arm.data.vrm_addon_extension
        if not ext.is_vrm1():raise ValueError('音频口型首版需要VRM1的aa表情绑定。')
        expressions = ext.vrm1.expressions.all_name_to_expression_dict()
        expression = expressions.get('aa')
        if not expression or not expression.morph_target_binds:raise ValueError('模型缺少aa嘴形，不能生成口播。')
        self.bindings = {}
        for bind in expression.morph_target_binds:
            obj = bpy.data.objects.get(bind.node.mesh_object_name)
            if not obj or not obj.data.shape_keys or bind.index not in obj.data.shape_keys.key_blocks:
                raise ValueError('aa嘴形绑定无效。')
            key = obj.data.shape_keys.key_blocks[bind.index]
            ident = (obj.name, key.name)
            previous = self.bindings.get(ident, (key, 0.))[1]
            self.bindings[ident] = (key, previous + bind.weight)
        if not any(weight > 0 for _,weight in self.bindings.values()):raise ValueError('aa嘴形权重为零。')
        owned = set(self.bindings)
        for name in ('blink', 'blinkLeft', 'blinkRight'):
            blink = expressions.get(name)
            if blink and any((b.node.mesh_object_name,b.index) in owned for b in blink.morph_target_binds):
                raise ValueError('嘴形与眨眼共用形状键，需修正模型后再叠加。')

    def apply(self, seconds, frame):
        value = at(self.track, seconds)
        for key, weight in self.bindings.values():
            key.value = min(1., value*weight)
            key.keyframe_insert('value', frame=frame)
        return value
