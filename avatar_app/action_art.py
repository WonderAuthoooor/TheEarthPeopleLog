"""原画图集读取、关节贴图、局部表情与评分道具绘制。"""
from pathlib import Path
import json,math,re
from PIL import Image,ImageDraw,ImageFilter,ImageFont,ImageOps
from .actions import joints,ROOTS

ASSETS=Path(__file__).parent/'assets/actions-v01'


def validate_score(text):
    text=str(text).strip()
    if text=='待评':return text
    if not re.fullmatch(r'[+-]?(?:[0-4](?:\.[05])?|5(?:\.0)?)',text):
        raise ValueError('评分须为待评，或-5.0至+5.0之间、以0.5递增的人工确认分数。')
    return f'{float(text):+.1f}'


def mask_for(size,feather):
    mask=Image.new('L',size)
    ImageDraw.Draw(mask).rounded_rectangle((2,2,size[0]-3,size[1]-3),radius=max(2,min(size)//5),fill=255)
    return mask.filter(ImageFilter.GaussianBlur(feather))


class ActionArt:
    def __init__(self,scale):
        self.scale=scale
        self.config=json.loads((ASSETS/'rig.json').read_text(encoding='utf-8'))
        self.canvas=(round(1024*scale),round(1536*scale))
        self.torso=Image.open(ASSETS/'torso.png').convert('RGBA').resize(self.canvas,Image.Resampling.LANCZOS)
        atlas=Image.open(ASSETS/'arms-atlas.png').convert('RGBA')
        self.sprites={name:atlas.crop(spec['box']) for name,spec in self.config['sprites'].items()}
        expressions=Image.open(ASSETS/'expressions-atlas.png').convert('RGBA')
        talking=Image.open(ASSETS/'talk-atlas.png').convert('RGBA')
        self.face={};self.talk={};self.features=[]
        for spec in self.config['features']:
            target=tuple(round(v*scale) for v in spec['target'])
            size=(target[2]-target[0],target[3]-target[1])
            self.features.append((target,mask_for(size,max(1,5*scale))))
        for name,offset in self.config['expression_cells'].items():
            patches=[]
            for index,spec in enumerate(self.config['features']):
                box=tuple(v+offset[i%2] for i,v in enumerate(spec['source']))
                target=self.features[index][0];size=(target[2]-target[0],target[3]-target[1])
                patches.append(expressions.crop(box).resize(size,Image.Resampling.LANCZOS))
                if index==2:self.talk[name]=talking.crop(box).resize(size,Image.Resampling.LANCZOS)
            self.face[name]=patches
        self.cards={}
        self.body_cache=None

    def expression(self,head,weights,neutral_talk):
        # 只替换眉眼与嘴部，不切换整个头部或更换身份。
        speech=neutral_talk
        weights={key:value for key,value in weights.items() if key!='neutral' and value>0}
        for index,(box,mask) in enumerate(self.features):
            patch=head.crop(box)
            current=0.0
            for name,weight in weights.items():
                incoming=self.face[name][index]
                if current==0:
                    combined=incoming.copy()
                else:
                    combined=Image.blend(combined,incoming,weight/(current+weight))
                current+=weight
            if current:
                head.paste(combined,box[:2],mask.point(lambda v:int(v*min(1,current))))
        current=0.0
        for name,weight in weights.items():
            if current==0:combined=self.talk[name].copy()
            else:combined=Image.blend(combined,self.talk[name],weight/(current+weight))
            current+=weight
        if current:speech=Image.blend(neutral_talk,combined,min(1,current))
        return head,speech

    def bone(self,canvas,name,start,end,side):
        spec=self.config['sprites'][name]
        texture=self.sprites[name]
        pivot=[spec['pivot'][i]-spec['box'][i] for i in (0,1)]
        tip=[spec['end'][i]-spec['box'][i] for i in (0,1)]
        if side=='left':
            texture=ImageOps.mirror(texture)
            pivot[0]=texture.width-pivot[0];tip[0]=texture.width-tip[0]
        dx,dy=end[0]-start[0],end[1]-start[1]
        ratio=math.hypot(dx,dy)*self.scale/max(.01,math.dist(pivot,tip))
        angle=math.atan2(dy,dx)-math.atan2(tip[1]-pivot[1],tip[0]-pivot[0])
        a,b=ratio*math.cos(angle),ratio*math.sin(angle)
        ox,oy=start[0]*self.scale,start[1]*self.scale
        def forward(x,y):return ox+a*(x-pivot[0])-b*(y-pivot[1]),oy+b*(x-pivot[0])+a*(y-pivot[1])
        corners=[forward(x,y) for x,y in ((0,0),(0,texture.height),(texture.width,0),(texture.width,texture.height))]
        left,top=math.floor(min(v[0] for v in corners)),math.floor(min(v[1] for v in corners))
        width=math.ceil(max(v[0] for v in corners))-left;height=math.ceil(max(v[1] for v in corners))-top
        determinant=a*a+b*b
        inverse=(a/determinant,b/determinant,pivot[0]+(a*(left-ox)+b*(top-oy))/determinant,
                 -b/determinant,a/determinant,pivot[1]+(-b*(left-ox)+a*(top-oy))/determinant)
        piece=texture.transform((width,height),Image.Transform.AFFINE,inverse,Image.Resampling.BICUBIC)
        canvas.alpha_composite(piece,(left,top))

    def body(self,pose,score='待评'):
        key=(tuple(round(v,2) for side in ROOTS for v in pose.angles[side]),
             tuple(pose.hands[s] for s in ROOTS),tuple(round(pose.hand_angles[s],2) for s in ROOTS),round(pose.card,3),score)
        if self.body_cache and self.body_cache[0]==key:return self.body_cache[1].copy()
        canvas=Image.new('RGBA',self.canvas)
        chains={side:joints(side,pose.angles[side]) for side in ROOTS}
        for side,(root,elbow,wrist) in chains.items():self.bone(canvas,'upper',root,elbow,side)
        offset=self.config['torso_offset']
        canvas.alpha_composite(self.torso,tuple(round(v*self.scale) for v in offset))
        for side,(root,elbow,wrist) in chains.items():self.bone(canvas,'fore',elbow,wrist,side)
        if pose.card>.005:
            card=self.card(score).copy()
            card.putalpha(card.getchannel('A').point(lambda v:int(v*pose.card)))
            wrists=[chain[2] for chain in chains.values()]
            center=(sum(p[0] for p in wrists)/2,sum(p[1] for p in wrists)/2)
            canvas.alpha_composite(card,(round((center[0]-235)*self.scale),round((center[1]-60)*self.scale)))
        for side,(root,elbow,wrist) in chains.items():
            name=pose.hands[side];length=self.config['sprites'][name]['length']
            angle=math.radians(pose.hand_angles[side])
            end=(wrist[0]+length*math.cos(angle),wrist[1]+length*math.sin(angle))
            self.bone(canvas,name,wrist,end,side)
        self.body_cache=(key,canvas.copy())
        return canvas

    def card(self,score):
        score=validate_score(score)
        if score in self.cards:return self.cards[score]
        # 原生绘制简单道具与可编辑文字；角色原画仍来自image_gen。
        size=(470,240);image=Image.new('RGBA',size)
        draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((5,5,465,235),radius=28,fill='#f4f1e4',outline='#283b40',width=7)
        draw.rounded_rectangle((23,23,447,217),radius=18,outline='#5aafa0',width=3)
        def font(px):
            for path in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf'):
                if Path(path).is_file():return ImageFont.truetype(path,px)
            return ImageFont.load_default(px)
        draw.text((235,55),'文明观察',font=font(30),fill='#315356',anchor='mm')
        draw.text((235,137),score+(' 分' if score!='待评' else ''),font=font(66),fill='#153b37',anchor='mm')
        result=image.resize((round(470*self.scale),round(240*self.scale)),Image.Resampling.LANCZOS)
        if len(self.cards)>30:self.cards.clear()
        self.cards[score]=result
        return result
