# cinematic finishing: bloom, anamorphic streak, grade, chromatic aberration, vignette, grain
import sys, numpy as np
from PIL import Image, ImageFilter
src, dst = sys.argv[1], sys.argv[2]
kw = dict(a.split('=') for a in sys.argv[3:]); f = lambda k, d: float(kw.get(k, d))
im = Image.open(src).convert('RGB'); W_, H_ = im.size; s = W_/2048
a = np.asarray(im).astype(np.float32)/255
lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
def blur(arr, r):
    return np.asarray(Image.fromarray((np.clip(arr, 0, 1)*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32)/255
hi = np.clip((lum - f('th', 0.6))/(1 - f('th', 0.6)), 0, 1)[..., None]*a
bloom = blur(hi, 6*s)*0.35 + blur(hi, 24*s)*0.35 + blur(hi, 70*s)*0.35
# anamorphic streak: very bright parts smeared horizontally, slightly warm
core = np.clip((lum - f('sth', 0.8))/(1 - f('sth', 0.8)), 0, 1)[..., None]*a
st = Image.fromarray((core*255).astype(np.uint8)).resize((max(1, W_//64), H_), Image.BILINEAR).resize((W_, H_), Image.BILINEAR)
st = np.asarray(st.filter(ImageFilter.GaussianBlur(2*s))).astype(np.float32)/255
st = st*np.array([1.0, 0.93, 0.82])*f('streak', 1.6)
o = 1 - (1 - a)*(1 - np.clip(bloom*f('bloom', 1.0), 0, 1))
o = 1 - (1 - o)*(1 - np.clip(st, 0, 1))
# grade: warm highlights, slightly cool deep shadows, gentle S-curve
L = o.mean(2, keepdims=True)
o = o*(1 + (L - 0.5)*np.array([0.10, 0.02, -0.10])*f('warm', 1.0)) + (1 - L)**4*np.array([-0.004, 0.0, 0.010])
o = np.clip(o, 0, 1); o = o + 0.10*f('contrast', 1.0)*(o - o**2)*(2*o - 1)*-1 + 0.08*f('contrast', 1.0)*np.sin(np.pi*(o - 0.5))*0.5
# saturation
L2 = o.mean(2, keepdims=True); o = np.clip(L2 + (o - L2)*f('sat', 1.0), 0, 1)
# chromatic aberration (radial)
yy, xx = np.mgrid[0:H_, 0:W_].astype(np.float32); cx, cy = W_/2, H_/2
dx, dy = (xx - cx)/cx, (yy - cy)/cy; amt = f('ca', 2.0)*s
def shift(ch, k):
    xs = np.clip(xx + dx*k, 0, W_ - 1).astype(np.int32); ys = np.clip(yy + dy*k, 0, H_ - 1).astype(np.int32); return ch[ys, xs]
o[..., 0] = shift(o[..., 0], amt); o[..., 2] = shift(o[..., 2], -amt)
# vignette + grain
r2 = dx**2 + dy**2; o *= (1 - f('vig', 0.35)*np.clip(r2/2, 0, 1)**1.3)[..., None]
rng = np.random.default_rng(3); g = rng.normal(0, f('grain', 0.022), (H_, W_)).astype(np.float32)
g = np.asarray(Image.fromarray(((g + 0.5)*255).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6*s))).astype(np.float32)/255 - 0.5
o = o + g[..., None]*(0.6 + 0.4*(1 - o))
Image.fromarray((np.clip(o, 0, 1)*255).astype(np.uint8)).save(dst)
