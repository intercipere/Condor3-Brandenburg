"""Prozedurale Wandtexturen für die EDAZ-Gebäude (keine Fotos, alles aus Rauschen und Formen erzeugt).

Alle Texturen 1024 x 1024 px, v nach unten (DirectX): Zeile 0 = oben, letzte Zeile = Boden.
- putz:    heller Putz mit Sockel, 4 Fensterachsen breit, PUTZ_H Meter hoch (ohne Fenster).
- fassade: dasselbe Bild mit Fensterreihen je Geschoss (GESCHOSS Meter), gleiche UV -> nahtloser Übergang zu putz.
- blech:   Trapezblech (senkrechte Rippen), BLECH_M x BLECH_M Meter, Betonsockel unten. Varianten (BLECH_FARBEN):
           hangar (hellgrau), stall (graubeige, Reihe Zuluftklappen), gewerbe (mittelgrau); stall mit luefter=True:
           Giebel mit Abluftventilatoren. Grobe Struktur (Tafelstöße 1 m, Wetterspuren 2-5 m, Schmutz unten), damit
           die Wand auch in den kleinen Mip-Stufen nicht als gleichmäßig helle Fläche erscheint.
- tore:    Hangartor (olivgrau, nach den Toren der Hangarzeilen A und C), 4 Torflügel nebeneinander,
           Höhe = genau ein Tor (v 0 = Torsturz, v 1 = Boden).
- silo:    verzinkter Futtersilo, SILO_M x SILO_M Meter, Ringstöße.
Helligkeit: die offiziellen Condor-Autogen-Texturen liegen bei Metall um 130, Putz 165-190 (Luminanz 0-255).

Aufruf: python fassaden.py <ordner>  -> schreibt die PNGs zur Kontrolle.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

PX = 1024
ACHSEN = 4  # Fensterachsen bzw. Torflügel je Kachelbreite
ACHSE_M = 3.0  # Sollbreite einer Fensterachse (wird je Wand so gestreckt, dass ganze Achsen passen)
PUTZ_H = 18.0  # Meter je Kachelhöhe bei Putz/Fassade
GESCHOSS = 3.0
SOCKEL_M = 0.45
FENSTER = (0.9, 2.3)  # Brüstung und Sturz über Geschossboden (m)
FENSTER_B = 1.3  # Fensterbreite (m, bei Sollachse)
BLECH_M = 16.0  # Meter je Kachel (waagerecht und senkrecht)
RIPPE_M = 0.25  # Rippenabstand Trapezblech
FLUEGEL_M = 4.0  # Sollbreite eines Torflügels
BLECH_FARBEN = {"hangar": (152, 156, 158), "stall": (156, 150, 135), "gewerbe": (138, 142, 141)}
PUTZ_FLUGPLATZ = (209, 199, 174)  # cremefarben wie die Putzbauten am Platz
SILO_M = 8.0


def _weich(r, sigma):
    """Gaußfilter mit periodischem Rand (über FFT), damit die Kachel nahtlos bleibt."""
    if sigma <= 0:
        return r
    f = [np.fft.fftfreq(n) for n in r.shape]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (f[0][:, None] ** 2 + f[1][None, :] ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(r) * g)).astype(np.float32)


def _rauschen(rng, sigma, amp, form=(PX, PX)):
    """Weiches Rauschen mit Standardabweichung ~amp, kachelbar."""
    r = _weich(rng.normal(0, 1, form).astype(np.float32), sigma)
    return r / (r.std() + 1e-9) * amp


def _streifen_senkrecht(rng, sigma_x, amp):
    """Senkrechte Schlieren (Wetterspuren): Rauschen nur entlang x, nach unten leicht verstärkt."""
    r = _weich(rng.normal(0, 1, (1, PX)).astype(np.float32), sigma_x)
    r = r / (r.std() + 1e-9) * amp
    return np.repeat(r, PX, 0) * np.linspace(0.6, 1.2, PX, dtype=np.float32)[:, None]


def _zeile(z_m, hoehe_m):
    """Bildzeile für die Höhe z_m über Boden bei einer Kachelhöhe hoehe_m."""
    return int(round((hoehe_m - z_m) / hoehe_m * PX))


def putz(mit_fenstern=False, seed=1, farbe=(201, 194, 181)):
    rng = np.random.default_rng(seed)
    img = np.empty((PX, PX, 3), np.float32)
    img[:] = farbe
    hell = _rauschen(rng, 40, 4) + _rauschen(rng, 1.2, 4) + _streifen_senkrecht(rng, 6, 2.5)
    img += hell[..., None]
    s0 = _zeile(SOCKEL_M, PUTZ_H)
    # leicht dunkler zum Boden hin (Spritzwasser), dann Sockel
    unten = _zeile(1.2, PUTZ_H)
    img[unten:s0] *= np.linspace(1.0, 0.92, s0 - unten, dtype=np.float32)[:, None, None]
    img[s0:] = np.array((142, 138, 131), np.float32) + _rauschen(rng, 1.0, 6, (PX - s0, PX))[..., None]
    img[s0:s0 + 2] *= 0.8  # Kante Sockel
    if mit_fenstern:
        _fenster(img, rng)
    return np.clip(img, 0, 255).astype(np.uint8)


def _fenster(img, rng):
    achse_px = PX // ACHSEN
    fb = int(round(FENSTER_B / ACHSE_M * achse_px))
    for g in range(int(PUTZ_H // GESCHOSS)):
        y0, y1 = _zeile(g * GESCHOSS + FENSTER[1], PUTZ_H), _zeile(g * GESCHOSS + FENSTER[0], PUTZ_H)
        if y0 < 0:
            continue
        for a in range(ACHSEN):
            x0 = a * achse_px + (achse_px - fb) // 2
            x1 = x0 + fb
            # Laibung (Schatten oben/links), Rahmen, Glas mit Himmelsspiegelung, Mittelpfosten
            img[y0 - 3:y1 + 2, x0 - 3:x1 + 3] *= 0.78
            glas = np.linspace(1.0, 0.55, y1 - y0, dtype=np.float32)[:, None, None]
            ton = np.array((112, 126, 140), np.float32) * rng.uniform(0.85, 1.1)
            img[y0:y1, x0:x1] = ton * glas + _rauschen(rng, 2, 3, (y1 - y0, fb))[..., None]
            if rng.random() < 0.3:  # Rollladen halb unten
                r = y0 + int((y1 - y0) * rng.uniform(0.25, 0.6))
                lam = 150 + 12 * (np.arange(y0, r) % 4 < 2)
                img[y0:r, x0:x1] = lam[:, None, None]
            rahmen = np.array((232, 232, 228), np.float32)
            img[y0:y0 + 4, x0:x1] = rahmen
            img[y1 - 4:y1, x0:x1] = rahmen
            img[y0:y1, x0:x0 + 4] = rahmen
            img[y0:y1, x1 - 4:x1] = rahmen
            m = (x0 + x1) // 2
            img[y0:y1, m - 2:m + 2] = rahmen
            img[y0 + 4:y0 + 7, x0 + 4:x1 - 4] *= 0.7  # Schatten unter dem Sturz
            # Fensterbank
            img[y1:y1 + 4, x0 - 6:x1 + 6] = (205, 205, 202)
            img[y1 + 4:y1 + 7, x0 - 6:x1 + 6] *= 0.75


def blech(seed=2, variante="hangar", luefter=False):
    rng = np.random.default_rng(seed)
    ppm = PX / BLECH_M
    xm = np.arange(PX) / ppm
    x = xm % RIPPE_M / RIPPE_M  # Phase 0..1 innerhalb einer Rippe
    # Profil: Obergurt, linke Flanke (beleuchtet), Untergurt, rechte Flanke (Schatten)
    profil = np.select([x < 0.22, x < 0.34, x < 0.88], [1.0, 1.06, 0.94], 0.80).astype(np.float32)
    img = np.empty((PX, PX, 3), np.float32)
    img[:] = np.array(BLECH_FARBEN[variante], np.float32)
    img *= profil[None, :, None]
    # Tafeln (1 m breit) mit deutlich unterschiedlicher Helligkeit und dunkler Stoßfuge
    tafel = (xm // (4 * RIPPE_M)).astype(int)
    faktor = rng.uniform(0.93, 1.07, tafel.max() + 1).astype(np.float32)
    img *= faktor[tafel][None, :, None]
    img[:, xm % (4 * RIPPE_M) < 0.05] *= 0.8
    # Wetterspuren: senkrechte Schlieren 2-5 m breit, nach unten stärker; Feinrauschen
    grob = _streifen_senkrecht(rng, 2.5 * ppm, 7) + _streifen_senkrecht(rng, 0.6 * ppm, 3)
    img += (grob + _rauschen(rng, 50, 3) + _rauschen(rng, 1.0, 2.5))[..., None]
    s0 = _zeile(0.5, BLECH_M)
    unten = _zeile(2.0, BLECH_M)
    img[unten:s0] *= np.linspace(1.0, 0.8, s0 - unten, dtype=np.float32)[:, None, None]  # Spritzwasser
    img[s0:] = np.array((128, 126, 120), np.float32) + _rauschen(rng, 1.0, 6, (PX - s0, PX))[..., None]
    img[s0 - 3:s0] = (85, 87, 89)  # Abschlussblech über dem Sockel
    if variante == "stall" and not luefter:
        # Reihe Zuluftklappen auf 1,9-2,3 m, 10 je Kachel (1,6 m Abstand), dunkel mit hellem Rahmen
        y0, y1 = _zeile(2.3, BLECH_M), _zeile(1.9, BLECH_M)
        b = int(0.75 * ppm)
        for k in range(10):
            x0 = int(k * PX / 10 + (PX / 10 - b) / 2)
            img[y0 - 3:y1 + 3, x0 - 3:x0 + b + 3] = (200, 200, 196)
            img[y0:y1, x0:x0 + b] = np.array((58, 60, 58), np.float32) * np.linspace(0.8, 1.2, y1 - y0, dtype=np.float32)[:, None, None]
    if luefter:
        # Abluftventilatoren am Giebel: 6 je Kachel (2,67 m Abstand), 1,4 m Kasten ab 0,7 m über Boden
        y0, y1 = _zeile(2.1, BLECH_M), _zeile(0.7, BLECH_M)
        b = y1 - y0
        yy, xx = np.mgrid[0:b, 0:b] - (b - 1) / 2
        rad = np.hypot(yy, xx) / (b / 2)
        for k in range(6):
            x0 = int(k * PX / 6 + (PX / 6 - b) / 2)
            box = np.array((150, 152, 150), np.float32) * np.ones((b, b, 1), np.float32)
            box[rad < 0.92] = (42, 44, 44)  # Öffnung
            box[(rad < 0.92) & ((np.abs(yy) < 1.5) | (np.abs(xx) < 1.5))] = (95, 97, 97)  # Schutzgitter
            box[rad < 0.18] = (80, 82, 82)  # Nabe
            img[y0 - 4:y1 + 4, x0 - 4:x0 + b + 4] = (70, 72, 72)
            img[y0:y1, x0:x0 + b] = box
    return np.clip(img, 0, 255).astype(np.uint8)


def silo(seed=4):
    """Verzinkter Silo: 6 senkrechte Bahnen je Kachel (1,33 m), Ringstöße alle 0,8 m, Laufspuren; u-kachelbar."""
    rng = np.random.default_rng(seed)
    ppm = PX / SILO_M
    img = np.empty((PX, PX, 3), np.float32)
    img[:] = np.array((168, 172, 170), np.float32)
    bahn = (np.arange(PX) * 6 // PX).astype(int)
    img *= rng.uniform(0.93, 1.07, bahn.max() + 1).astype(np.float32)[bahn][None, :, None]
    ring = (np.arange(PX) / ppm) % 0.8 < 0.04
    img[ring] *= 0.75
    img += (_streifen_senkrecht(rng, 1.5 * ppm, 6) + _rauschen(rng, 1.0, 3))[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def tore(seed=3):
    """Ein Torflügel je PX/ACHSEN Pixel; senkrecht genau eine Torhöhe (Tor ist 4-7 m hoch, Maße relativ)."""
    rng = np.random.default_rng(seed)
    img = np.empty((PX, PX, 3), np.float32)
    img[:] = np.array((132, 140, 108), np.float32)  # Olivgrau wie die Falttore der Hangarzeilen
    yy = np.arange(PX)[:, None]
    # waagerechte Paneele (Sandwich) mit Fugen, feine Längssicken
    paneel = PX // 10
    img[(yy % paneel < 3)[:, 0]] *= 0.72
    img *= (1 + 0.03 * np.sin(np.arange(PX) / PX * 2 * np.pi * 80))[:, None, None].astype(np.float32)
    img += (_rauschen(rng, 30, 3) + _rauschen(rng, 1.0, 2.5) + _streifen_senkrecht(rng, 4, 2))[..., None]
    b = PX // ACHSEN
    for a in range(ACHSEN):
        x0 = a * b
        img[:, x0:x0 + 10] = (62, 66, 64)  # Rahmen/Stoß zwischen den Flügeln
        img[:, x0 + 6:x0 + 9] *= 0.8
        img[:, x0 + b - 3:x0 + b] *= 0.85
        img[:, x0:x0 + b] *= 1.08 if a % 2 else 0.94  # Flügel abwechselnd heller/dunkler, bleibt in kleinen Mips sichtbar
        # Fensterband im oberen Drittel: zwei Scheiben je Flügel
        y0, y1 = int(PX * 0.22), int(PX * 0.30)
        for k in range(2):
            f0 = x0 + 20 + k * (b - 20) // 2
            f1 = f0 + (b - 20) // 2 - 20
            img[y0 - 2:y1 + 2, f0 - 2:f1 + 2] = (70, 74, 78)
            img[y0:y1, f0:f1] = np.array((96, 112, 128), np.float32) * np.linspace(1.1, 0.7, y1 - y0)[:, None, None]
        # Laufrolle unten / Griffleiste
        img[int(PX * 0.55):int(PX * 0.62), x0 + b - 22:x0 + b - 14] = (70, 72, 74)
    img[:14] = (78, 80, 82)  # Laufschiene / Sturz oben
    img[14:22] *= 0.7
    img[-10:] = (45, 45, 45)  # Bodendichtung
    return np.clip(img, 0, 255).astype(np.uint8)


def alle(putzfarbe=(201, 194, 181)):
    return dict(putz=putz(False, farbe=putzfarbe), fassade=putz(True, farbe=putzfarbe), blech=blech(),
                blech_stall=blech(variante="stall"), blech_gewerbe=blech(variante="gewerbe"),
                blech_luefter=blech(variante="stall", luefter=True), tore=tore(), silo=silo())


if __name__ == "__main__":
    ziel = sys.argv[1] if len(sys.argv) > 1 else "."
    for name, bild in alle().items():
        Image.fromarray(bild).save(os.path.join(ziel, f"textur_{name}.png"))
        print(name, bild.shape, bild.mean((0, 1)).round())
