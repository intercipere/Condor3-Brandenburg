"""Erzeugt eine Waldkiefer (Pinus sylvestris, typischer Brandenburger Forst) prozedural und rendert sie als Billboard.

Aufruf: blender -b --python kiefer_blender.py -- <ausgabe.png> [seed]
Ausgabe: 1024 x 1024 RGBA, Seitenansicht orthografisch, transparenter Hintergrund.
Abbildung: Stammfuß bei Pixel (512, 1000), Baumhöhe HOEHE m = 940 px (für das Einpassen in die Condor-Baumtextur).

Merkmale: Gruppe aus drei Altkiefern (astfreier Stamm, unten graubraun, oben gedämpft fuchsrot, Krone etwa obere Hälfte,
breit aus dichten, dunkel blaugrünen Nadelbüscheln) und zwei Jungkiefern im Unterstand, damit eine Waldzelle geschlossen wirkt.
"""
import math
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HOEHE = 22.0
argv = sys.argv[sys.argv.index("--") + 1:]
AUSGABE = argv[0]
rng = np.random.default_rng(int(argv[1]) if len(argv) > 1 else 7)


def leer():
    for sammlung in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for x in list(sammlung):
            sammlung.remove(x)


def material(name, farbe, rauh=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*farbe, 1)
    b.inputs["Roughness"].default_value = rauh
    return m


