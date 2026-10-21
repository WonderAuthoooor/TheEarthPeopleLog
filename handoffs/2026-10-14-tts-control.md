# 配音语调细调工具调研
时间：2026-10-14T21:45:36+08:00（Asia/Shanghai）

用户希望逐句调语调以减少AI感，尚未决定替换音色。
- 微软Speech Studio Audio Content Creation提供可视化语速、音高、读音和停顿编辑；SSML支持局部控制，具体音色支持范围不同。
- ElevenLabs v3/v4提供内嵌情绪/表达标签；属于引导，不保证每次准确执行。
- 豆包TTS2.0提供语音指令，可分段生成；接口能力不等于所有网页提供对应按钮。
- ElevenLabs Voice Changer保留原录音节奏与口音，不能保证解决用户普通话不标准的问题。

来源：
https://speech.microsoft.com/audiocontentcreation
https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/speech-synthesis-markup-voice
https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech
https://elevenlabs.io/docs/eleven-creative/playground/voice-changer
https://docs.volcengine.com/docs/DoubaoVoice/HTTPChunkedSSEUnidirectionalStreaming-V3?lang=zh

已完成官方公开资料检索；未实测工具、试听、付费或生成音频。建议先同稿试听，再对少量关键句细调，不逐字拆开导致语流破碎。未改长期决策。已有未提交改动保留，不提交或推送。
