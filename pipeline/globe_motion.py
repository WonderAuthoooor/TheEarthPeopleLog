"""Deterministic camera and squash/stretch timeline, independent of the renderer."""
import math


def clamp(value):return max(0.,min(1.,value))
def smooth(value):
    t=clamp(value);return t*t*(3-2*t)
def segment(p,start,end):return clamp((p-start)/(end-start))
def mix(a,b,t):return a+(b-a)*t


def pose(config,progress):
    p=clamp(progress);a=config['origin'];b=config['target']
    delta=(b['lon']-a['lon']+180)%360-180
    if config['mode']=='intro':
        aim=smooth(segment(p,.25,.80))
        spin=1080*(1-(1-segment(p,.10,.72))**3)
        recoil=9*math.sin(math.pi*segment(p,.68,.88)) if .68<p<.88 else 0
        lat=mix(a['lat'],b['lat'],aim);lon=a['lon']+delta*aim+spin+recoil
        zoom=mix(.84,2.25,smooth(segment(p,.54,.90)))
        contact=math.exp(-((p-.10)/.045)**2)
        rebound=math.exp(-((p-.19)/.055)**2)
        sx=1+.22*contact-.08*rebound;sy=1-.18*contact+.10*rebound
        wobble=math.sin(segment(p,.13,.76)*math.pi*6)*(1-segment(p,.13,.76))
        roll=-9*math.sin(math.pi*segment(p,0,.12)) if p<.12 else 12*wobble
        smear=math.sin(math.pi*segment(p,.10,.67))**.7 if .10<p<.67 else 0
        hand=1-smooth(segment(p,.32,.48))
        point=b
        lock=smooth(segment(p,.84,.91))
        phase='anticipation' if p<.10 else ('spin' if p<.55 else ('push-in' if p<.90 else 'hold'))
    else:
        aim=smooth(segment(p,.18,.79))
        lat=mix(a['lat'],b['lat'],aim);lon=a['lon']+delta*aim
        zoom=mix(2.25,.80,smooth(segment(p,0,.24))) if p<.24 else mix(.80,2.25,smooth(segment(p,.35,.90)))
        spring=math.sin(math.pi*aim)*math.sin(math.pi*aim*2)
        sx=1+.045*spring;sy=1-.035*spring;roll=3*spring
        smear=.27*math.sin(math.pi*segment(p,.20,.70)) if .20<p<.70 else 0
        hand=0;point=a if p<.14 else b
        lock=1-smooth(segment(p,.06,.14)) if p<.14 else smooth(segment(p,.84,.91))
        phase='pull-out' if p<.24 else ('travel' if p<.79 else ('settle' if p<.91 else 'hold'))
    if p>=.91:
        lat,lon=b['lat'],b['lon'];zoom=2.25;sx=sy=1.;roll=smear=hand=0.;lock=1.
    if p==0 and config['mode']=='transition':lat,lon=a['lat'],a['lon'];sx=sy=1.;roll=0.;lock=1.
    return {'lat':lat,'lon':(lon+180)%360-180,'zoom':zoom,'sx':sx,'sy':sy,'roll':roll,
            'smear':smear,'hand':hand,'lock':lock,'point':point,'phase':phase}
