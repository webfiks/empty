import bpy, bmesh, math, sys, os
from mathutils import Vector

args = dict(a.split('=', 1) for a in sys.argv[1:])
OUT = args.get('out', '/tmp/r')
RES = int(args.get('res', 512)); SPP = int(args.get('spp', 64))
MATS = args.get('mats', 'steel,black').split(',')
ANGLES = args.get('angles', 'front').split(',')

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------- geometry: W traced from webfiks.no logo (units: logo px * 0.1) ----------
def quad(p0, c, p1, n=10):
    return [((1-t)**2*p0[0]+2*(1-t)*t*c[0]+t*t*p1[0], (1-t)**2*p0[1]+2*(1-t)*t*c[1]+t*t*p1[1]) for t in [i/n for i in range(1, n+1)]]
POLYS = [
    [(0,0),(16.5,0),(31,25.5),(41,25.5),(35,37),(21,37)],
    [(26,0),(43,0),(57.5,25.5),(68,25.5),(61.5,37),(47,37)],
    [(53,0),(70.5,0),(75.2,9.4)] + quad((75.2,9.4),(76.6,12.4),(74.6,15.2)) + [(68,25.5),(67.5,25.5)],
]
K = 0.1; DEPTH = 0.75
bm = bmesh.new()
for poly in POLYS:
    vs = [bm.verts.new(((x - 38.3)*K, 0, (37 - y)*K)) for x, y in poly]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.y > 0: f.normal_flip()          # front faces the camera (-Y)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, DEPTH, 0))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
