# cinematic finishing for a transparent render: works in premultiplied alpha so glow extends into clear areas
import sys, numpy as np
from PIL import Image, ImageFilter
src, dst = sys.argv[1], sys.argv[2]
kw = dict(a.split('=') for a in sys.argv[3:]); f = lambda k, d: float(kw.get(k, d))
im = Image.open(src).convert('RGBA'); W_, H_ = im.size; s = W_/2048
A = np.asarray(im).astype(np.float32)/255; al = A[..., 3:4]; c = A[..., :3]*al          # premultiplied
if kw.get('mask'):
    # stars and gas are light, not paint: outside the logo their opacity follows their brightness
    mk = np.asarray(Image.open(kw['mask']).convert('L').resize((W_, H_))).astype(np.float32)[..., None]/255
    mk = np.clip((mk - 0.05)/0.25, 0, 1)
    la = np.clip(c.max(2, keepdims=True)*f('lalpha', 1.4), 0, 1)
    al = np.maximum(mk*al, la*(1 - mk)); c = np.where(mk > 0.5, c, c)
lum = c @ np.array([0.2126, 0.7152, 0.0722], np.float32)
def blur(arr, r):
    u8 = Image.fromarray((np.clip(arr, 0, 1)*255).astype(np.uint8))
    return np.asarray(u8.filter(ImageFilter.GaussianBlur(r))).astype(np.float32)/255
hi = np.clip((lum - f('th', 0.6))/(1 - f('th', 0.6)), 0, 1)[..., None]*c
bloom = (blur(hi, 6*s) + blur(hi, 24*s) + blur(hi, 70*s))*0.35*f('bloom', 1.0)
core = np.clip((lum - f('sth', 0.8))/(1 - f('sth', 0.8)), 0, 1)[..., None]*c
st = np.asarray(Image.fromarray((np.clip(core, 0, 1)*255).astype(np.uint8)).resize((max(1, W_//64), H_), Image.BILINEAR).resize((W_, H_), Image.BILINEAR)).astype(np.float32)/255
st = blur(st, 2*s)*np.array([1.0, 0.93, 0.82])*f('streak', 1.6)
glow = np.clip(bloom + st, 0, 1)
ga = np.clip(glow.max(2, keepdims=True), 0, 1)
c = c + glow - c*glow; al = al + ga - al*ga                                               # screen, premultiplied
o = np.where(al > 1e-4, c/np.maximum(al, 1e-4), 0)                                        # back to straight colour
L = o.mean(2, keepdims=True)
o = o*(1 + (L - 0.5)*np.array([0.10, 0.02, -0.10])*f('warm', 1.0)); o = np.clip(o, 0, 1)
o = o + 0.04*np.sin(np.pi*(o - 0.5))*f('contrast', 1.0)
L2 = o.mean(2, keepdims=True); o = np.clip(L2 + (o - L2)*f('sat', 1.0), 0, 1)
yy, xx = np.mgrid[0:H_, 0:W_].astype(np.float32); cx, cy = W_/2, H_/2; dx, dy = (xx - cx)/cx, (yy - cy)/cy; amt = f('ca', 2.0)*s
def shift(ch, k):
    xs = np.clip(xx + dx*k, 0, W_ - 1).astype(np.int32); ys = np.clip(yy + dy*k, 0, H_ - 1).astype(np.int32); return ch[ys, xs]
o[..., 0] = shift(o[..., 0], amt); o[..., 2] = shift(o[..., 2], -amt)
rng = np.random.default_rng(3); g = rng.normal(0, f('grain', 0.02), (H_, W_)).astype(np.float32)
o = np.clip(o + g[..., None]*(0.6 + 0.4*(1 - o)), 0, 1)
if kw.get('mask') and f('edgefade', 0):
    # fade the galaxy (never the logo) to nothing before the image border
    yy2, xx2 = np.mgrid[0:H_, 0:W_].astype(np.float32)
    d = np.minimum.reduce([xx2, W_ - 1 - xx2, yy2, H_ - 1 - yy2])/(f('edgefade', 0.12)*W_)
    ef = np.clip(d, 0, 1); ef = (ef*ef*(3 - 2*ef))[..., None]
    al = np.maximum(mk*al, al*ef*(1 - mk))
out = np.concatenate([o, np.clip(al, 0, 1)], -1)
Image.fromarray((out*255).astype(np.uint8), 'RGBA').save(dst)
