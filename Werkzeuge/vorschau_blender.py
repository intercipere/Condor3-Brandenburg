"""Blender-Vorschau der EDAZ-Szenerie. Liest Daten/Vorschau (erzeugt von vorschau_daten.py).

Interaktiv:  blender --python vorschau_blender.py
Bilder:      blender -b --python vorschau_blender.py -- --render <ordner>
Weltkoordinaten: x = Ost, y = Nord (m ab Flugplatzpunkt), z = Höhe über Flugplatzhöhe.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(os.path.dirname(HIER), "Daten", "Vorschau")


def material(name, bild=None, farbe=(0.8, 0.8, 0.8)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    if bild:
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(DATEN, bild))
        tex.image.alpha_mode = "CHANNEL_PACKED"  # Alpha ist bei Condor Grashöhe, keine Transparenz
        m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*farbe, 1)
    return m


def netz(name, p, tris, uv=None, mat=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(p)); me.vertices.foreach_set("co", np.asarray(p, np.float32).ravel())
    me.loops.add(tris.size); me.loops.foreach_set("vertex_index", tris.astype(np.int32).ravel())
    me.polygons.add(len(tris))
    me.polygons.foreach_set("loop_start", np.arange(0, tris.size, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(tris), 3, np.int32))
    if uv is not None:
        lay = me.uv_layers.new(name="UV")
        u = np.asarray(uv, np.float32)[tris.ravel()].copy()
        u[:, 1] = 1.0 - u[:, 1]  # Condor/DirectX: v nach unten, Blender: v nach oben
        lay.data.foreach_set("uv", u.ravel())
    me.update(); me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def baum_vorlage(name, nadel):
    """Einfacher Platzhalterbaum (Kegel bzw. Kugel auf Stamm), ohne bpy.ops (läuft auch beim Programmstart)."""
    bm = bmesh.new()
    if nadel:
        krone = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=2.5, radius2=0, depth=12)["verts"]
        bmesh.ops.translate(bm, vec=(0, 0, 12), verts=krone)
    else:
        krone = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=4.5)["verts"]
        bmesh.ops.translate(bm, vec=(0, 0, 13), verts=krone)
    stamm = bmesh.ops.create_cone(bm, cap_ends=True, segments=5, radius1=0.3, radius2=0.3, depth=8)["verts"]
    bmesh.ops.translate(bm, vec=(0, 0, 4), verts=stamm)
    stamm = set(stamm)
    for f in bm.faces:
        f.material_index = 1 if all(v in stamm for v in f.verts) else 0
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(material(name + "_Krone", farbe=(0.06, 0.16, 0.06) if nadel else (0.18, 0.32, 0.08)))
    me.materials.append(material(name + "_Stamm", farbe=(0.25, 0.18, 0.12)))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def leere_szene():
    for sammlung in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.images):
        for x in list(sammlung):
            sammlung.remove(x)


def baue_szene():
    leere_szene()
    s = json.load(open(os.path.join(DATEN, "szene.json")))
    # Gelände
    H = np.load(os.path.join(DATEN, "gelaende.npy")); ny, nx = H.shape
    gl = s["gelaende"]
    jj, ii = np.mgrid[0:ny, 0:nx]
    p = np.c_[gl["e0"] + ii.ravel() * gl["zelle"], gl["n0"] + jj.ravel() * gl["zelle"], H.ravel()]
    q = (jj[:-1, :-1] * nx + ii[:-1, :-1]).ravel()
    gerade = ((ii[:-1, :-1] + jj[:-1, :-1]) % 2 == 0).ravel()
    a, b, c, d = q, q + 1, q + nx + 1, q + nx  # (i,j) (i+1,j) (i+1,j+1) (i,j+1)
    t1 = np.where(gerade[:, None], np.c_[a, b, c], np.c_[a, b, d])
    t2 = np.where(gerade[:, None], np.c_[a, c, d], np.c_[b, c, d])
    tris = np.vstack([t1, t2])
    uv = np.c_[ii.ravel() / (nx - 1), 1.0 - jj.ravel() / (ny - 1)]  # Textur: Nord oben -> v=0 oben (DirectX)
    netz("Gelaende", p, tris, uv, material("Gelaende", "gelaende.png"))
    # Flugplatz-Objekte
    for o in s["objekte"]:
        z = np.load(os.path.join(DATEN, o["name"] + ".npz"))
        netz(o["name"], z["p"], z["tris"], z["uv"], material(o["name"], o["textur"], tuple(o["farbe"])))
    # Wald als Instanzen auf Punkten (Platzhalterbäume, zufällig um die Zellmitte versetzt)
    B = np.load(os.path.join(DATEN, "baeume.npy"))
    rng = np.random.default_rng(1)
    for wert, nadel in ((1, True), (2, False)):
        P = B[B[:, 3] == wert, :3].copy()
        P[:, :2] += rng.uniform(-4, 4, (len(P), 2))
        punkte = bpy.data.meshes.new(f"Wald{wert}")
        punkte.vertices.add(len(P)); punkte.vertices.foreach_set("co", P.ravel())
        ob = bpy.data.objects.new(f"Wald_{'Nadel' if nadel else 'Laub'}", punkte)
        bpy.context.scene.collection.objects.link(ob)
        vorlage = baum_vorlage(f"Baum_{'Nadel' if nadel else 'Laub'}", nadel)
        vorlage.parent = ob
        ob.instance_type = "VERTS"
    # Licht, Himmel, Kameras
    welt = bpy.data.worlds.new("Himmel"); bpy.context.scene.world = welt
    welt.use_nodes = True; welt.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.7, 0.95, 1)
    welt.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sonne = bpy.data.objects.new("Sonne", bpy.data.lights.new("Sonne", "SUN"))
    sonne.data.energy = 4; sonne.rotation_euler = (math.radians(40), 0, math.radians(200))
    bpy.context.scene.collection.objects.link(sonne)
    # Nahkameras auf den Schwerpunkt der Gebäude ausrichten
    dach = np.load(os.path.join(DATEN, "SchoenhagenO_Daecher.npz"))["p"]
    gx, gy = np.median(dach[:, 0]), np.median(dach[:, 1])
    kameras = {
        # name: (Position, Blickziel)
        "anflug_25": ((1600, 500, 180), (-200, -60, 0)),
        "hallen_nah": ((gx + 250, gy - 250, 45), (gx, gy, 5)),
        "vorfeld": ((gx + 120, gy - 60, 8), (gx - 150, gy + 150, 6)),
        "uebersicht": ((1500, -2500, 900), (-300, 300, 0)),
        "boden_piste": ((300, 60, 2), (-400, -90, 1)),
    }
    for name, (pos, ziel) in kameras.items():
        cam = bpy.data.objects.new("Kamera_" + name, bpy.data.cameras.new(name))
        cam.data.lens = 28; cam.data.clip_end = 30000
        cam.location = pos
        richtung = np.subtract(ziel, pos)
        cam.rotation_euler = (math.atan2(math.hypot(richtung[0], richtung[1]), -richtung[2]), 0,
                              math.atan2(richtung[1], richtung[0]) - math.pi / 2)
        bpy.context.scene.collection.objects.link(cam)
    sc = bpy.context.scene
    sc.camera = bpy.data.objects["Kamera_anflug_25"]
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    return kameras


def ansicht_einrichten():
    """Im offenen Fenster: Sichtweite hoch, Materialansicht, Blick durch die Anflugkamera."""
    for fenster in bpy.context.window_manager.windows:
        for area in fenster.screen.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.clip_end = 30000
                        sp.shading.type = "MATERIAL"
                        sp.region_3d.view_perspective = "CAMERA"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--render" in argv:
        kameras = baue_szene()
        ziel = argv[argv.index("--render") + 1]
        os.makedirs(ziel, exist_ok=True)
        nur = argv[argv.index("--nur") + 1].split(",") if "--nur" in argv else list(kameras)
        for name in nur:
            bpy.context.scene.camera = bpy.data.objects["Kamera_" + name]
            bpy.context.scene.render.filepath = os.path.join(ziel, name + ".png")
            bpy.ops.render.render(write_still=True)
            print("gerendert:", name)
    else:
        # Fenster-Modus: erst bauen, wenn die Oberfläche fertig geladen ist
        def spaeter():
            baue_szene()
            ansicht_einrichten()
            return None
        bpy.app.timers.register(spaeter, first_interval=1.0)


main()