me = bpy.data.meshes.new('W'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
W = bpy.data.objects.new('W', me); sc.collection.objects.link(W)
if args.get('logo') == 'cc':
    # BRACC "CC" from the owner's SVG: import, mesh, extrude to the same depth as the W, stand it up
    import addon_utils; addon_utils.enable('io_curve_svg', default_set=True)
    bpy.ops.import_curve.svg(filepath=args['svg'])
    C = [o for o in bpy.data.objects if o.type == 'CURVE'][0]
    C.data.dimensions = '2D'; C.data.fill_mode = 'BOTH'; C.data.resolution_u = 48
    bpy.context.view_layer.objects.active = C; C.select_set(True)
    bpy.ops.object.convert(target='MESH'); C = bpy.context.view_layer.objects.active
    cm = C.data; cm.transform(C.matrix_world)
    xs = [v.co.x for v in cm.vertices]; ys = [v.co.y for v in cm.vertices]
    k = 3.7 / (max(ys) - min(ys)); cx = (max(xs) + min(xs)) / 2; y0 = min(ys)
    cbm2 = bmesh.new(); cbm2.from_mesh(cm)
    bmesh.ops.remove_doubles(cbm2, verts=cbm2.verts, dist=1e-6)
    for v in cbm2.verts: v.co = Vector(((v.co.x - cx)*k, 0, (v.co.y - y0)*k))
    for f in cbm2.faces:
        f.normal_update()
        if f.normal.y > 0: f.normal_flip()
    r2 = bmesh.ops.extrude_face_region(cbm2, geom=list(cbm2.faces))
    bmesh.ops.translate(cbm2, verts=[g for g in r2['geom'] if isinstance(g, bmesh.types.BMVert)], vec=(0, DEPTH, 0))
    bmesh.ops.recalc_face_normals(cbm2, faces=cbm2.faces)
    me2 = bpy.data.meshes.new('CC'); cbm2.to_mesh(me2); cbm2.free()
    for p in me2.polygons: p.use_smooth = True
    W.data = me2; bpy.data.objects.remove(C)
bev = W.modifiers.new('bevel', 'BEVEL')
bev.width = 0.06; bev.segments = 8; bev.limit_method = 'ANGLE'; bev.angle_limit = math.radians(30)
bev.harden_normals = True; bev.profile = 0.5
CENTER = Vector((0, DEPTH/2, 2.05))

# ---------- materials ----------
def principled(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    return m, nt, b

def mat_steel():
    m, nt, b = principled('steel'); N = nt.nodes; L = nt.links
    b.inputs['Base Color'].default_value = (0.80, 0.80, 0.81, 1)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Anisotropic'].default_value = 0.85
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (0.6, 260, 260)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.0; nz.inputs['Detail'].default_value = 12
    nz.inputs['Roughness'].default_value = 0.65
    L.new(mp.outputs['Vector'], nz.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 0.16; mr.inputs['To Max'].default_value = 0.34
    L.new(nz.outputs['Fac'], mr.inputs['Value']); L.new(mr.outputs['Result'], b.inputs['Roughness'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.12; bp.inputs['Distance'].default_value = 0.002
    L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    t = N.new('ShaderNodeCombineXYZ'); t.inputs['X'].default_value = 1.0
    L.new(t.outputs['Vector'], b.inputs['Tangent'])
    return m

def mat_black():
    m, nt, b = principled('black'); N = nt.nodes; L = nt.links
    b.inputs['Base Color'].default_value = (0.010, 0.010, 0.011, 1)
    b.inputs['Roughness'].default_value = 0.52
    b.inputs['Specular IOR Level'].default_value = 0.55
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 4
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.08; bp.inputs['Distance'].default_value = 0.001
    L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def mat_titanium():
    m, nt, b = principled('titanium'); N = nt.nodes; L = nt.links
    b.inputs['Base Color'].default_value = (0.542, 0.497, 0.449, 1)   # measured titanium reflectance
    b.inputs['Metallic'].default_value = 1.0
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1400; nz.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    big = N.new('ShaderNodeTexNoise'); big.inputs['Scale'].default_value = 1.2; big.inputs['Detail'].default_value = 2
    L.new(tc.outputs['Object'], big.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 0.27; mr.inputs['To Max'].default_value = 0.31
    L.new(big.outputs['Fac'], mr.inputs['Value']); L.new(mr.outputs['Result'], b.inputs['Roughness'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.06; bp.inputs['Distance'].default_value = 0.0008
    L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

MATFN = {'steel': mat_steel, 'black': mat_black, 'titanium': mat_titanium}

# ---------- floor: glossy black studio surface ----------
# curved cyclorama: floor sweeping up into a back wall, no horizon seam
prof = [(y, 0.0) for y in range(-60, 13, 2)]
R = float(args.get('cove', 12.0))
prof += [(12 + R*math.sin(t*math.pi/2/64), R - R*math.cos(t*math.pi/2/64)) for t in range(1, 65)]
prof += [(12 + R, z) for z in range(int(R) + 2, 80, 2)]
cbm = bmesh.new()
rows = [[cbm.verts.new((x, y, z)) for y, z in prof] for x in (-80, 80)]
for i in range(len(prof) - 1):
    cbm.faces.new((rows[0][i], rows[0][i+1], rows[1][i+1], rows[1][i]))
bmesh.ops.recalc_face_normals(cbm, faces=cbm.faces)
for f in cbm.faces:
    if f.normal.z < -0.1 or f.normal.y > 0.1: f.normal_flip()
cme = bpy.data.meshes.new('cyc'); cbm.to_mesh(cme); cbm.free()
for p in cme.polygons: p.use_smooth = True
fl = bpy.data.objects.new('cyc', cme); sc.collection.objects.link(fl)
fm, fnt, fb = principled('floor')
fb.inputs['Base Color'].default_value = (0.035, 0.035, 0.035, 1)
fb.inputs['Roughness'].default_value = float(args.get('floorrough', 0.16))
fb.inputs['Specular IOR Level'].default_value = 0.35
fl.data.materials.append(fm)
# scale the floor's mirror reflection without touching its diffuse response
_out = fm.node_tree.nodes['Material Output']; _b = fm.node_tree.nodes['Principled BSDF']
_mix = fm.node_tree.nodes.new('ShaderNodeMixShader'); _tr = fm.node_tree.nodes.new('ShaderNodeBsdfTransparent')
_dif = fm.node_tree.nodes.new('ShaderNodeBsdfDiffuse'); _dif.inputs['Color'].default_value = (0.035, 0.035, 0.035, 1)
_add = fm.node_tree.nodes.new('ShaderNodeAddShader')
_mix.inputs['Fac'].default_value = 1 - float(args.get('refl', 1.0))
_hold = fm.node_tree.nodes.new('ShaderNodeHoldout')
fm.node_tree.links.new(_b.outputs['BSDF'], _mix.inputs[1])
fm.node_tree.links.new(_dif.outputs['BSDF'], _mix.inputs[2])
fm.node_tree.links.new(_mix.outputs['Shader'], _out.inputs['Surface'])

# ---------- world: black ----------
wd = bpy.data.worlds.new('w'); sc.world = wd; wd.use_nodes = True
wd.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)

# ---------- lights: softbox studio (linked to the W only) ----------
WONLY = bpy.data.collections.new('Wonly'); WONLY.objects.link(W)
FONLY = bpy.data.collections.new('Fonly'); FONLY.objects.link(fl)
sd = bpy.data.lights.new('floorspot', 'SPOT'); sd.energy = 4000; sd.spot_size = math.radians(55); sd.spot_blend = 1.0; sd.shadow_soft_size = 1.2
so = bpy.data.objects.new('floorspot', sd); so.location = (-1.5, -2.5, 10); sc.collection.objects.link(so)
so.rotation_euler = (Vector((0, 0.6, 0)) - so.location).to_track_quat('-Z', 'Y').to_euler()
so.light_linking.receiver_collection = FONLY
wd2 = bpy.data.lights.new('wallspot', 'SPOT'); wd2.energy = float(args.get('wall', 9000)); wd2.spot_size = math.radians(70); wd2.spot_blend = 1.0; wd2.shadow_soft_size = 2
wo = bpy.data.objects.new('wallspot', wd2); wo.location = (0, -6, 14); sc.collection.objects.link(wo)
wo.rotation_euler = (Vector((0, 24, 5)) - wo.location).to_track_quat('-Z', 'Y').to_euler()
wo.light_linking.receiver_collection = FONLY
def area(name, loc, size, power, sx=None, aim=CENTER, spread=180):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = power
    d.shape = 'RECTANGLE'; d.size = size; d.size_y = sx or size; d.spread = math.radians(spread)
    o = bpy.data.objects.new(name, d); o.location = loc; sc.collection.objects.link(o)
    o.rotation_euler = (aim - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    o.light_linking.receiver_collection = WONLY
    return o
area('key',  (-6, -7, 7), 4.0, 650)
area('fill', (7, -8, 2.5), 6.0, 160, spread=60)
area('rim',  (3, 8, 6), 3.0, 900)
area('top',  (0, -2, 10), 9.0, 300, sx=2.0)
area('kick', (-8, 4, 1.5), 2.0, 260)
area('sweep', (0, -14, 4), 9.0, 0, sx=4.0)
if args.get('rig') == 'studio':
    for n_ in ('key', 'fill', 'rim', 'top', 'kick'): bpy.data.objects[n_].data.energy = 0
    G = float(args.get('gain', 1.0))
    area('s_top',   (0, -1.5, 10), 9.0, 700*G, sx=4.0)                      # big overhead softbox
    area('s_left',  (-7.5, -3.5, 2.6), 0.7, 520*G, sx=8.0)                  # tall strip, left
    area('s_right', (7.5, -2.5, 2.6), 0.7, 420*G, sx=8.0)                   # tall strip, right
    area('s_bl',    (-4.5, 7, 4.5), 0.6, 380*G, sx=7.0)                     # back rim strips
    area('s_br',    (4.5, 7, 4.5), 0.6, 380*G, sx=7.0)
    area('s_front', (0, -11, 0.8), 7.0, 70*G, sx=1.6)                       # low front fill

# ---------- camera ----------
target = bpy.data.objects.new('t', None); target.location = CENTER; sc.collection.objects.link(target)
cd = bpy.data.cameras.new('cam'); cd.lens = 85
cd.dof.use_dof = True; cd.dof.focus_object = target; cd.dof.aperture_fstop = 5.6
cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
tr = cam.constraints.new('TRACK_TO'); tr.target = target; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
ANG = {  # azimuth (deg, 0 = straight on), elevation (deg), distance
    'front':  (-16, 9, 29),
    'right':  (40, 13, 28),
    'hero':   (-30, 3, 27),
    'high':   (20, 36, 31),
}

# ---------- render settings ----------
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = SPP; sc.cycles.adaptive_threshold = 0.008; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = RES
sc.render.film_transparent = args.get('transparent') == '1'
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA' if args.get('transparent') == '1' else 'RGB'


from bpy_extras.object_utils import world_to_camera_view
RIG = {}
SHOTS = {'ti-turned': ('titanium', -16, 9, 0.0), 'steel-up': ('steel', -16, float(args.get('elup', -3.5)), -0.4), 'steel-turned': ('steel', -16, 9, 0.0), 'steel-front': ('steel', -16, 9, 0.0), 'black-front': ('black', -16, 9, 0.15), 'steel-hero': ('steel', -30, 3, -1.3)}
FILL, CY = float(args.get('fill', 0.74)), float(args.get('cy', 0.54))


dg = bpy.context.evaluated_depsgraph_get()
def wverts():
    e = W.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [e.matrix_world @ v.co for v in e.data.vertices]

ENVOBJS = []
if args.get('env') == 'galaxy':
    import numpy as np
    rng = np.random.default_rng(7)
    fl.hide_render = True
    so.data.energy = 0; wo.data.energy = 0

    # ---- sky: star field + faint warm nebula on the world ----
    wn = wd.node_tree; WN = wn.nodes; WL = wn.links
    bg = WN['Background']
    tcw = WN.new('ShaderNodeTexCoord')
    def starlayer(scale, size, gain):
        v = WN.new('ShaderNodeTexVoronoi'); v.inputs['Scale'].default_value = scale; v.inputs['Randomness'].default_value = 1
        WL.new(tcw.outputs['Generated'], v.inputs['Vector'])
        mr = WN.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0; mr.inputs['From Max'].default_value = size
        mr.inputs['To Min'].default_value = 1; mr.inputs['To Max'].default_value = 0
        WL.new(v.outputs['Distance'], mr.inputs['Value'])
        pw = WN.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 3
        WL.new(mr.outputs['Result'], pw.inputs[0])
        sep = WN.new('ShaderNodeSeparateColor'); WL.new(v.outputs['Color'], sep.inputs['Color']); STARCOL.append(v)
        th = WN.new('ShaderNodeMath'); th.operation = 'GREATER_THAN'; th.inputs[1].default_value = 0.72   # only some cells hold a star
        WL.new(sep.outputs['Red'], th.inputs[0])
        m1 = WN.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; WL.new(pw.outputs['Value'], m1.inputs[0]); WL.new(th.outputs['Value'], m1.inputs[1])
        m2 = WN.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; m2.inputs[1].default_value = gain
        WL.new(m1.outputs['Value'], m2.inputs[0]); return m2
    STARCOL = []
    a1 = starlayer(260, float(args.get('skysize', 0.12)), float(args.get('skygain', 8))); a2 = starlayer(700, float(args.get('skysize', 0.12))*1.3, float(args.get('skygain', 8))*0.5)
    st = WN.new('ShaderNodeMath'); st.operation = 'ADD'; WL.new(a1.outputs['Value'], st.inputs[0]); WL.new(a2.outputs['Value'], st.inputs[1])
    nb = WN.new('ShaderNodeTexNoise'); nb.inputs['Scale'].default_value = 1.6; nb.inputs['Detail'].default_value = 10; nb.inputs['Roughness'].default_value = 0.62
    WL.new(tcw.outputs['Generated'], nb.inputs['Vector'])
    cr = WN.new('ShaderNodeValToRGB'); e_ = cr.color_ramp.elements
    e_[0].position = 0.5; e_[0].color = (0, 0, 0, 1); e_[1].position = 0.9; e_[1].color = (0.016, 0.006, 0.010, 1)
    WL.new(nb.outputs['Fac'], cr.inputs['Fac'])
    # stellar colour by temperature: blue-white, white, yellow, orange
    sp_ = WN.new('ShaderNodeSeparateColor'); WL.new(STARCOL[0].outputs['Color'], sp_.inputs['Color'])
    tr = WN.new('ShaderNodeValToRGB'); el = tr.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0.62, 0.74, 1.0, 1); el[1].position = 1.0; el[1].color = (1.0, 0.62, 0.36, 1)
    e2 = el.new(0.35); e2.color = (0.95, 0.96, 1.0, 1); e3 = el.new(0.7); e3.color = (1.0, 0.9, 0.72, 1)
    WL.new(sp_.outputs['Green'], tr.inputs['Fac'])
    sc_ = WN.new('ShaderNodeMix'); sc_.data_type = 'RGBA'; sc_.blend_type = 'MULTIPLY'; sc_.inputs['Factor'].default_value = 1
    cc_ = WN.new('ShaderNodeCombineColor')
    for ch in ('Red', 'Green', 'Blue'): WL.new(st.outputs['Value'], cc_.inputs[ch])
    WL.new(cc_.outputs['Color'], sc_.inputs[6]); WL.new(tr.outputs['Color'], sc_.inputs[7])
    class _W: pass
    _w = _W(); _w.outputs = {'Color': sc_.outputs[2]}; sc_ = _w
    ad = WN.new('ShaderNodeMix'); ad.data_type = 'RGBA'; ad.blend_type = 'ADD'; ad.inputs['Factor'].default_value = 1
    WL.new(cr.outputs['Color'], ad.inputs[6]); WL.new(sc_.outputs['Color'], ad.inputs[7])
    lp = WN.new('ShaderNodeLightPath')
    mx = WN.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs['Factor'].default_value = 1
    # camera sees the sky; reflections see a dimmer version so the metal stays readable
    dim = WN.new('ShaderNodeMix'); dim.data_type = 'RGBA'; dim.blend_type = 'MULTIPLY'; dim.inputs['Factor'].default_value = 1
    dim.inputs[7].default_value = (0.35, 0.35, 0.35, 1); WL.new(ad.outputs[2], dim.inputs[6])
    WL.new(lp.outputs['Is Camera Ray'], mx.inputs['Factor']); WL.new(dim.outputs[2], mx.inputs[6]); WL.new(ad.outputs[2], mx.inputs[7])
    WL.new(mx.outputs[2], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0

    # ---- Milky Way style barred spiral: bar + bulge, 4 log-spiral arms, young blue stars,
    #      pink HII regions, an old yellow disk, and dark dust lanes on the arms' inner edges ----
    RG = float(args.get('grad', 46.0)); NS = int(args.get('stars', 900000))
    def lerp(c1, c2, t): return c1*(1 - t) + c2*t
    OLD = np.array([1.0, 0.80, 0.56]); DISK = np.array([1.0, 0.90, 0.78]); YOUNG = np.array([0.48, 0.66, 1.0]); HII = np.array([1.0, 0.34, 0.46])
    pitch = math.radians(float(args.get('pitch', 19))); r0 = 0.16; barang = math.radians(28)
    def arm_theta(r, k): return k*np.pi/2 + barang + np.log(r/r0)/math.tan(pitch)
    parts_P, parts_C, parts_R = [], [], []
    def add(P, C, R): parts_P.append(P); parts_C.append(C); parts_R.append(R)
    # bulge
    n = int(NS*float(args.get('bulgefrac', 0.10))); rb = np.abs(rng.normal(0, float(args.get('bulge', 0.055)), n)); u = rng.normal(size=(n, 3)); u /= np.linalg.norm(u, axis=1)[:, None]
    P = u*rb[:, None]; P[:, 2] *= 0.6
    add(P, OLD*rng.lognormal(0.5, 0.5, (n, 1))*1.6*float(args.get('bulgegain', 1.0)), np.full(n, float(args.get('bulgesize', 0.9))))
    # bar
    n = int(NS*0.07); P = rng.normal(0, 1, (n, 3))*[0.16, 0.045, 0.03]
    ca, sa = math.cos(barang), math.sin(barang); P = P @ np.array([[ca, sa, 0], [-sa, ca, 0], [0, 0, 1]])
    add(P, OLD*rng.lognormal(0.3, 0.5, (n, 1))*1.2, np.full(n, 0.9))
    # old disk (diffuse, everywhere)
    n = int(NS*0.30); r = rng.exponential(0.28, n*2); r = r[(r > 0.04) & (r < 1)][:n]; n = len(r); t = rng.uniform(0, 2*np.pi, n)
    P = np.stack([r*np.cos(t), r*np.sin(t), rng.normal(0, 0.012, n)], 1)
    add(P, DISK*rng.lognormal(-0.25, 0.6, (n, 1))*np.exp(-r/0.45)[:, None], np.full(n, 1.0))
    # arms: young stars tight to the arm ridge
    n = int(NS*0.40); k = rng.choice(4, n, p=[0.32, 0.18, 0.32, 0.18])
    r = r0 + rng.exponential(0.30, n*2)[:n]; keep = r < 1.0; r, k = r[keep], k[keep]; n = len(r)
    th = arm_theta(r, k) + rng.normal(0, 0.15 + 0.09*r, n)
    P = np.stack([r*np.cos(th), r*np.sin(th), rng.normal(0, 0.008, n)], 1)
    mix = rng.random(n)[:, None]
    add(P, lerp(YOUNG, DISK, mix*0.35)*rng.lognormal(-0.1, 0.8, (n, 1))*np.exp(-r/0.6)[:, None]*1.3, np.full(n, 1.0))
    # HII regions: pink clumps on the outer edge of the arms
    nc = int(args.get('hii', 260)); kc = rng.choice(4, nc); rc = r0 + rng.uniform(0.08, 0.85, nc)
    tc_ = arm_theta(rc, kc) - 0.07
    m_ = 26; P = np.repeat(np.stack([rc*np.cos(tc_), rc*np.sin(tc_), np.zeros(nc)], 1), m_, 0) + rng.normal(0, 0.009, (nc*m_, 3))*[1, 1, 0.4]
    add(P, HII*rng.lognormal(0.2, 0.5, (nc*m_, 1))*1.4, np.full(nc*m_, 1.2))
    P = np.concatenate(parts_P)*RG; C = np.concatenate(parts_C); RS_ = np.concatenate(parts_R)
    rad = RS_*(0.04 + 0.05*rng.random(len(P)))*RG/46*float(args.get('starsize', 1.0))
    col = np.concatenate([C, np.ones((len(C), 1))], 1).astype(np.float32)
    cav = float(args.get('cavity', 0))                    # keep the logo clear: no stars inside this radius
    # view direction in the galaxy's own frame (galaxy frame = view basis @ Rx(tilt) @ Rz(spin))
    from mathutils import Matrix as _M
    Minv = _M.Rotation(-math.radians(float(args.get('gspin', 30))), 3, 'Z') @ _M.Rotation(-math.radians(float(args.get('gtilt', 55))), 3, 'X')
    vloc = np.array((Minv @ Vector((0, 0, 1)))[:]); rloc = np.array((Minv @ Vector((1, 0, 0)))[:]); uloc = np.array((Minv @ Vector((0, 1, 0)))[:])
    DCAM = float(args.get('dcam', 20.0)); RX, RY = cav, cav*float(args.get('cavy', 0.68))
    def clear(P_):                                     # drop stars inside the logo's silhouette cone toward the camera
        a_ = P_ @ vloc; k_ = np.clip((DCAM - a_)/DCAM, 0.05, None)
        x_ = (P_ @ rloc)/(RX*k_); y_ = (P_ @ uloc)/(RY*k_)
        return ~((x_**2 + y_**2 < 1) & (a_ > -0.6))
    if cav:
        keep = clear(P); P, col, rad = P[keep], col[keep], rad[keep]
    # dust lanes: dark, non-emissive grains on the inner (trailing) edge of each arm, slightly above the disk
    nd = int(args.get('dustlanes', 260000)); k = rng.choice(4, nd, p=[0.32, 0.18, 0.32, 0.18])
    r = r0*0.7 + rng.exponential(0.30, nd*2)[:nd]; keep = (r < 0.95) & (r > float(args.get('lanemin', 0))); r, k = r[keep], k[keep]; nd = len(r)
    th = arm_theta(r, k) + 0.09 + rng.normal(0, 0.05, nd)
    PD = np.stack([r*np.cos(th), r*np.sin(th), 0.004 + np.abs(rng.normal(0, 0.006, nd))], 1)*RG
    radd = (0.05 + 0.07*rng.random(nd))*RG/46
    if cav:
        keep = clear(PD); PD, radd = PD[keep], radd[keep]

    def pointcloud(name, P, rad, mat, col=None):
        m = bpy.data.meshes.new(name); m.vertices.add(len(P)); m.vertices.foreach_set('co', P.astype(np.float32).ravel())
        if col is not None:
            ca_ = m.attributes.new('scol', 'FLOAT_COLOR', 'POINT'); ca_.data.foreach_set('color', col.ravel())
        ra_ = m.attributes.new('srad', 'FLOAT', 'POINT'); ra_.data.foreach_set('value', rad.astype(np.float32))
        o = bpy.data.objects.new(name, m); sc.collection.objects.link(o)
        g = bpy.data.node_groups.new(name + 'gn', 'GeometryNodeTree')
        g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        gi = g.nodes.new('NodeGroupInput'); go = g.nodes.new('NodeGroupOutput')
        m2p = g.nodes.new('GeometryNodeMeshToPoints'); na = g.nodes.new('GeometryNodeInputNamedAttribute')
        na.data_type = 'FLOAT'; na.inputs['Name'].default_value = 'srad'
        smt = g.nodes.new('GeometryNodeSetMaterial'); smt.inputs['Material'].default_value = mat
        g.links.new(gi.outputs[0], m2p.inputs['Mesh']); g.links.new(na.outputs['Attribute'], m2p.inputs['Radius'])
        g.links.new(m2p.outputs['Points'], smt.inputs['Geometry']); g.links.new(smt.outputs['Geometry'], go.inputs[0])
        o.modifiers.new('pts', 'NODES').node_group = g
        for a_ in ('visible_diffuse', 'visible_shadow', 'visible_glossy'): setattr(o, a_, False)
        return o
    smat = bpy.data.materials.new('starmat'); smat.use_nodes = True; SN = smat.node_tree.nodes; SL = smat.node_tree.links
    SN.remove(SN['Principled BSDF'])
    at = SN.new('ShaderNodeAttribute'); at.attribute_name = 'scol'
    es = SN.new('ShaderNodeEmission'); es.inputs['Strength'].default_value = float(args.get('starpow', 6))
    SL.new(at.outputs['Color'], es.inputs['Color']); SL.new(es.outputs['Emission'], SN['Material Output'].inputs['Surface'])
    dmat = bpy.data.materials.new('lanemat'); dmat.use_nodes = True; DNN = dmat.node_tree.nodes
    DNN.remove(DNN['Principled BSDF']); hb = DNN.new('ShaderNodeBsdfDiffuse'); hb.inputs['Color'].default_value = (0, 0, 0, 1)
    dmat.node_tree.links.new(hb.outputs['BSDF'], DNN['Material Output'].inputs['Surface'])
    G = pointcloud('galaxy', P, rad, smat, col)
    GD = pointcloud('lanes', PD, radd, dmat); GD.parent = G
    for a_ in ('visible_diffuse', 'visible_shadow'): setattr(G, a_, False)
    ENVOBJS.append(G)

    # ---- particle simulation: glowing dust swirling around the logo ----
    bpy.ops.mesh.primitive_torus_add(major_radius=float(args.get('ring', 6.5)), minor_radius=float(args.get('ringw', 1.1)), location=CENTER)
    em_ = bpy.context.object; em_.rotation_euler = (math.radians(float(args.get('ringtilt', 10))), math.radians(-6), 0)
    ps = em_.modifiers.new('dust', 'PARTICLE_SYSTEM').particle_system.settings
    ps.count = int(args.get('dust', 2200)); ps.frame_start = 1; ps.frame_end = 1; ps.lifetime = 1000
    ps.emit_from = 'VOLUME'; ps.distribution = 'RAND'; ps.normal_factor = 0; ps.factor_random = 0.25
    ps.physics_type = 'NEWTON'; ps.effector_weights.gravity = 0; ps.use_rotations = True; ps.rotation_mode = 'VEL'
    em_.show_instancer_for_render = False; ps.render_type = 'OBJECT'; ps.particle_size = 1.0; ps.size_random = 0.8
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=float(args.get('grain', 0.008)), location=(0, 0, 0))
    grain = bpy.context.object; grain.scale = (float(args.get('streak', 7)), 1, 1)
    bpy.ops.object.transform_apply(scale=True); grain.location = CENTER
    dm = bpy.data.materials.new('dust'); dm.use_nodes = True; DN = dm.node_tree.nodes
    DN.remove(DN['Principled BSDF']); de = DN.new('ShaderNodeEmission')
    de.inputs['Color'].default_value = (1.0, 0.80, 0.60, 1); de.inputs['Strength'].default_value = float(args.get('dustpow', 14))
    dm.node_tree.links.new(de.outputs['Emission'], DN['Material Output'].inputs['Surface'])
    pi_ = DN.new('ShaderNodeParticleInfo'); pw_ = DN.new('ShaderNodeMath'); pw_.operation = 'POWER'; pw_.inputs[1].default_value = 3
    dm.node_tree.links.new(pi_.outputs['Random'], pw_.inputs[0])
    mr_ = DN.new('ShaderNodeMapRange'); mr_.inputs['To Min'].default_value = 0.15; mr_.inputs['To Max'].default_value = float(args.get('dustpow', 14))
    dm.node_tree.links.new(pw_.outputs['Value'], mr_.inputs['Value']); dm.node_tree.links.new(mr_.outputs['Result'], de.inputs['Strength'])
    grain.data.materials.append(dm); ps.instance_object = grain; grain.hide_render = False
    for a_ in ('visible_diffuse', 'visible_shadow'): setattr(grain, a_, False)
    bpy.ops.object.effector_add(type='VORTEX', location=CENTER); vx = bpy.context.object
    vx.rotation_euler = em_.rotation_euler; vx.field.strength = float(args.get('vortex', 4.0)); vx.field.flow = 0
    bpy.ops.object.effector_add(type='TURBULENCE', location=CENTER); tb_ = bpy.context.object
    tb_.field.strength = 1.6; tb_.field.size = 2.5; tb_.field.noise = 0
    bpy.ops.object.effector_add(type='FORCE', location=CENTER); fc = bpy.context.object
    fc.field.strength = float(args.get('push', 0.0)); fc.field.shape = 'POINT'                      # gentle outward push keeps dust off the logo
    FR = int(args.get('frame', 60)); sc.frame_start = 1; sc.frame_end = FR
    ps_sys = em_.particle_systems[0]; ps_sys.point_cache.frame_start = 1; ps_sys.point_cache.frame_end = FR
    sc.frame_set(1)
    with bpy.context.temp_override(scene=sc, active_object=em_, object=em_, point_cache=ps_sys.point_cache):
        bpy.ops.ptcache.bake_all(bake=True)
    sc.frame_set(FR)
    if args.get('dbg'):
        import numpy as np
        pe = em_.evaluated_get(bpy.context.evaluated_depsgraph_get()).particle_systems[0].particles
        L_ = np.array([tuple(p.location) for p in pe if p.alive_state == 'ALIVE']); V_ = np.array([tuple(p.velocity) for p in pe if p.alive_state == 'ALIVE'])
        d_ = np.linalg.norm(L_ - np.array(CENTER), axis=1)
        print('Z rel', np.percentile(L_[:,2]-CENTER.z,[5,50,95]).round(2), 'X', np.percentile(L_[:,0]-CENTER.x,[5,50,95]).round(2), 'Y', np.percentile(L_[:,1]-CENTER.y,[5,50,95]).round(2)); print('PARTICLES alive', len(L_), 'dist min/med/max', d_.min().round(2), np.median(d_).round(2), d_.max().round(2), 'speed med', np.median(np.linalg.norm(V_, axis=1)).round(2), flush=True)
    sc.render.use_motion_blur = args.get('mblur', '1') == '1'; sc.render.motion_blur_shutter = float(args.get('shutter', 0.6))
    ENVOBJS += [em_]
    DUST = em_
    # warm fill from the galaxy core so the metal picks up its colour
    area('g_core', tuple(float(v) for v in args.get('coreloc', '6,10,8').split(',')), float(args.get('coresize', 6.0)), float(args.get('corepow', 500)))
    bpy.data.lights['g_core'].color = (1.0, 0.82, 0.62)
    cd.dof.aperture_fstop = float(args.get('fstop', 8))

os.makedirs(OUT, exist_ok=True)
for name in args.get('shots', ','.join(SHOTS)).split(','):
    mk, az, el, ev = SHOTS[name]; sc.view_settings.exposure = ev
    W.rotation_euler = (0, 0, math.radians(float(args.get('rotz', 0)) if name in ('steel-turned', 'steel-up', 'ti-turned') else 0))
    from mathutils import Matrix
    lr = math.radians(float(args.get('rotz', 0)) * float(args.get('lightk', 0))) if name == 'steel-turned' else 0
    Rm = Matrix.Rotation(lr, 4, 'Z')
    for ln, base in RIG.items():
        o = bpy.data.objects[ln]; o.location = CENTER + Rm @ (Vector(base) - CENTER)
        o.rotation_euler = (CENTER - o.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    W.data.materials.clear(); W.data.materials.append(MATFN[mk]())
    cd.lens = float(args.get('lensup', 50)) if name == 'steel-up' else 85
    a, e = math.radians(az), math.radians(el)
    dirv = Vector((math.sin(a)*math.cos(e), -math.cos(a)*math.cos(e), math.sin(e)))
    dist = 28; cd.shift_x = cd.shift_y = 0
    vs = wverts()
    for _ in range(6):
        cam.location = CENTER + dirv*dist; bpy.context.view_layer.update()
        p = [world_to_camera_view(sc, cam, v) for v in vs]
        xs = [q.x for q in p]; ys = [q.y for q in p]
        span = max(max(xs)-min(xs), max(ys)-min(ys))
        dist *= span / FILL
        cd.shift_x += ((max(xs)+min(xs))/2 - 0.5)
        cd.shift_y += ((max(ys)+min(ys))/2 - CY)
    t = (12 + R - CENTER.y) / -dirv.y; P = CENTER - dirv*t + Vector((0, 0, float(args.get('glowz', 1.5))))
    wo.location = (P.x, 7, P.z + 5)
    wo.rotation_euler = (P - wo.location).to_track_quat('-Z', 'Y').to_euler()
    G_ = bpy.data.objects.get('galaxy')
    if G_:
        from mathutils import Matrix
        view = -dirv; right = view.cross(Vector((0, 0, 1))).normalized(); up = right.cross(view).normalized()
        G_.location = CENTER + view*float(args.get('gd', 260)) + right*float(args.get('gx', 24)) + up*float(args.get('gz', 22))
        R0 = Matrix((right, up, dirv)).transposed().to_4x4()
        G_.matrix_world = Matrix.Translation(G_.location) @ R0 @ Matrix.Rotation(math.radians(float(args.get('gtilt', 55))), 4, 'X') @ Matrix.Rotation(math.radians(float(args.get('gspin', 30))), 4, 'Z')
        bpy.context.view_layer.update()
    if args.get('optical'):
        # optical centering: centre the W's visual mass (its silhouette centroid), then lift it slightly
        import numpy as np, tempfile
        em = bpy.data.materials.get('maskem') or bpy.data.materials.new('maskem'); em.use_nodes = True
        nn = em.node_tree.nodes; nn.clear(); e_ = nn.new('ShaderNodeEmission'); o_ = nn.new('ShaderNodeOutputMaterial')
        em.node_tree.links.new(e_.outputs['Emission'], o_.inputs['Surface'])
        keep = (W.data.materials[0], sc.render.resolution_x, sc.cycles.samples, sc.cycles.use_denoising, cd.dof.use_dof, sc.view_settings.view_transform)
        keepfl = fl.hide_render; W.data.materials[0] = em; fl.hide_render = True
        glow = []                                           # switch emitters off instead of hiding (hiding resets the particle sim)
        for mn_ in ('dust', 'starmat'):
            mt_ = bpy.data.materials.get(mn_)
            if mt_:
                en_ = [n for n in mt_.node_tree.nodes if n.type == 'EMISSION'][0]; glow.append((en_, en_.inputs['Strength'].default_value)); en_.inputs['Strength'].default_value = 0
        bgn_ = wd.node_tree.nodes['Background']; glow.append((bgn_, bgn_.inputs['Strength'].default_value)); bgn_.inputs['Strength'].default_value = 0
        sc.render.resolution_x = sc.render.resolution_y = 512; sc.cycles.samples = 4; sc.cycles.use_denoising = False
        cd.dof.use_dof = False; sc.view_settings.view_transform = 'Standard'
        OY = float(args.get('opty', 0.47))
        for _ in range(3):
            tmp = os.path.join(tempfile.gettempdir(), 'wmask.png'); sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(tmp, check_existing=False)
            px = np.array(img.pixels[:]).reshape(512, 512, 4)[::-1, :, 0]; bpy.data.images.remove(img)
            ys, xs = np.mgrid[0:512, 0:512]; w_ = px.sum()
            cx, cy = (px*xs).sum()/w_/512, (px*ys).sum()/w_/512      # cy measured from the top
            cd.shift_x += cx - 0.5; cd.shift_y += OY - cy
            print('centroid', round(cx, 4), round(cy, 4), flush=True)
        W.data.materials[0] = keep[0]; fl.hide_render = keepfl
        for n_, v_ in glow: n_.inputs['Strength'].default_value = v_
        sc.render.resolution_x = sc.render.resolution_y = keep[1]; sc.cycles.samples = keep[2]; sc.cycles.use_denoising = keep[3]
        cd.dof.use_dof = keep[4]; sc.view_settings.view_transform = keep[5]
    sw = bpy.data.objects['sweep']; sw.data.energy = 0
    if name in ('steel-turned', 'ti-turned'):
        n = (Matrix.Rotation(W.rotation_euler.z, 4, 'Z') @ Vector((0, -1, 0))).normalized()
        r = (2*n.dot(dirv)*n - dirv).normalized()
        sw.location = CENTER + r*14 + Vector((0, 0, float(args.get('swz', 2.0))))
        sw.rotation_euler = (CENTER - sw.location).to_track_quat('-Z', 'Y').to_euler()
        sw.data.energy = float(args.get('sweep', 300))
    if args.get('env') == '2':
        so.data.energy = 0; wo.data.energy = 0
        sl = bpy.data.objects.get('setlight')
        if not sl:
            sd2 = bpy.data.lights.new('setlight', 'AREA'); sd2.shape = 'RECTANGLE'; sd2.size = 16; sd2.size_y = 9
            sl = bpy.data.objects.new('setlight', sd2); sc.collection.objects.link(sl)
            sl.light_linking.receiver_collection = FONLY
        sl.data.energy = float(args.get('setpow', 2500)); sl.data.spread = math.radians(float(args.get('spread', 180)))
        aim = CENTER + Vector((0, float(args.get('setback', 6)), -CENTER.z))
        sl.location = aim + Vector((dirv.x*4, -6, 13))
        sl.rotation_euler = (aim - sl.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f'{OUT}/{name}.png'
    bpy.ops.render.render(write_still=True)
    if args.get('savemask'):
        # logo silhouette at full resolution (white logo, everything else dark) for alpha compositing
        mk_ = bpy.data.materials.get('maskem')
        kept = (W.data.materials[0], sc.cycles.samples, sc.cycles.use_denoising, sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure, sc.render.film_transparent)
        W.data.materials[0] = mk_; sc.cycles.samples = 16; sc.cycles.use_denoising = False
        sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0; sc.render.film_transparent = False
        gl_ = []
        for mn_ in ('dust', 'starmat'):
            mt_ = bpy.data.materials.get(mn_)
            if mt_:
                en_ = [n for n in mt_.node_tree.nodes if n.type == 'EMISSION'][0]; gl_.append((en_, en_.inputs['Strength'].default_value)); en_.inputs['Strength'].default_value = 0
        bgn_ = wd.node_tree.nodes['Background']; gl_.append((bgn_, bgn_.inputs['Strength'].default_value)); bgn_.inputs['Strength'].default_value = 0
        lights_ = [(l, l.energy) for l in bpy.data.lights]
        for l, _ in lights_: l.energy = 0
        sc.render.filepath = f'{OUT}/{name}-mask.png'; bpy.ops.render.render(write_still=True)
        for l, e_ in lights_: l.energy = e_
        for n_, v_ in gl_: n_.inputs['Strength'].default_value = v_
        W.data.materials[0], sc.cycles.samples, sc.cycles.use_denoising, sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure, sc.render.film_transparent = kept
    print('DONE', name, round(dist, 2), round(cd.shift_x, 3), round(cd.shift_y, 3), flush=True)
