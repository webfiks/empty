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
bev.width = 0.045; bev.segments = 6; bev.limit_method = 'ANGLE'; bev.angle_limit = math.radians(30)
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
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
fl = bpy.context.object
fm, fnt, fb = principled('floor')
fb.inputs['Base Color'].default_value = (0.035, 0.035, 0.035, 1)
fb.inputs['Roughness'].default_value = 0.22
fb.inputs['Specular IOR Level'].default_value = 0.35
fl.data.materials.append(fm)

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
sc.cycles.samples = SPP; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = RES
sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'PNG'

os.makedirs(OUT, exist_ok=True)
for mk in MATS:
    W.data.materials.clear(); W.data.materials.append(MATFN[mk]())
    for an in ANGLES:
        az, el, dist = ANG[an]
        a, e = math.radians(az), math.radians(el)
        cam.location = CENTER + Vector((dist*math.sin(a)*math.cos(e), -dist*math.cos(a)*math.cos(e), dist*math.sin(e)))
        sc.render.filepath = f'{OUT}/{mk}-{an}.png'
        bpy.ops.render.render(write_still=True)
        print('DONE', sc.render.filepath, flush=True)