def objekt(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def zylinder(bm, a, b, r0, r1, seg=8, mat=0):
    """Kegelstumpf von Punkt a nach b."""
    a, b = Vector(a), Vector(b)
    achse = b - a
    geo = bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r0, radius2=r1, depth=achse.length)
    vs = geo["verts"]
    rot = Vector((0, 0, 1)).rotation_difference(achse.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=rot, verts=vs)
    bmesh.ops.translate(bm, vec=(a + b) / 2, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mat


KUGELN = []  # (x, y, z, radius, material) aller Nadelbüschel; am Ende in einem Rutsch als Netz gebaut


def nadelbueschel(mitte, r, mat):
    """Lockerer, abgeflachter Nadelballen aus vielen kleinen Büscheln -> fransige, durchbrochene Silhouette."""
    n = int(60 * r * r) + 20
    for _ in range(n):
        d = rng.normal(0, 1, 3)
        d = d / (np.linalg.norm(d) + 1e-9) * rng.uniform(0, 1) ** 0.6 * r
        d[2] *= 0.5
        m = mat if rng.random() < 0.7 else 2 + int(rng.integers(0, 3))
        KUGELN.append((mitte[0] + d[0], mitte[1] + d[1], mitte[2] + d[2], rng.uniform(0.10, 0.22), m))


def nadelnetz(mats):
    """Alle Büschel als abgeflachte Ikosphären (einzeln per bmesh.ops wäre quadratisch langsam)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    bm.verts.index_update()
    v0 = np.array([v.co[:] for v in bm.verts]); v0[:, 2] *= 0.6
    f0 = np.array([[v.index for v in f.verts] for f in bm.faces]); bm.free()
    K = np.array(KUGELN)
    V = (K[:, None, :3] + K[:, None, 3:4] * v0[None]).reshape(-1, 3)
    F = (f0[None] + (np.arange(len(K)) * len(v0))[:, None, None]).reshape(-1, 3)
    me = bpy.data.meshes.new("Nadeln")
    me.from_pydata(V.tolist(), [], F.tolist())
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", np.repeat(K[:, 4].astype(np.int32), len(f0)))
    me.update()
    ob = bpy.data.objects.new("Nadeln", me)
    bpy.context.scene.collection.objects.link(ob)
    print(f"{len(K)} Nadelbüschel, {len(F)} Dreiecke")


def stamm(bm, ox, oy, h, r_fuss, mat_unten, mat_oben):
    """Leicht gebogener Stamm, gibt die Stützpunkte zurück."""
    pts = [Vector((ox, oy, 0))]
    for k in range(1, 9):
        pts.append(Vector((ox + rng.normal(0, 0.12) * k / 8, oy + rng.normal(0, 0.12) * k / 8, h * k / 8)))
    for k in range(8):
        r0 = r_fuss * (1 - 0.8 * k / 8); r1 = r_fuss * (1 - 0.8 * (k + 1) / 8)
        zylinder(bm, pts[k], pts[k + 1], r0, r1, mat=mat_unten if pts[k].z < h * 0.45 else mat_oben)
    return pts


def altkiefer(bm, ox, oy, h):
    """Altkiefer im Bestand: astfreier Stamm, Krone etwa die obere Hälfte, breit und dicht."""
    kronenansatz = h * rng.uniform(0.46, 0.54)
    pts = stamm(bm, ox, oy, h, 0.30 * h / 22, 0, 1)
    for k in range(rng.integers(14, 19)):
        z = rng.uniform(kronenansatz, h * 0.97)
        st = pts[min(8, int(z / h * 8))]
        winkel = rng.uniform(0, 2 * math.pi)
        oben = (z - kronenansatz) / (h - kronenansatz)
        laenge = rng.uniform(2.2, 4.0) * (1.1 - 0.6 * oben) * h / 22
        steig = rng.uniform(0.25, 0.65)
        start = Vector((st.x, st.y, z))
        ende = start + Vector((math.cos(winkel) * laenge, math.sin(winkel) * laenge, laenge * steig))
        zylinder(bm, start, ende, 0.09, 0.04, seg=5, mat=1)
        for t in (0.4, 0.65, 0.85, 1.0):
            p = start.lerp(ende, t) + Vector(rng.normal(0, 0.25, 3))
            nadelbueschel(p, rng.uniform(0.8, 1.4) * (0.7 + 0.5 * t), 2 + int(rng.integers(0, 3)))
    # Füllballen über die ganze Kronenhöhe, damit die Krone geschlossen wirkt
    for _ in range(22):
        a = rng.uniform(0, 2 * math.pi); d = rng.uniform(0, 2.6) * h / 22
        z = rng.uniform(kronenansatz + 1.0, h)
        nadelbueschel((ox + math.cos(a) * d, oy + math.sin(a) * d, z), rng.uniform(1.0, 1.6), 2 + int(rng.integers(0, 3)))


def jungkiefer(bm, ox, oy, h):
    """Junge Kiefer aus dem Unterstand: kegelförmig, benadelt fast bis zum Boden."""
    stamm(bm, ox, oy, h, 0.08, 0, 0)
    for _ in range(int(16 * h)):
        z = rng.uniform(0.4, h)
        r = (h - z) / h * 0.45 * h + 0.3
        a = rng.uniform(0, 2 * math.pi); d = rng.uniform(0, 1) ** 0.5 * r
        nadelbueschel((ox + math.cos(a) * d, oy + math.sin(a) * d, z), rng.uniform(0.5, 0.8), 2 + int(rng.integers(0, 3)))


# Gruppe statt Einzelbaum: eine Condor-Waldzelle ist 11 m breit, ein einzelner schlanker Baum darin wirkt licht.
# (x, y, Höhe) in m relativ zum Stammfuß der Hauptkiefer. Nach links versetzt: im Atlas-Quadranten liegt der Fuß bei x=346 px,
# rechts bleiben nur ~7,5 m (bei 22 m = 470 px), links ~16 m; Astspitzen samt Büscheln reichen ~5 m über den Stamm hinaus.
GRUPPE_ALT = [(0.0, 0.0, HOEHE), (-5.0, 2.0, HOEHE * 0.88), (1.5, -1.6, HOEHE * 0.93)]
GRUPPE_JUNG = [(-2.6, -2.2, 5.5), (1.4, 2.4, 4.2)]


def baue_kiefer():
    m_unten = material("Rinde_unten", (0.12, 0.095, 0.075))
    m_oben = material("Rinde_oben", (0.42, 0.22, 0.11))
    nadel = [material(f"Nadel{k}", c, 0.9) for k, c in enumerate([(0.045, 0.085, 0.035), (0.065, 0.11, 0.045), (0.09, 0.13, 0.05)])]
    bm = bmesh.new()
    for x, y, h in GRUPPE_ALT:
        altkiefer(bm, x, y, h)
    for x, y, h in GRUPPE_JUNG:
        jungkiefer(bm, x, y, h)
    nadelnetz([m_unten, m_oben] + nadel)
    return objekt("Kiefer", bm, [m_unten, m_oben] + nadel)


def render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = 1024
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    welt = bpy.data.worlds.new("W"); sc.world = welt; welt.use_nodes = True
    welt.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.75, 0.72, 1)
    welt.node_tree.nodes["Background"].inputs[1].default_value = 0.45
    sonne = bpy.data.objects.new("Sonne", bpy.data.lights.new("Sonne", "SUN"))
    sonne.data.energy = 3.5
    sonne.data.color = (1.0, 0.95, 0.85)
    sonne.rotation_euler = (math.radians(50), 0, math.radians(-30))
    sc.collection.objects.link(sonne)
    # Orthografische Seitenansicht: Bildbreite 1024 px = ortho_scale m; Stammfuß bei Zeile 1000, Spalte 512
    cam = bpy.data.objects.new("Kamera", bpy.data.cameras.new("Kamera"))
    cam.data.type = "ORTHO"
    px_pro_m = 940 / HOEHE
    cam.data.ortho_scale = 1024 / px_pro_m
    mitte_z = (1000 - 512) / px_pro_m  # Bildmitte liegt 488 px über dem Stammfuß
    cam.location = (0, -50, mitte_z)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.collection.objects.link(cam); sc.camera = cam
    sc.render.filepath = AUSGABE
    bpy.ops.render.render(write_still=True)


leer()
baue_kiefer()
render()
print("Kiefer gerendert:", AUSGABE)
