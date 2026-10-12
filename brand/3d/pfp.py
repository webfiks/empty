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

MATFN = {'steel': mat_steel, 'black': mat_black}

# ---------- floor: glossy black studio surface ----------
# curved cyclorama: floor sweeping up into a back wall, no horizon seam
prof = [(y, 0.0) for y in range(-60, 13, 4)]
R = 12.0
prof += [(12 + R*math.sin(t*math.pi/2/24), R - R*math.cos(t*math.pi/2/24)) for t in range(1, 25)]
prof += [(12 + R, z) for z in range(int(R) + 4, 64, 4)]
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
fb.inputs['Roughness'].default_value = 0.16
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
sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'PNG'


from bpy_extras.object_utils import world_to_camera_view
RIG = {n: tuple(bpy.data.objects[n].location) for n in ('key','fill','rim','top','kick')}
SHOTS = {'steel-turned': ('steel', -16, 9, 0.0), 'steel-front': ('steel', -16, 9, 0.0), 'black-front': ('black', -16, 9, 0.15), 'steel-hero': ('steel', -30, 3, -1.3)}
FILL, CY = float(args.get('fill', 0.74)), float(args.get('cy', 0.54))


dg = bpy.context.evaluated_depsgraph_get()
def wverts():
    e = W.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [e.matrix_world @ v.co for v in e.data.vertices]

os.makedirs(OUT, exist_ok=True)
for name in args.get('shots', ','.join(SHOTS)).split(','):
    mk, az, el, ev = SHOTS[name]; sc.view_settings.exposure = ev
    W.rotation_euler = (0, 0, math.radians(float(args.get('rotz', 0)) if name == 'steel-turned' else 0))
    from mathutils import Matrix
    lr = math.radians(float(args.get('rotz', 0)) * float(args.get('lightk', 0))) if name == 'steel-turned' else 0
    Rm = Matrix.Rotation(lr, 4, 'Z')
    for ln, base in RIG.items():
        o = bpy.data.objects[ln]; o.location = CENTER + Rm @ (Vector(base) - CENTER)
        o.rotation_euler = (CENTER - o.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    W.data.materials.clear(); W.data.materials.append(MATFN[mk]())
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
    sw = bpy.data.objects['sweep']; sw.data.energy = 0
    if name == 'steel-turned':
        n = (Matrix.Rotation(W.rotation_euler.z, 4, 'Z') @ Vector((0, -1, 0))).normalized()
        r = (2*n.dot(dirv)*n - dirv).normalized()
        sw.location = CENTER + r*14 + Vector((0, 0, float(args.get('swz', 2.0))))
        sw.rotation_euler = (CENTER - sw.location).to_track_quat('-Z', 'Y').to_euler()
        sw.data.energy = float(args.get('sweep', 300))
    sc.render.filepath = f'{OUT}/{name}.png'
    bpy.ops.render.render(write_still=True)
    print('DONE', name, round(dist, 2), round(cd.shift_x, 3), round(cd.shift_y, 3), flush=True)
