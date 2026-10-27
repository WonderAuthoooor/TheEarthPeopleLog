# 原生格式核实与检查范围

2026-10-25T16:30:00+08:00。版本Warudo0.15.1；读取本机保存的C_Test_v001.json和Warudo_Data/Managed程序集。未启用设备、未加载新场景。

- 原生场景提供Character／Camera类型、资源URI、EnumArray字段、F8节点及连线。源待机仍引用旧Wave1a8b0452b3f5；新场景改为已构建Idlea5c207ac973a。原场景不变。
- 只读反射确认AnimationMaskedBodyPart：Root0、Body1、Head2、LeftLeg3、RightLeg4、LeftArm5、RightArm6、LeftFingers7、RightFingers8、LeftFoot9、RightFoot10。
- 通过本机Trivial.Mono.Cecil读取Warudo.Core.Graphs.DataInputPort.Deserialize：EnumArray反序列化为SerializedEnum[]；字段label:string/value:Int64/description:string/icon:string。因此不是裸数字数组。
- 读取CharacterAsset.CreateAvatarMask方法IL：先禁用所有部位，再启用所选部位。Native MaskUpperBody内数组为5/6/7/8/2；本次使用5/6/7/8，不包含Head2。
- 10项回归结果见tests.txt；真实安装／依赖SHA／节点端口和旧文件保护见delivery.json。保留表情图、插件数据和原机位；新增讲解图并加入层级。
- 完整场景可能含用户插件设置，仅保存在忽略的工作素材和Warudo目录，不纳入Git；证据只存哈希和检查摘要。
- Python结构验证和本机程序集检查不等于Unity运行时反序列化、加载、实际动作混合、摄像头或OBS验收。上述均待人工恢复，不能勾选通过。

官方依据：https://docs.warudo.app/docs/assets/character 、https://docs.warudo.app/docs/assets/camera 、https://docs.warudo.app/docs/mocap/mediapipe 。

环境说明：默认沙箱临时目录拒绝访问、系统短路径临时目录出现WinError6；将测试TEMP/TMP限制到项目.runtime后10项全部通过。未因此修改业务原子写入函数，也未扩大重试掩盖错误。
