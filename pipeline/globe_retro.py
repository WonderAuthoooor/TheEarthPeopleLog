"""Original ink-and-cel globe skin with rubber-hose motion and clean backgrounds."""
from functools import lru_cache
import math
from PIL import Image,ImageDraw,ImageFilter
from . import globe as g
from .globe_motion import pose,smooth,segment

INK='#302e25'

@lru_cache(maxsize=3)
def background(w,h):
    image=Image.new('RGB',(64,114));pixels=image.load()
    for y in range(114):
        for x in range(64):
            edge=min(1,math.hypot((x-32)/47,(y-57)/82))
            pixels[x,y]=(round(247-17*edge),round(238-20*edge),round(210-25*edge))
    image=image.resize((w,h),Image.Resampling.BICUBIC).convert('RGBA')
    d=ImageDraw.Draw(image)
    for x,y,size in ((.15,.13,.018),(.84,.18,.012),(.13,.83,.012),(.84,.87,.018)):
        x*=w;y*=h;s=size*w
        d.line((x-s,y,x+s,y),fill='#c2af83',width=max(1,round(w*.002)))
        d.line((x,y-s,x,y+s),fill='#c2af83',width=max(1,round(w*.002)))
    return image


def frame(c,progress):
    w,h=c['width'],c['height'];m=pose(c,progress);image=background(w,h).copy()
    base=round(w*.82);planet=g.globe(base,m['lat'],m['lon'],'rubberhose')
    size=max(8,round(base*m['zoom']))
    planet=planet.resize((size,size),Image.Resampling.LANCZOS)
    d=ImageDraw.Draw(planet);stroke=max(3,round(w*.007))
    d.ellipse((stroke/2,stroke/2,size-1-stroke/2,size-1-stroke/2),outline=INK,width=stroke)
    # A curved cel highlight is readable while the full globe is in view.
    d.arc((size*.05,size*.05,size*.95,size*.95),195,247,fill='#f1dfb5',width=max(2,round(w*.005)))
    planet=planet.resize((max(8,round(size*m['sx'])),max(8,round(size*m['sy']))),Image.Resampling.BICUBIC)
    if abs(m['roll'])>.01:planet=planet.rotate(m['roll'],Image.Resampling.BICUBIC,expand=True)
    cx,cy=w*.5,h*.50;x=round(cx-planet.width/2);y=round(cy-planet.height/2)
    # A soft stage shadow and ink arcs, rather than a rotating background.
    if m['zoom']<1.25:
        shadow=Image.new('RGBA',(w,h));sd=ImageDraw.Draw(shadow)
        floor=cy+size*.59;sd.ellipse((cx-size*.30,floor-size*.025,cx+size*.30,floor+size*.025),fill=(91,73,42,45))
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(1,w*.008))))
    if m['smear']>.03:
        ghost=planet.copy();ghost.putalpha(ghost.getchannel('A').point(lambda a:round(a*.20*m['smear'])))
        shift=round(w*.075*m['smear']);image.alpha_composite(ghost,(x-shift,y+round(w*.01)))
        image.alpha_composite(ghost,(x+shift,y-round(w*.01)))
        lines=ImageDraw.Draw(image)
        for i in range(3):
            pad=w*(.025+i*.022);rx=size*.55+pad;ry=size*.38+pad
            box=(cx-rx,cy-ry,cx+rx,cy+ry)
            lines.arc(box,193+i*8,247+i*5,fill=INK,width=max(2,round(w*.004)))
            lines.arc(box,12+i*8,57+i*5,fill='#a9603b',width=max(2,round(w*.004)))
    image.alpha_composite(planet,(x,y))
    if c['mode']=='intro' and c['show_hand'] and m['hand']>.001:
        hand=g.sprite(c['hand'],round(w*.49))
        arrival=smooth(segment(progress,0,.08));departure=smooth(segment(progress,.32,.48))
        angle=-13+17*smooth(segment(progress,.06,.20))
        hand=hand.rotate(angle,Image.Resampling.BICUBIC,expand=True)
        hx=round(w*.66+(1-arrival+departure)*w*.65);hy=round(h*.35-w*.04*math.sin(segment(progress,.05,.22)*math.pi))
        image.alpha_composite(hand,(hx,hy))
    if m['lock']>.001:
        px,py,z=g.project(m['point']['lat'],m['point']['lon'],m['lat'],m['lon'])
        if z>0:
            mx=cx+px*size/2;my=cy-py*size/2
            radius=w*(.017+.008*(1-m['lock']));d=ImageDraw.Draw(image)
            d.ellipse((mx-radius*1.55,my-radius*1.55,mx+radius*1.55,my+radius*1.55),fill='#f6e9c6',outline=INK,width=max(2,round(w*.003)))
            d.ellipse((mx-radius,my-radius,mx+radius,my+radius),fill='#be5838',outline=INK,width=max(2,round(w*.003)))
            d.ellipse((mx-radius*.35,my-radius*.35,mx+radius*.35,my+radius*.35),fill='#f7eacb')
    return image
