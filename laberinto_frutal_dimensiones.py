# -*- coding: utf-8 -*-
"""
LABERINTO FRUTAL: DIMENSIONES  (version 2.0)
============================================
Archivo unico (no necesita otros modulos). Solo requiere:  pip install pygame

Controles (se pueden cambiar en CONFIGURACION > CONTROLES):
    Flechas o WASD ... mover
    ESPACIO ......... disparar (mantener = ataque cargado)
    B / SHIFT ....... bomba (cambia con cada mundo)
    C ............... ataque cargado (mantener y soltar)
    E ............... ataque especial (estallido)
    R ............... rayo        Q ... hielo        X ... rafaga
    M ............... musica ON/OFF
    P ............... pausa
    ESC ............. pausa / volver  (el menu de pausa permite salir)

Novedades 2.0:
    - Frutas con habilidades + frutas especiales (legendaria, cristal, dorada)
    - EL CAZADOR: un enemigo que aprende tus caminos
    - Jefes con 3 fases, eventos aleatorios, pasadizos secretos
    - Frutacoins, tienda completa (skins, mejoras, mascotas, efectos)
    - Modo Furia, combos hasta x20, 8 tipos de ataque
    - 10 mundos con mecanica unica + dimension oculta tras el nivel 50
    - Historia, misiones, logros, records, configuracion y guardado JSON

Opcional:  python laberinto_frutal_dimensiones.py --nivel 12
"""

import colorsys
import json
import math
import os
import random
import sys
from array import array
from collections import deque
from functools import lru_cache

import pygame

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

# ======================================================
# Guardado: ruta y configuracion (se lee antes de abrir la ventana)
# ======================================================
RUTA_PROGRESO = os.environ.get("LABERINTO_PROGRESO") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "progreso_laberinto.json")


def _leer_guardado():
    try:
        with open(RUTA_PROGRESO, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


DATOS_GUARDADO = _leer_guardado()

CONTROLES_DEF = {
    "arriba": [pygame.K_UP, pygame.K_w], "abajo": [pygame.K_DOWN, pygame.K_s],
    "izquierda": [pygame.K_LEFT, pygame.K_a], "derecha": [pygame.K_RIGHT, pygame.K_d],
    "disparo": [pygame.K_SPACE], "bomba": [pygame.K_b, pygame.K_LSHIFT, pygame.K_z],
    "cargado": [pygame.K_c], "especial": [pygame.K_e], "rayo": [pygame.K_r], "hielo": [pygame.K_q], "rafaga": [pygame.K_x],
    "musica": [pygame.K_m], "pausa": [pygame.K_p],
}
NOMBRES_CONTROL = {
    "arriba": "Mover arriba", "abajo": "Mover abajo", "izquierda": "Mover izquierda",
    "derecha": "Mover derecha", "disparo": "Disparo / ataque", "bomba": "Bomba",
    "cargado": "Ataque cargado (mantener)", "especial": "Ataque especial", "rayo": "Rayo", "hielo": "Hielo", "rafaga": "Ráfaga",
    "musica": "Música ON/OFF", "pausa": "Pausa",
}
CONFIG_DEF = dict(vol_musica=0.7, vol_efectos=0.8, musica_on=True, efectos_on=True,
                  pantalla_completa=False, resolucion=0, particulas=True, efectos=True)
CONFIG = dict(CONFIG_DEF)
CONTROLES = {k: list(v) for k, v in CONTROLES_DEF.items()}


def _cargar_config():
    c = DATOS_GUARDADO.get("config", {})
    if not isinstance(c, dict):
        return
    for k, v in CONFIG_DEF.items():
        if k in c and type(c[k]) == type(v):
            CONFIG[k] = c[k]
        elif k in c and isinstance(v, float) and isinstance(c[k], int):
            CONFIG[k] = float(c[k])
    for k in ("vol_musica", "vol_efectos"):
        CONFIG[k] = max(0.0, min(1.0, CONFIG[k]))
    CONFIG["resolucion"] = max(0, min(4, CONFIG["resolucion"]))
    ct = c.get("controles", {})
    if isinstance(ct, dict):
        for k, v in ct.items():
            if k in CONTROLES and isinstance(v, list) and v and all(isinstance(x, int) for x in v):
                CONTROLES[k] = v


_cargar_config()


def tecla(teclas, accion):
    """True si alguna de las teclas asignadas a la accion esta pulsada."""
    for k in CONTROLES[accion]:
        try:
            if teclas[k]:
                return True
        except (IndexError, KeyError):
            pass
    return False


def es_tecla(key, accion):
    return key in CONTROLES[accion]

# ======================================================
# Configuracion general
# ======================================================
TAM = 40  # tamano de cada casilla

MAPA_BASE = [
    "#########################",
    "#.........#.............#",
    "###.#####.#.###########.#",
    "#.#.#...#.....#.......#.#",
    "#.#.#.#.#####.###.#####.#",
    "#.#...#...#...#...#...#.#",
    "#.#######.#.###.###.#.#.#",
    "#...#...#.......#...#.#.#",
    "#.#.###.#.#######.###.#.#",
    "#.#.....#.......#.#.....#",
    "#.#####.#######.#.#######",
    "#...#...#.....#.#.......#",
    "###.#.###.###.#.#.#####.#",
    "#...#.#.....#.#.#.....#.#",
    "#.#####.#####.#.#######.#",
    "#.....#.#.....#.........#",
    "#.###.#.#.#############.#",
    "#...#...#...............#",
    "#########################",
]

FILAS = len(MAPA_BASE)
COLS = len(MAPA_BASE[0])
MAPA = list(MAPA_BASE)  # mapa del nivel actual (cambia en cada nivel)
RADIO_BOMBA = 6  # alcance de la bomba (en casillas de camino)
ANCHO = COLS * TAM
ALTO_MAPA = FILAS * TAM
ALTO_HUD = 92
ALTO = ALTO_MAPA + ALTO_HUD
FPS = 60

pygame.display.set_caption("Laberinto Frutal: Dimensiones")
pantalla = pygame.Surface((ANCHO, ALTO))   # todo el juego se dibuja aqui y luego se escala
RESOLUCIONES = [("Auto", 0), ("70%", 0.7), ("85%", 0.85), ("100%", 1.0), ("125%", 1.25)]
_ventana = None


def aplicar_ventana():
    """Crea / reconfigura la ventana segun CONFIG (pantalla completa y resolucion)."""
    global _ventana
    try:
        escritorio = pygame.display.get_desktop_sizes()[0]
    except Exception:
        escritorio = (1280, 720)
    if CONFIG["pantalla_completa"]:
        _ventana = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        return
    k = RESOLUCIONES[CONFIG["resolucion"]][1]
    if k == 0:
        k = min(1.0, (escritorio[1] - 90) / ALTO, (escritorio[0] - 20) / ANCHO)
    k = max(0.4, k)
    _ventana = pygame.display.set_mode((int(ANCHO * k), int(ALTO * k)), pygame.RESIZABLE)


def presentar():
    """Muestra la pantalla virtual escalada (con barras negras si hace falta)."""
    if _ventana is None:
        return
    surf = pygame.display.get_surface()
    w, h = surf.get_size()
    k = min(w / ANCHO, h / ALTO)
    tw, th = max(1, int(ANCHO * k)), max(1, int(ALTO * k))
    if (tw, th) == (ANCHO, ALTO) and (w, h) == (ANCHO, ALTO):
        surf.blit(pantalla, (0, 0))
    else:
        if (tw, th) != (w, h):
            surf.fill((0, 0, 0))
        img = pygame.transform.smoothscale(pantalla, (tw, th)) if k < 1.0 else pygame.transform.scale(pantalla, (tw, th))
        surf.blit(img, ((w - tw) // 2, (h - th) // 2))
    pygame.display.flip()


aplicar_ventana()
pantalla = pantalla.convert()   # mismo formato que la ventana: se dibuja mas rapido
reloj = pygame.time.Clock()
lienzo = pygame.Surface((ANCHO, ALTO_MAPA))  # aqui se dibuja el laberinto

CELDA_INICIAL = (1, 1)
ANCHO_PJ = 20
ALTO_PJ = 20
MARGEN = (TAM - ANCHO_PJ) // 2
VEL_JUGADOR = 4
COMBO_FRAMES = 150  # tiempo para encadenar frutas
MAX_NIVELES = 50
NIVELES_POR_MUNDO = 5
NUM_MUNDOS = 10
MUNDO_DIM = 10            # indice del mundo secreto (El Corazon del Laberinto)
NIVEL_DIM_INI = MAX_NIVELES + 1
MAX_NIVEL_TOTAL = MAX_NIVELES + 5   # la dimension oculta tiene 5 niveles
VIDAS_MAX = 5
VIDAS_INICIALES = 5  # corazones con los que empiezas cada partida


def mundo_de(nivel):
    if nivel > MAX_NIVELES:
        return MUNDO_DIM
    return min((nivel - 1) // NIVELES_POR_MUNDO, NUM_MUNDOS - 1)


def es_nivel_jefe(nivel):
    return nivel % NIVELES_POR_MUNDO == 0


DIRS = {"arriba": (0, -1), "abajo": (0, 1), "izquierda": (-1, 0), "derecha": (1, 0)}


@lru_cache(maxsize=None)
def fuente(tam, negrita=True):
    return pygame.font.SysFont("arial,helvetica,dejavusans", tam, bold=negrita)


F_TITULO = fuente(84)
F_GRANDE = fuente(46)
F_MED = fuente(26)
F_HUD = fuente(28)
F_PEQ = fuente(17)

# Temas de color (uno por mundo)
TEMAS = [
    dict(nombre="Cripta", fondo=(14, 14, 24), piso=(38, 40, 58), piso2=(43, 45, 65),
         pared=(92, 96, 128), luz=(130, 136, 172), sombra=(50, 52, 78), acento=(120, 140, 255)),
    dict(nombre="Bosque", fondo=(10, 22, 14), piso=(30, 50, 40), piso2=(35, 57, 46),
         pared=(66, 108, 68), luz=(102, 152, 96), sombra=(36, 62, 40), acento=(110, 220, 120)),
    dict(nombre="Desierto", fondo=(40, 28, 16), piso=(122, 100, 72), piso2=(130, 107, 78),
         pared=(176, 130, 82), luz=(216, 170, 110), sombra=(112, 78, 48), acento=(255, 200, 90)),
    dict(nombre="Volcan", fondo=(24, 8, 8), piso=(52, 32, 34), piso2=(60, 36, 38),
         pared=(122, 60, 50), luz=(170, 94, 72), sombra=(70, 32, 30), acento=(255, 110, 70)),
    dict(nombre="Glaciar", fondo=(8, 18, 30), piso=(40, 68, 92), piso2=(46, 76, 102),
         pared=(140, 192, 220), luz=(220, 244, 255), sombra=(84, 124, 158), acento=(150, 228, 255)),
    dict(nombre="Neon", fondo=(10, 4, 20), piso=(26, 16, 44), piso2=(32, 20, 52),
         pared=(74, 42, 124), luz=(255, 90, 205), sombra=(36, 20, 72), acento=(255, 90, 210)),
    dict(nombre="Pantano", fondo=(10, 20, 14), piso=(34, 56, 38), piso2=(40, 63, 44),
         pared=(58, 96, 60), luz=(120, 168, 100), sombra=(28, 48, 30), acento=(150, 230, 90)),
    dict(nombre="Cueva", fondo=(10, 8, 16), piso=(38, 34, 50), piso2=(44, 40, 58),
         pared=(84, 72, 110), luz=(160, 140, 210), sombra=(34, 28, 48), acento=(190, 150, 255)),
    dict(nombre="Cielo", fondo=(14, 22, 42), piso=(56, 88, 128), piso2=(64, 98, 140),
         pared=(140, 178, 220), luz=(220, 236, 255), sombra=(70, 100, 140), acento=(255, 230, 120)),
    dict(nombre="Abismo", fondo=(4, 4, 12), piso=(24, 18, 44), piso2=(30, 22, 52),
         pared=(70, 40, 110), luz=(140, 90, 210), sombra=(24, 14, 44), acento=(120, 255, 200)),
]


def dificultad(n):
    """Parametros del nivel n (1..MAX_NIVELES). Todo sube (o se acorta) gradualmente."""
    k = min(1.12, (n - 1) / (MAX_NIVELES - 1))  # 0.0 en el nivel 1, 1.0 en el nivel 50
    return dict(
        cazador=0 if n < 2 else min(5, 1 + (n - 2) // 10),     # inteligencia de El Cazador (0 = no aparece)
        eventos=int(2400 - 1300 * k),                          # frames entre eventos aleatorios
        trampas=min(2 + n // 5, 14),                           # trampas del mundo
        tiempo_par=int(170 - 85 * k),                          # segundos para el bonus de rapidez
        tanques=0 if n < 8 else min(4, 1 + (n - 8) // 10),
        tiradores=0 if n < 15 else min(4, 1 + (n - 15) // 9),
        fantasmas=0 if n < 22 else min(4, 1 + (n - 22) // 8),
        enemigos=3 + (n - 1) * 6 // (MAX_NIVELES - 1),  # 3 -> 9 enemigos
        vel=2.3 + 1.2 * k,                               # 2.3 -> 3.5 (el jugador va a 4)
        frutas=min(8 + (2 * n) // 3, 28),                # 8 -> 28 frutas
        respawn=int(300 - 180 * k),                      # enemigos eliminados vuelven antes
        factor_poder=1.0 - 0.4 * k,                      # poderes duran hasta 40% menos
        poderes_ini=max(2, 5 - (n - 1) // 8),            # 5 -> 2 poderes al empezar
        sig_poder=int(720 + 500 * k),                    # los poderes nuevos tardan mas
        invulnerable=int(150 - 60 * k),                  # menos tiempo protegido tras un golpe
        aberturas=min(14 + 2 * n, 34),                   # atajos en el laberinto
        plazas=min(1 + n // 4, 3),
    )


# ======================================================
# Utilidades de mapa
# ======================================================
def es_pared(px, py):
    """True si el punto (px, py) en pixeles cae sobre una pared."""
    col = int(px // TAM)
    fila = int(py // TAM)
    if fila < 0 or fila >= FILAS or col < 0 or col >= COLS:
        return True
    return MAPA[fila][col] == "#"


def hay_colision(x, y, ancho, alto):
    esquinas = ((x, y), (x + ancho - 1, y), (x, y + alto - 1), (x + ancho - 1, y + alto - 1))
    return any(es_pared(ex, ey) for ex, ey in esquinas)


def mover(x, y, dx, dy):
    """Mueve por ejes separados para poder deslizar por las paredes."""
    if not hay_colision(x + dx, y, ANCHO_PJ, ALTO_PJ):
        x += dx
    if not hay_colision(x, y + dy, ANCHO_PJ, ALTO_PJ):
        y += dy
    return x, y


def distancias(origen, mapa=None):
    """BFS: distancia (en casillas) desde 'origen' a cada casilla alcanzable."""
    m = MAPA if mapa is None else mapa
    d = {origen: 0}
    cola = deque([origen])
    while cola:
        c = cola.popleft()
        for dc, df in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dc, c[1] + df)
            if 0 <= n[0] < COLS and 0 <= n[1] < FILAS and m[n[1]][n[0]] != "#" and n not in d:
                d[n] = d[c] + 1
                cola.append(n)
    return d


DIST_INICIO = distancias(CELDA_INICIAL)

# ------------------------------------------------------
# Secretos: paredes falsas, pasadizos y habitaciones ocultas
# ------------------------------------------------------
SECRETAS = {}          # celda de la pared falsa -> dict(tipo, sala, tell)
SALAS_SECRETAS = []    # habitaciones ocultas del nivel
PROTEGIDAS = set()     # casillas que las paredes cambiantes nunca tocan


def _generar_laberinto(rnd, reservados=()):
    """Laberinto perfecto (backtracking) sobre una cuadricula de casillas impares.
    'reservados' son celdas del laberinto que se dejan como roca maciza (habitaciones secretas)."""
    g = [["#"] * COLS for _ in range(FILAS)]
    cw, ch = (COLS - 1) // 2, (FILAS - 1) // 2
    vis = set(reservados) | {(0, 0)}
    pila = [(0, 0)]
    g[1][1] = "."
    while pila:
        cx, cy = pila[-1]
        vec = [(cx + dx, cy + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
               if 0 <= cx + dx < cw and 0 <= cy + dy < ch and (cx + dx, cy + dy) not in vis]
        if vec:
            nx, ny = rnd.choice(vec)
            g[2 * ny + 1][2 * nx + 1] = "."
            g[cy + ny + 1][cx + nx + 1] = "."
            vis.add((nx, ny))
            pila.append((nx, ny))
        else:
            pila.pop()
    return g, len(vis) == cw * ch


def _abrir_muros(g, cantidad, rnd, bloqueadas=()):
    """Derriba paredes que separan dos pasillos: crea ciclos (mas caminos para huir)."""
    cand = []
    for y in range(1, FILAS - 1):
        for x in range(1, COLS - 1):
            if g[y][x] == "#" and (x, y) not in bloqueadas and (
                    (g[y][x - 1] == "." and g[y][x + 1] == ".") or
                    (g[y - 1][x] == "." and g[y + 1][x] == ".")):
                cand.append((x, y))
    rnd.shuffle(cand)
    for x, y in cand[:cantidad]:
        g[y][x] = "."


def _plazas(g, cantidad, rnd, bloqueadas=()):
    """Abre plazas de 3x3 donde se cruzan varios caminos."""
    hechas = 0
    for _ in range(cantidad * 4):
        if hechas >= cantidad:
            break
        x = rnd.randrange(4, COLS - 4, 2)
        y = rnd.randrange(4, FILAS - 4, 2)
        if any((x + dx, y + dy) in bloqueadas for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                g[y + dy][x + dx] = "."
        hechas += 1


def _salas(g, cantidad, rnd, bloqueadas=(), grandes=False):
    """Salas rectangulares abiertas (3x3 hasta 7x5): zonas amplias para combatir."""
    hechas = 0
    for _ in range(cantidad * 8):
        if hechas >= cantidad:
            break
        w = rnd.choice((5, 7, 7)) if grandes else rnd.choice((3, 5))
        h = rnd.choice((3, 5))
        x = rnd.randrange(1, COLS - w, 2)
        y = rnd.randrange(1, FILAS - h, 2)
        if any((xx, yy) in bloqueadas for xx in range(x - 1, x + w + 1) for yy in range(y - 1, y + h + 1)):
            continue
        for xx in range(x, x + w):
            for yy in range(y, y + h):
                g[yy][xx] = "."
        hechas += 1


def _elegir_bloques(cantidad, rnd, cw, ch):
    """Elige bloques 2x2 de celdas para esconder habitaciones (sin tocar el inicio ni pegados)."""
    bloques = []
    for _ in range(cantidad * 25):
        if len(bloques) >= cantidad:
            break
        a = rnd.randrange(0, cw - 1)
        b = rnd.randrange(0, ch - 1)
        if a + b < 4:
            continue
        if any(abs(a - a2) < 3 and abs(b - b2) < 3 for a2, b2 in bloques):
            continue
        bloques.append((a, b))
    return bloques


def _puerta_sala(a, b, cw, ch, reserv, rnd):
    """Pared falsa que comunica la habitacion con un pasillo: (puerta, tile_dentro)."""
    ops = []
    for dy in (0, 1):
        y = 2 * (b + dy) + 1
        if a + 2 < cw and (a + 2, b + dy) not in reserv:
            ops.append(((2 * a + 4, y), (2 * a + 3, y)))
        if a - 1 >= 0 and (a - 1, b + dy) not in reserv:
            ops.append(((2 * a, y), (2 * a + 1, y)))
    for dx in (0, 1):
        x = 2 * (a + dx) + 1
        if b + 2 < ch and (a + dx, b + 2) not in reserv:
            ops.append(((x, 2 * b + 4), (x, 2 * b + 3)))
        if b - 1 >= 0 and (a + dx, b - 1) not in reserv:
            ops.append(((x, 2 * b), (x, 2 * b + 1)))
    return rnd.choice(ops) if ops else None


def _intentar_nivel(nivel, rnd, con_secretos):
    cw, ch = (COLS - 1) // 2, (FILAS - 1) // 2
    jefe = es_nivel_jefe(nivel)
    dim = nivel > MAX_NIVELES
    dif = dificultad(nivel)
    estilo = "clasico"
    bloques = []
    if nivel == 1:
        g = [list(f) for f in MAPA_BASE]
        _abrir_muros(g, 14, rnd)
    else:
        if con_secretos and (not jefe or dim):
            cant = 1 if rnd.random() < 0.8 else 0
            if nivel >= 10 and rnd.random() < 0.5:
                cant = 2
            if dim:
                cant = 2
            bloques = _elegir_bloques(cant, rnd, cw, ch)
        reserv = {(a + i, b + j) for a, b in bloques for i in (0, 1) for j in (0, 1)}
        g, ok = _generar_laberinto(rnd, reserv)
        if not ok:
            return None
        bloq = set()
        for a, b in bloques:
            for x in range(2 * a, 2 * a + 5):
                for y in range(2 * b, 2 * b + 5):
                    bloq.add((x, y))
        estilo = rnd.choice(("clasico", "abierto", "salas", "denso", "clasico", "salas"))
        aberturas, plazas = dif["aberturas"], dif["plazas"]
        if jefe:
            estilo = "arena"
            aberturas, plazas = aberturas + 8, 4
        elif estilo == "abierto":
            aberturas, plazas = int(aberturas * 1.7), plazas + 1
        elif estilo == "denso":
            aberturas, plazas = max(6, aberturas // 3), 0
        _abrir_muros(g, aberturas, rnd, bloq)
        _plazas(g, plazas, rnd, bloq)
        if estilo == "salas" or dim:
            _salas(g, 3 if dim else rnd.choice((2, 3)), rnd, bloq)
        if jefe:
            _salas(g, 2, rnd, bloq, grandes=True)
    mapa = ["".join(f) for f in g]
    # --- habitaciones secretas ---
    SECRETAS.clear()
    SALAS_SECRETAS.clear()
    PROTEGIDAS.clear()
    for a, b in bloques:
        pu = _puerta_sala(a, b, cw, ch, {(a + i, b + j) for i in (0, 1) for j in (0, 1)}, rnd)
        if pu is None:
            return None
        puerta, dentro = pu
        tiles = [(x, y) for x in range(2 * a + 1, 2 * a + 4) for y in range(2 * b + 1, 2 * b + 4)]
        for x, y in tiles:
            g[y][x] = "."
        w = rnd.random()
        k = min(1.0, nivel / 40)
        if w < 0.62 - 0.35 * k:
            tipo, tell = "empuje", 1
        elif w < 0.88 - 0.2 * k:
            tipo, tell = "disparo", rnd.choice((2, 0))
        else:
            tipo, tell = "bomba", 0
        idx = len(SALAS_SECRETAS)
        SALAS_SECRETAS.append(dict(id=idx, celdas=tiles, puerta=puerta, dentro=dentro,
                                   centro=(2 * a + 2, 2 * b + 2), tipo=tipo, abierta=False, contenido=None))
        SECRETAS[puerta] = dict(tipo=tipo, sala=idx, tell=tell)
        for x in range(2 * a, 2 * a + 5):
            for y in range(2 * b, 2 * b + 5):
                PROTEGIDAS.add((x, y))
    mapa = ["".join(f) for f in g]
    # --- pasadizo secreto: un atajo tapado con una pared falsa ---
    if (nivel == 1 or (nivel >= 3 and rnd.random() < 0.55)) and not jefe:
        dist = distancias(CELDA_INICIAL, mapa)
        cand = []
        for y in range(1, FILAS - 1):
            for x in range(1, COLS - 1):
                if mapa[y][x] != "#" or (x, y) in PROTEGIDAS:
                    continue
                for (p, q) in (((x - 1, y), (x + 1, y)), ((x, y - 1), (x, y + 1))):
                    if p in dist and q in dist and abs(dist[p] - dist[q]) >= 12:
                        cand.append((x, y))
                        break
        if cand:
            c = rnd.choice(cand)
            SECRETAS[c] = dict(tipo="empuje", sala=None, tell=1)
            PROTEGIDAS.add(c)
    # comprobacion final: todo el mapa normal debe ser alcanzable desde el inicio
    dist = distancias(CELDA_INICIAL, mapa)
    abiertas = sum(r.count(".") for r in mapa)
    ocultas = sum(len(sl["celdas"]) for sl in SALAS_SECRETAS)
    if len(dist) != abiertas - ocultas:
        return None
    return mapa, estilo


ESTILO_ACTUAL = "clasico"


def construir_mapa(nivel, semilla):
    """Devuelve el mapa (lista de strings) del nivel y prepara los secretos (SECRETAS)."""
    global ESTILO_ACTUAL
    rnd = random.Random(semilla * 31 + nivel)
    for intento in range(8):
        res = _intentar_nivel(nivel, rnd, con_secretos=intento < 6)
        if res:
            ESTILO_ACTUAL = res[1]
            return res[0]
    SECRETAS.clear()
    SALAS_SECRETAS.clear()
    PROTEGIDAS.clear()
    g, _ = _generar_laberinto(rnd)
    ESTILO_ACTUAL = "clasico"
    return ["".join(f) for f in g]


# ------------------------------------------------------
# Paredes cambiantes (Bosque, Desierto, Cielo, Abismo...)
# ------------------------------------------------------
def poner_celda(c, f, ch):
    MAPA[f] = MAPA[f][:c] + ch + MAPA[f][c + 1:]


def recalcular_mapa():
    global DIST_INICIO
    DIST_INICIO = distancias(CELDA_INICIAL)


def paredes_abribles():
    """Paredes interiores que separan dos pasillos (se pueden derribar sin romper nada)."""
    out = []
    for y in range(1, FILAS - 1):
        for x in range(1, COLS - 1):
            if MAPA[y][x] == "#" and (x, y) not in PROTEGIDAS and (x, y) not in SECRETAS:
                if (MAPA[y][x - 1] != "#" and MAPA[y][x + 1] != "#") or (MAPA[y - 1][x] != "#" and MAPA[y + 1][x] != "#"):
                    out.append((x, y))
    return out


def pasillos_cerrables(ocupadas, max_pruebas=14):
    """Casillas de camino que se pueden tapar sin aislar ninguna otra zona."""
    base = len(DIST_INICIO)
    cand = [c for c in DIST_INICIO if c not in ocupadas and c not in PROTEGIDAS
            and 1 <= c[0] < COLS - 1 and 1 <= c[1] < FILAS - 1 and DIST_INICIO[c] > 3]
    random.shuffle(cand)
    out = []
    for c in cand[:max_pruebas]:
        poner_celda(c[0], c[1], "#")
        ok = len(distancias(CELDA_INICIAL)) == base - 1
        poner_celda(c[0], c[1], ".")
        if ok:
            out.append(c)
    return out


def cargar_mapa(mapa):
    global MAPA, DIST_INICIO
    MAPA = mapa
    DIST_INICIO = distancias(CELDA_INICIAL)


cargar_mapa(list(MAPA_BASE))


def celda_lejana(desde, minimo):
    d = distancias(desde)
    opciones = [c for c, v in d.items() if v >= minimo]
    if not opciones:
        opciones = [max(d, key=d.get)]
    return random.choice(opciones)


# ======================================================
# Graficos: sprites dibujados a alta resolucion y reducidos (suavizado)
# ======================================================
def hacer_sprite(fn, base, salida, *args, e=4):
    """Dibuja fn en una superficie 'e' veces mas grande y la reduce con suavizado."""
    grande = pygame.Surface((base * e, base * e), pygame.SRCALPHA)
    fn(grande, e, *args)
    return pygame.transform.smoothscale(grande, (salida, salida))


def _E(e):
    return lambda v: int(round(v * e))


def f_cereza(s, e):
    E = _E(e)
    for cx, cy in ((9, 20), (19, 19)):
        pygame.draw.line(s, (90, 130, 45), (E(cx), E(cy - 5)), (E(16), E(4)), E(1.4))
    for cx, cy in ((9, 20), (19, 19)):
        pygame.draw.circle(s, (130, 8, 28), (E(cx), E(cy)), E(6.6))
        pygame.draw.circle(s, (220, 36, 58), (E(cx - 0.4), E(cy - 0.4)), E(5.6))
        pygame.draw.circle(s, (255, 190, 195), (E(cx - 2), E(cy - 2.4)), E(1.6))
    pygame.draw.ellipse(s, (80, 175, 60), (E(15), E(1.5), E(9), E(4.5)))


def f_manzana(s, e):
    E = _E(e)
    pygame.draw.circle(s, (140, 12, 24), (E(14), E(16)), E(10))
    pygame.draw.circle(s, (226, 40, 46), (E(14), E(16)), E(9))
    pygame.draw.circle(s, (245, 80, 70), (E(11.5), E(14)), E(5.5))
    pygame.draw.ellipse(s, (255, 200, 195), (E(8), E(9.5), E(4), E(6)))
    pygame.draw.line(s, (100, 62, 30), (E(14), E(7.5)), (E(15.5), E(3)), E(1.6))
    pygame.draw.ellipse(s, (80, 175, 60), (E(15), E(2), E(8), E(4.5)))


def f_naranja(s, e):
    E = _E(e)
    pygame.draw.circle(s, (200, 96, 8), (E(14), E(15.5)), E(10.5))
    pygame.draw.circle(s, (252, 152, 24), (E(14), E(15.5)), E(9.5))
    pygame.draw.circle(s, (255, 190, 70), (E(11.5), E(13)), E(5))
    pygame.draw.ellipse(s, (255, 230, 170), (E(8), E(8.5), E(4), E(5)))
    for px, py in ((16, 18), (12, 21), (19, 14)):
        pygame.draw.circle(s, (215, 110, 10), (E(px), E(py)), E(0.7))
    pygame.draw.ellipse(s, (70, 160, 55), (E(13), E(2.5), E(8), E(4)))
    pygame.draw.circle(s, (70, 130, 45), (E(14), E(5.5)), E(1.4))


def f_uva(s, e):
    E = _E(e)
    pygame.draw.line(s, (100, 70, 35), (E(14), E(8)), (E(15), E(2.5)), E(1.6))
    pygame.draw.ellipse(s, (80, 175, 60), (E(15), E(1.5), E(8), E(4)))
    for cx, cy in ((8, 12), (14, 11.5), (20, 12), (11, 17.5), (17, 17.5), (14, 23)):
        pygame.draw.circle(s, (70, 25, 115), (E(cx), E(cy)), E(5))
        pygame.draw.circle(s, (140, 70, 200), (E(cx), E(cy)), E(4.2))
        pygame.draw.circle(s, (215, 175, 250), (E(cx - 1.3), E(cy - 1.4)), E(1.2))


def f_limon(s, e):
    E = _E(e)
    pygame.draw.ellipse(s, (190, 160, 20), (E(3), E(8), E(22), E(15)))
    pygame.draw.circle(s, (190, 160, 20), (E(3.5), E(15.5)), E(2))
    pygame.draw.circle(s, (190, 160, 20), (E(24.5), E(15.5)), E(2))
    pygame.draw.ellipse(s, (250, 230, 60), (E(4), E(9), E(20), E(13)))
    pygame.draw.circle(s, (250, 230, 60), (E(3.8), E(15.5)), E(1.6))
    pygame.draw.circle(s, (250, 230, 60), (E(24.2), E(15.5)), E(1.6))
    pygame.draw.ellipse(s, (255, 250, 190), (E(8), E(10.5), E(8), E(3.5)))
    pygame.draw.ellipse(s, (80, 175, 60), (E(17), E(4.5), E(8), E(4)))


def f_legendaria(s, e):
    """Fruta legendaria: orbe arcoiris con una estrella."""
    E = _E(e)
    for i in range(12):
        a = i * math.tau / 12
        h = i / 12
        r, g, b = colorsys.hsv_to_rgb(h, 0.7, 1.0)
        pygame.draw.circle(s, (int(r * 255), int(g * 255), int(b * 255)),
                           (E(14 + 11.6 * math.cos(a)), E(14 + 11.6 * math.sin(a))), E(2.6))
    pygame.draw.circle(s, (70, 30, 120), (E(14), E(14)), E(10.5))
    pygame.draw.circle(s, (130, 70, 210), (E(14), E(14)), E(9))
    pts = []
    for i in range(10):
        r = 7.4 if i % 2 == 0 else 3.2
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((E(14 + r * math.cos(a)), E(14.6 + r * math.sin(a))))
    pygame.draw.polygon(s, (255, 235, 120), pts)
    pygame.draw.circle(s, (255, 255, 255), (E(11), E(10)), E(1.3))


def f_cristal(s, e):
    """Fruta cristal: diamante azul."""
    E = _E(e)
    top = [(E(8), E(5)), (E(20), E(5)), (E(25), E(11)), (E(3), E(11))]
    pygame.draw.polygon(s, (150, 235, 255), top)
    pygame.draw.polygon(s, (60, 160, 230), [(E(3), E(11)), (E(25), E(11)), (E(14), E(25))])
    pygame.draw.polygon(s, (110, 205, 250), [(E(3), E(11)), (E(14), E(11)), (E(14), E(25))])
    pygame.draw.polygon(s, (230, 255, 255), [(E(8), E(5)), (E(12), E(5)), (E(9), E(11)), (E(5.6), E(11))])
    pygame.draw.lines(s, (20, 90, 160), True, [(E(8), E(5)), (E(20), E(5)), (E(25), E(11)), (E(14), E(25)), (E(3), E(11))], E(0.9))
    pygame.draw.line(s, (20, 90, 160), (E(3), E(11)), (E(25), E(11)), E(0.7))


def f_dorada(s, e):
    """Fruta dorada: manzana de oro con corona."""
    E = _E(e)
    pygame.draw.circle(s, (150, 100, 10), (E(14), E(16)), E(10))
    pygame.draw.circle(s, (250, 200, 40), (E(14), E(16)), E(9))
    pygame.draw.circle(s, (255, 236, 130), (E(11.5), E(14)), E(5.4))
    pygame.draw.ellipse(s, (255, 255, 230), (E(8), E(9.5), E(4), E(6)))
    pygame.draw.line(s, (110, 70, 20), (E(14), E(7.5)), (E(15.5), E(3.6)), E(1.6))
    pts = [(E(9), E(4.6)), (E(9), E(1.4)), (E(11.5), E(3)), (E(14), E(0.4)), (E(16.5), E(3)), (E(19), E(1.4)), (E(19), E(4.6))]
    pygame.draw.polygon(s, (255, 150, 30), pts)
    pygame.draw.polygon(s, (255, 235, 100), [(x, y + E(0.6)) for x, y in pts])


def f_fruta_corazon(s, e):
    """Fruta del Corazon (solo en la dimension oculta)."""
    E = _E(e)

    def forma(c, g):
        pygame.draw.circle(s, c, (E(9.5), E(11)), E(6.4 + g))
        pygame.draw.circle(s, c, (E(18.5), E(11)), E(6.4 + g))
        pygame.draw.polygon(s, c, [(E(3 - g), E(13)), (E(25 + g), E(13)), (E(14), E(26 + g))])
    forma((90, 0, 30), 1)
    forma((230, 40, 90), 0)
    pygame.draw.ellipse(s, (255, 190, 210), (E(6), E(6.5), E(5), E(3.4)))
    pygame.draw.line(s, (70, 150, 60), (E(14), E(6)), (E(16), E(2)), E(1.5))
    pygame.draw.ellipse(s, (255, 220, 90), (E(15), E(1), E(7), E(3.6)))


# nombre, funcion de dibujo, puntos, color de las particulas
# (los 5 primeros son las frutas normales; el resto son frutas especiales)
N_FRUTAS_NORMALES = 5
FRUTAS = [
    ("cereza", f_cereza, 10, (235, 50, 70)),
    ("manzana", f_manzana, 20, (240, 60, 60)),
    ("naranja", f_naranja, 30, (255, 165, 40)),
    ("limon", f_limon, 40, (250, 232, 70)),
    ("uva", f_uva, 50, (170, 100, 225)),
    ("legendaria", f_legendaria, 250, (255, 140, 255)),
    ("cristal", f_cristal, 150, (120, 230, 255)),
    ("dorada", f_dorada, 1000, (255, 215, 60)),
    ("corazon", f_fruta_corazon, 400, (255, 70, 120)),
]
IDX_LEGENDARIA, IDX_CRISTAL, IDX_DORADA, IDX_CORAZON = 5, 6, 7, 8
SPR_FRUTAS = [hacer_sprite(f[1], 28, 28) for f in FRUTAS]
SPR_FRUTAS_GRANDES = [hacer_sprite(f[1], 28, 60) for f in FRUTAS]
SPR_FRUTAS_HUD = [hacer_sprite(f[1], 28, 30) for f in FRUTAS]


# ======================================================
# Brillos (glow) reutilizados por frutas, poderes, etc.
# ======================================================
def crear_brillo(radio, color):
    s = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
    for r in range(radio, 0, -1):
        a = int(110 * (1 - r / radio) ** 2)
        pygame.draw.circle(s, (*color, a), (radio, radio), r)
    return s


BRILLOS_FRUTA = [crear_brillo(24, f[3]) for f in FRUTAS]
BRILLO_BALA = crear_brillo(16, (120, 220, 255))

COLORES_FANTASMA = [(235, 64, 64), (255, 130, 200), (70, 200, 235), (255, 165, 50)]


def f_fantasma(s, e, color, fase, direccion):
    E = _E(e)
    oscuro = tuple(max(0, c - 90) for c in color)
    claro = tuple(min(255, c + 70) for c in color)

    def forma(col, g):
        pygame.draw.circle(s, col, (E(15), E(14)), E(12 + g))
        pts = [(E(3 - g), E(14))]
        for x in range(3, 28):
            y = 25 + 2.0 * math.sin(x * 0.9 + fase * math.pi / 2) + g
            pts.append((E(x), E(y)))
        pts.append((E(27 + g), E(14)))
        pygame.draw.polygon(s, col, pts)

    forma(oscuro, 1.2)
    forma(color, 0)
    pygame.draw.ellipse(s, claro, (E(7), E(4), E(8), E(4)))
    dx, dy = DIRS[direccion]
    for ex in (10, 20):
        pygame.draw.circle(s, (250, 250, 250), (E(ex + dx * 1.2), E(13 + dy * 1.2)), E(4.4))
        pygame.draw.circle(s, (25, 30, 90), (E(ex + dx * 3), E(13 + dy * 2.6)), E(2.2))


def mezcla(col, k):
    """k<1 oscurece, k>1 aclara."""
    return tuple(max(0, min(255, int(c * k))) for c in col)


def _badge(s, e, color):
    E = _E(e)
    pygame.draw.circle(s, mezcla(color, 0.75), (E(14), E(14)), E(13.6))
    pygame.draw.circle(s, (20, 20, 38), (E(14), E(14)), E(12))


def f_estrella(s, e):
    E = _E(e)
    _badge(s, e, (255, 215, 60))
    for r1, r2, col in ((9.6, 4.2, (255, 205, 50)), (6.2, 2.6, (255, 244, 165))):
        pts = []
        for i in range(10):
            r = r1 if i % 2 == 0 else r2
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((E(14 + r * math.cos(a)), E(14.8 + r * math.sin(a))))
        pygame.draw.polygon(s, col, pts)


def f_hielo(s, e):
    E = _E(e)
    _badge(s, e, (120, 215, 255))
    for ang in (0, 60, 120):
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        pygame.draw.line(s, (185, 238, 255), (E(14 - 8.5 * dx), E(14 - 8.5 * dy)),
                         (E(14 + 8.5 * dx), E(14 + 8.5 * dy)), E(1.7))
        for sgn in (-1, 1):
            px, py = 14 + sgn * 6 * dx, 14 + sgn * 6 * dy
            pygame.draw.circle(s, (230, 250, 255), (E(px), E(py)), E(1.4))
    pygame.draw.circle(s, (255, 255, 255), (E(14), E(14)), E(2))


def f_bomba(s, e):
    E = _E(e)
    _badge(s, e, (255, 120, 60))
    pygame.draw.circle(s, (70, 72, 90), (E(13.5), E(16)), E(7.2))
    pygame.draw.circle(s, (34, 35, 46), (E(13.5), E(16)), E(6.4))
    pygame.draw.circle(s, (120, 125, 150), (E(11.3), E(13.8)), E(1.7))
    pygame.draw.line(s, (205, 170, 110), (E(17), E(10.6)), (E(20), E(6.6)), E(1.4))
    pygame.draw.circle(s, (255, 130, 40), (E(20.8), E(5.8)), E(2.4))
    pygame.draw.circle(s, (255, 235, 110), (E(20.8), E(5.8)), E(1.2))


def f_rafaga(s, e):
    E = _E(e)
    _badge(s, e, (220, 110, 255))
    for dx, dy in DIRS.values():
        tip = (14 + dx * 10, 14 + dy * 10)
        bx, by = 14 + dx * 4.6, 14 + dy * 4.6
        px, py = -dy * 3.6, dx * 3.6
        pygame.draw.polygon(s, (235, 150, 255), [(E(tip[0]), E(tip[1])), (E(bx + px), E(by + py)),
                                                 (E(bx - px), E(by - py))])
    pygame.draw.circle(s, (255, 255, 255), (E(14), E(14)), E(2.6))


def f_rayo(s, e):
    E = _E(e)
    _badge(s, e, (255, 180, 50))
    pts = [(16.5, 3.8), (9, 15), (13.6, 15), (11, 24.4), (19.5, 12.6), (15, 12.6)]
    pygame.draw.polygon(s, (255, 205, 60), [(E(x), E(y)) for x, y in pts])
    pygame.draw.polygon(s, (255, 245, 170), [(E(x), E(y)) for x, y in pts], E(0.8))


def f_eclipse(s, e):
    E = _E(e)
    _badge(s, e, (255, 190, 80))
    pygame.draw.circle(s, (255, 200, 90), (E(14), E(14)), E(9.4))
    pygame.draw.circle(s, (30, 8, 24), (E(14), E(14)), E(7.6))
    for i in range(12):
        a = i * math.tau / 12
        pygame.draw.line(s, (255, 230, 140), (E(14 + 9.8 * math.cos(a)), E(14 + 9.8 * math.sin(a))),
                         (E(14 + 12.4 * math.cos(a)), E(14 + 12.4 * math.sin(a))), E(1.1))


# nombre, texto al recogerlo, color
PODERES = [
    ("estrella", "¡SUPER!", (255, 215, 60)),
    ("hielo", "¡CONGELADOS!", (120, 215, 255)),
    ("bomba", "+1 BOMBA", (255, 130, 60)),
    ("rafaga", "¡RAFAGA!", (225, 125, 255)),
    ("rayo", "¡VELOCIDAD!", (255, 185, 55)),
    ("eclipse", "¡ECLIPSE!", (255, 200, 90)),
]
SPR_PODERES = [hacer_sprite(f, 28, 28) for f in (f_estrella, f_hielo, f_bomba, f_rafaga, f_rayo, f_eclipse)]


def f_corazon(s, e, lleno):
    E = _E(e)
    borde = (120, 15, 35) if lleno else (60, 60, 78)
    col = (240, 55, 85) if lleno else (38, 38, 54)

    def forma(c, g):
        pygame.draw.circle(s, c, (E(9), E(9.5)), E(5.8 + g))
        pygame.draw.circle(s, c, (E(19), E(9.5)), E(5.8 + g))
        pygame.draw.polygon(s, c, [(E(3.4 - g), E(11)), (E(24.6 + g), E(11)), (E(14), E(24.5 + g))])

    forma(borde, 1)
    forma(col, 0)
    if lleno:
        pygame.draw.ellipse(s, (255, 175, 195), (E(6), E(5.5), E(4), E(3)))


def _sprites_color(col):
    return [{d: hacer_sprite(f_fantasma, 30, 30, col, fase, d) for d in DIRS} for fase in range(4)]


SPR_ASUSTADO = _sprites_color((50, 80, 225))
SPR_PARPADEO = _sprites_color((235, 235, 255))
BRILLOS_PODER = [crear_brillo(28, p[2]) for p in PODERES]
BRILLOS_ESTRELLA = [crear_brillo(30, c) for c in
                    ((255, 80, 80), (255, 200, 60), (90, 230, 110), (80, 200, 255), (200, 110, 255), (255, 120, 200))]

SPR_CORAZON_S = hacer_sprite(f_corazon, 28, 24, True)
SPR_CORAZON_VACIO_S = hacer_sprite(f_corazon, 28, 24, False)


def crear_sombra(ancho, alto, alfa=90):
    s = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, alfa), s.get_rect())
    return s


SOMBRA = crear_sombra(24, 9)
SOMBRA_FRUTA = crear_sombra(18, 6, 70)


def crear_degradado_v(ancho, alto, c1, c2):
    s = pygame.Surface((ancho, alto))
    for y in range(alto):
        k = y / max(1, alto - 1)
        col = tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))
        pygame.draw.line(s, col, (0, y), (ancho, y))
    return s


def crear_vineta():
    w, h = 100, 76
    peq = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            dx = (x - w / 2) / (w / 2)
            dy = (y - h / 2) / (h / 2)
            d = math.hypot(dx, dy)
            a = int(max(0.0, min(1.0, (d - 0.65) / 0.8)) * 150)
            peq.set_at((x, y), (0, 0, 0, a))
    return pygame.transform.smoothscale(peq, (ANCHO, ALTO_MAPA))


VINETA = crear_vineta()
HUD_BG = crear_degradado_v(ANCHO, ALTO_HUD, (32, 32, 50), (14, 14, 24))
SOMB_V = pygame.Surface((TAM, 12), pygame.SRCALPHA)
SOMB_H = pygame.Surface((8, TAM), pygame.SRCALPHA)
for _i in range(12):
    pygame.draw.line(SOMB_V, (0, 0, 0, int(120 * (1 - _i / 12) ** 1.5)), (0, _i), (TAM, _i))
for _i in range(8):
    pygame.draw.line(SOMB_H, (0, 0, 0, int(80 * (1 - _i / 8) ** 1.5)), (_i, 0), (_i, TAM))


def dibujar_pared(s, t, c, f, rnd):
    x, y = c * TAM, f * TAM
    abajo_libre = f + 1 < FILAS and MAPA[f + 1][c] != "#"
    arriba_libre = f == 0 or MAPA[f - 1][c] != "#"
    izq_libre = c == 0 or MAPA[f][c - 1] != "#"
    der_libre = c + 1 >= COLS or MAPA[f][c + 1] != "#"
    alto_cara = TAM - 9 if abajo_libre else TAM

    if abajo_libre:  # cara frontal (da sensacion de altura)
        pygame.draw.rect(s, t["sombra"], (x, y + TAM - 9, TAM, 9))
        pygame.draw.rect(s, mezcla(t["sombra"], 0.7), (x, y + TAM - 3, TAM, 3))
    pygame.draw.rect(s, t["pared"], (x, y, TAM, alto_cara))

    # ladrillos
    mortero = mezcla(t["pared"], 0.82)
    mitad = y + alto_cara // 2
    pygame.draw.line(s, mortero, (x, mitad), (x + TAM, mitad))
    pygame.draw.line(s, mortero, (x + TAM // 2, y), (x + TAM // 2, mitad))
    pygame.draw.line(s, mortero, (x, mitad), (x, y + alto_cara))
    for _ in range(4):  # textura
        px = x + rnd.randint(2, TAM - 5)
        py = y + rnd.randint(2, max(3, alto_cara - 4))
        col = mezcla(t["pared"], rnd.choice((0.9, 1.1)))
        pygame.draw.rect(s, col, (px, py, rnd.randint(2, 4), rnd.randint(1, 2)))

    sec = SECRETAS.get((c, f))
    if sec is not None and sec["tell"]:  # pista casi invisible de que la pared es falsa
        if sec["tell"] == 1:
            clar = mezcla(t["pared"], 1.22)
            pygame.draw.line(s, clar, (x + 12, y + 6), (x + 17, y + 14), 1)
            pygame.draw.line(s, clar, (x + 17, y + 14), (x + 14, y + 22), 1)
            pygame.draw.line(s, clar, (x + 17, y + 14), (x + 25, y + 17), 1)
        else:
            pygame.draw.rect(s, mezcla(t["pared"], 1.18), (x + 20, y + 10, 3, 2))
    # bisel solo donde el borde da al piso
    if arriba_libre:
        pygame.draw.rect(s, t["luz"], (x, y, TAM, 3))
    if izq_libre:
        pygame.draw.rect(s, t["luz"], (x, y, 2, alto_cara))
    if der_libre:
        pygame.draw.rect(s, t["sombra"], (x + TAM - 2, y, 2, alto_cara))


def crear_fondo(t, semilla):
    s = pygame.Surface((ANCHO, ALTO_MAPA))
    s.fill(t["fondo"])
    for f in range(FILAS):
        for c in range(COLS):
            rnd = random.Random(semilla * 7919 + f * 131 + c)  # textura estable por casilla
            x, y = c * TAM, f * TAM
            if MAPA[f][c] == "#":
                dibujar_pared(s, t, c, f, rnd)
            else:
                col = t["piso"] if (c + f) % 2 == 0 else t["piso2"]
                pygame.draw.rect(s, col, (x, y, TAM, TAM))
                for _ in range(5):
                    px = x + rnd.randint(2, TAM - 4)
                    py = y + rnd.randint(2, TAM - 4)
                    c2 = mezcla(col, rnd.choice((0.88, 1.12)))
                    pygame.draw.rect(s, c2, (px, py, rnd.randint(1, 3), rnd.randint(1, 2)))
    for f in range(FILAS):  # sombras que proyectan las paredes sobre el piso
        for c in range(COLS):
            if MAPA[f][c] != "#":
                if f > 0 and MAPA[f - 1][c] == "#":
                    s.blit(SOMB_V, (c * TAM, f * TAM))
                if c > 0 and MAPA[f][c - 1] == "#":
                    s.blit(SOMB_H, (c * TAM, f * TAM))
    return s


# ======================================================
# Texto
# ======================================================
def texto(surf, txt, fnt, color, pos, centro=False, sombra=(0, 0, 0), desp=2, alfa=255):
    img = fnt.render(txt, True, color)
    r = img.get_rect()
    if centro:
        r.center = pos
    else:
        r.topleft = pos
    if sombra:
        sh = fnt.render(txt, True, sombra)
        if alfa < 255:
            sh.set_alpha(alfa)
        surf.blit(sh, (r.x + desp, r.y + desp))
    if alfa < 255:
        img.set_alpha(alfa)
    surf.blit(img, r)
    return r


def texto_borde(surf, txt, fnt, color, borde, pos, grosor=3):
    img = fnt.render(txt, True, color)
    cont = fnt.render(txt, True, borde)
    r = img.get_rect(center=pos)
    for ox in range(-grosor, grosor + 1):
        for oy in range(-grosor, grosor + 1):
            if ox * ox + oy * oy <= grosor * grosor:
                surf.blit(cont, (r.x + ox, r.y + oy))
    surf.blit(img, r)


# ======================================================
# Particulas y textos flotantes
# ======================================================
class Particula:
    def __init__(self, x, y, vx, vy, vida, color, radio, grav=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.vida = self.vida_max = vida
        self.color, self.radio, self.grav = color, radio, grav

    def actualizar(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.grav
        self.vx *= 0.98
        self.vida -= 1

    def dibujar(self, m):
        r = max(1, int(self.radio * self.vida / self.vida_max))
        pygame.draw.circle(m, self.color, (int(self.x), int(self.y)), r)


def chispas(lista, x, y, color, n=14, vel=3.0, vida=30, radio=3, grav=0.05):
    if not CONFIG["particulas"]:
        n = (n + 3) // 4
    for _ in range(n):
        ang = random.uniform(0, math.tau)
        v = random.uniform(0.3, 1.0) * vel
        c = mezcla(color, random.uniform(0.85, 1.25))
        lista.append(Particula(x, y, math.cos(ang) * v, math.sin(ang) * v,
                               random.randint(vida // 2, vida), c, radio, grav))


class TextoFlotante:
    def __init__(self, x, y, txt, color, fnt=F_MED, vida=60):
        self.img = fnt.render(txt, True, color)
        self.sombra = fnt.render(txt, True, (0, 0, 0))
        self.x, self.y = x, y
        self.vida = self.vida_max = vida

    def actualizar(self):
        self.y -= 0.8
        self.vida -= 1

    def dibujar(self, m):
        a = int(255 * min(1.0, self.vida / (self.vida_max * 0.5)))
        self.img.set_alpha(a)
        self.sombra.set_alpha(a)
        r = self.img.get_rect(center=(int(self.x), int(self.y)))
        r.x = max(4, min(ANCHO - r.width - 4, r.x))
        m.blit(self.sombra, (r.x + 2, r.y + 2))
        m.blit(self.img, r)


# ======================================================
# Fruta
# ======================================================
class Fruta:
    def __init__(self, celda, tipo, ttl=None):
        self.cx = celda[0] * TAM + TAM / 2
        self.cy = celda[1] * TAM + TAM / 2
        self.tipo = tipo
        self.ttl = ttl     # frames que dura en el suelo (solo frutas extra y especiales)
        self.fase = random.uniform(0, math.tau)

    def dibujar(self, m, t):
        if self.ttl is not None and self.ttl < 150 and (self.ttl // 5) % 2 == 0:
            return
        b = math.sin(t * 0.08 + self.fase)
        especial = self.tipo >= N_FRUTAS_NORMALES
        brillo = BRILLOS_FRUTA[self.tipo]
        brillo.set_alpha(int(150 + 90 * math.sin(t * 0.06 + self.fase)))
        m.blit(brillo, (int(self.cx - 24), int(self.cy - 24)))
        if especial:  # las frutas raras brillan mas y lanzan destellos
            col = FRUTAS[self.tipo][3]
            g = crear_brillo_cache(38, col)
            g.set_alpha(int(120 + 100 * abs(math.sin(t * 0.07 + self.fase))))
            m.blit(g, (int(self.cx - 38), int(self.cy - 38)))
            for i in range(4):
                a = t * 0.08 + self.fase + i * math.pi / 2
                px, py = self.cx + math.cos(a) * 22, self.cy + math.sin(a) * 22 - 2 * b
                pygame.draw.polygon(m, col, [(px, py - 4), (px + 2, py), (px, py + 4), (px - 2, py)])
        m.blit(SOMBRA_FRUTA, (int(self.cx - 9), int(self.cy + 9)))
        m.blit(SPR_FRUTAS[self.tipo], (int(self.cx - 14), int(self.cy - 14 - 3 * b)))


# ======================================================
# Sprites de mundos: enemigos, jefes, iconos de poderes, trampas y skins
# ======================================================
# Paletas: (principal, oscuro, claro, acento)
# orden: 0 perseguidor A, 1 emboscador, 2 perseguidor B, 3 cazador
PALETAS = {
    1: [((150, 152, 168), (78, 80, 98), (222, 224, 234), (255, 212, 60)),      # lobos
        ((74, 76, 92), (32, 34, 46), (150, 152, 170), (255, 80, 80)),
        ((196, 168, 132), (112, 88, 64), (242, 228, 204), (255, 212, 60)),
        ((186, 82, 60), (110, 40, 30), (240, 200, 170), (255, 170, 40))],
    2: [((226, 170, 82), (138, 88, 30), (250, 222, 152), (255, 70, 60)),       # escorpiones
        ((96, 70, 120), (48, 30, 70), (170, 140, 200), (255, 90, 200)),
        ((150, 168, 72), (84, 98, 34), (206, 220, 130), (255, 70, 60)),
        ((208, 66, 52), (120, 30, 26), (250, 170, 140), (255, 230, 90))],
    3: [((222, 62, 52), (130, 26, 26), (250, 150, 110), (255, 200, 60)),       # diablillos
        ((136, 66, 176), (70, 30, 100), (200, 150, 230), (255, 200, 60)),
        ((250, 140, 44), (150, 70, 20), (255, 210, 130), (255, 240, 120)),
        ((60, 130, 236), (26, 60, 140), (150, 200, 255), (255, 255, 200))],
    4: [((226, 238, 250), (120, 150, 190), (176, 214, 240), (40, 60, 110)),    # yetis
        ((146, 192, 236), (70, 110, 170), (200, 226, 250), (40, 60, 110)),
        ((196, 204, 218), (110, 120, 145), (226, 232, 242), (40, 60, 110)),
        ((110, 156, 220), (50, 84, 150), (170, 204, 240), (255, 90, 90))],
    5: [((150, 158, 176), (58, 62, 78), (196, 204, 220), (70, 230, 255)),      # robots
        ((96, 100, 120), (36, 38, 52), (150, 154, 172), (255, 80, 210)),
        ((206, 212, 224), (100, 108, 128), (236, 240, 248), (110, 255, 130)),
        ((220, 180, 70), (120, 86, 24), (250, 224, 140), (255, 130, 40))],
    6: [((90, 176, 86), (44, 108, 46), (150, 220, 110), (255, 220, 60)),       # ranas
        ((70, 120, 150), (32, 64, 90), (130, 180, 200), (255, 90, 200)),
        ((150, 180, 60), (86, 112, 30), (200, 226, 110), (255, 220, 60)),
        ((196, 90, 70), (120, 42, 34), (230, 150, 120), (255, 230, 90))],
    7: [((110, 90, 140), (52, 40, 74), (170, 150, 200), (255, 90, 210)),       # murcielagos
        ((60, 54, 78), (26, 22, 40), (110, 100, 140), (255, 60, 60)),
        ((150, 110, 170), (86, 56, 108), (206, 170, 224), (120, 255, 220)),
        ((196, 60, 90), (120, 26, 42), (230, 120, 140), (255, 230, 90))],
    8: [((210, 150, 80), (130, 86, 34), (245, 205, 140), (255, 240, 130)),     # aguilas
        ((160, 170, 200), (86, 96, 128), (216, 224, 244), (255, 230, 90)),
        ((150, 100, 60), (90, 54, 26), (206, 160, 110), (255, 240, 130)),
        ((230, 200, 90), (150, 120, 30), (250, 232, 170), (110, 170, 255))],
    9: [((110, 220, 170), (44, 130, 96), (170, 250, 220), (255, 90, 230)),     # criaturas del abismo
        ((150, 90, 220), (78, 34, 140), (200, 160, 250), (110, 255, 220)),
        ((90, 150, 220), (34, 78, 140), (150, 200, 250), (255, 90, 230)),
        ((220, 90, 150), (140, 34, 78), (250, 160, 200), (110, 255, 220))],
}
PALETAS_JEFE = {
    1: ((88, 92, 116), (30, 32, 46), (172, 178, 198), (255, 60, 60)),
    2: ((190, 122, 50), (100, 56, 20), (240, 200, 120), (255, 60, 60)),
    3: ((176, 32, 42), (70, 10, 20), (240, 110, 70), (255, 220, 60)),
    4: ((196, 224, 248), (80, 110, 160), (150, 190, 230), (255, 70, 70)),
    5: ((124, 130, 154), (30, 32, 46), (172, 180, 202), (255, 60, 140)),
    6: ((70, 160, 76), (30, 90, 40), (140, 220, 120), (255, 220, 60)),
    7: ((90, 66, 120), (44, 30, 66), (150, 120, 180), (255, 90, 210)),
    8: ((220, 170, 80), (140, 100, 34), (250, 220, 150), (110, 170, 255)),
    9: ((130, 80, 220), (66, 30, 130), (190, 150, 250), (110, 255, 220)),
}


# ======================================================
# Enemigos (lienzo 30x30). fn(s, e, pal, fase, direccion)
# ======================================================
def f_lobo(s, e, pal, fase, d):
    E = _E(e)
    pel, osc, cla, ojo = pal
    dx, dy = DIRS[d]
    mov = 1.5 if fase % 2 == 0 else -1.0
    pygame.draw.ellipse(s, osc, (E(20.5 + mov * 0.4), E(16.5), E(9), E(5)))       # cola
    pygame.draw.ellipse(s, pel, (E(21.2 + mov * 0.4), E(17), E(7.6), E(3.8)))
    for i, px in enumerate((8.5, 12.5, 17.5, 21.5)):                              # patas
        off = 1.6 if (i + fase) % 2 == 0 else 0
        pygame.draw.ellipse(s, osc, (E(px - 2.3), E(23.2 - off), E(4.6), E(5)))
    pygame.draw.ellipse(s, osc, (E(4.5), E(13), E(21), E(13.5)))                  # cuerpo
    pygame.draw.ellipse(s, pel, (E(5.3), E(13.6), E(19.4), E(11.8)))
    for sg in (-1, 1):                                                            # orejas
        cx = 15 + sg * 6.4
        pygame.draw.polygon(s, osc, [(E(cx - 3.4), E(9.5)), (E(cx + 3.4), E(9.5)), (E(cx + sg * 0.6), E(1.2))])
        pygame.draw.polygon(s, cla, [(E(cx - 1.6), E(8.6)), (E(cx + 1.6), E(8.6)), (E(cx + sg * 0.4), E(3.8))])
    pygame.draw.circle(s, osc, (E(15), E(13)), E(9.6))                            # cabeza
    pygame.draw.circle(s, pel, (E(15), E(13)), E(8.7))
    if d == "arriba":
        pygame.draw.ellipse(s, mezcla(pel, 1.15), (E(10), E(6.5), E(10), E(5)))
        return
    ox, oy = dx * 1.8, dy * 1.0
    pygame.draw.ellipse(s, cla, (E(10.2 + ox), E(13.6 + oy), E(9.6), E(7.2)))     # hocico
    pygame.draw.ellipse(s, (28, 28, 38), (E(13.4 + ox), E(14.2 + oy), E(3.2), E(2.4)))
    for fx in (12.6, 16.6):                                                       # colmillos
        pygame.draw.polygon(s, (255, 255, 255), [(E(fx + ox), E(19.3 + oy)), (E(fx + 1.6 + ox), E(19.3 + oy)),
                                                 (E(fx + 0.8 + ox), E(21.6 + oy))])
    for ex in (10.8, 19.2):                                                       # ojos
        pygame.draw.ellipse(s, ojo, (E(ex - 2.2 + dx * 1.3), E(9.6 + dy * 0.8), E(4.4), E(3.4)))
        pygame.draw.circle(s, (20, 20, 30), (E(ex + dx * 1.6), E(11.3 + dy * 0.9)), E(0.9))
    pygame.draw.line(s, osc, (E(8.2), E(8.2)), (E(12.8), E(9.8)), E(1.2))
    pygame.draw.line(s, osc, (E(21.8), E(8.2)), (E(17.2), E(9.8)), E(1.2))


def f_escorpion(s, e, pal, fase, d):
    E = _E(e)
    cue, osc, cla, acc = pal
    dx, dy = DIRS[d]
    for i in range(3):                                                            # patas
        y = 15 + i * 3.4
        off = 1.8 if (i + fase) % 2 == 0 else -0.8
        for sg in (-1, 1):
            pygame.draw.line(s, osc, (E(15 + sg * 5.5), E(y)), (E(15 + sg * (11 + off)), E(y + 2.4)), E(1.5))
    cola = [(15, 11.6, 2.7), (15, 8, 2.4), (16.3, 4.8, 2.1)]                      # cola arriba
    for cx, cy, r in cola:
        pygame.draw.circle(s, osc, (E(cx), E(cy)), E(r + 0.7))
    for cx, cy, r in cola:
        pygame.draw.circle(s, cue, (E(cx), E(cy)), E(r))
    pygame.draw.polygon(s, acc, [(E(17.6), E(3.2)), (E(20.8), E(5.6)), (E(17.4), E(6.6))])  # aguijon
    pygame.draw.ellipse(s, osc, (E(7.5), E(12.5), E(15), E(13)))                  # cuerpo
    pygame.draw.ellipse(s, cue, (E(8.3), E(13.1), E(13.4), E(11.6)))
    for yy in (18.2, 21, 23.4):
        pygame.draw.line(s, osc, (E(10.4), E(yy)), (E(19.6), E(yy)), E(0.9))
    for sg in (-1, 1):                                                            # brazos y pinzas
        pygame.draw.line(s, osc, (E(15 + sg * 6.2), E(15)), (E(15 + sg * 10), E(9.6)), E(2))
        cx = 15 + sg * 10.4
        pygame.draw.circle(s, osc, (E(cx), E(7.8)), E(3.8))
        pygame.draw.circle(s, cue, (E(cx), E(7.8)), E(3.1))
        pygame.draw.polygon(s, osc, [(E(cx - 1.3), E(4.2)), (E(cx + 1.3), E(4.2)), (E(cx), E(7.2))])
    for ex in (12.8, 17.2):                                                       # ojos
        pygame.draw.circle(s, (255, 255, 255), (E(ex + dx * 0.8), E(15.6 + dy * 0.6)), E(1.7))
        pygame.draw.circle(s, (20, 20, 30), (E(ex + dx * 1.3), E(15.9 + dy * 0.9)), E(0.9))


def f_diablillo(s, e, pal, fase, d):
    E = _E(e)
    cue, osc, cla, acc = pal
    dx, dy = DIRS[d]
    pygame.draw.line(s, osc, (E(22.5), E(23)), (E(27), E(19.6)), E(1.6))          # cola con flecha
    pygame.draw.polygon(s, osc, [(E(27), E(17)), (E(29.4), E(20.6)), (E(24.8), E(20.2))])
    for sg, ph in ((-1, 0), (1, 1)):                                              # pies
        off = 1.4 if (fase + ph) % 2 == 0 else 0
        pygame.draw.ellipse(s, osc, (E(15 + sg * 4.6 - 2.6), E(24 - off), E(5.2), E(4.4)))
    for sg in (-1, 1):                                                            # cuernos
        pygame.draw.polygon(s, (70, 34, 34), [(E(15 + sg * 3.4), E(8.8)), (E(15 + sg * 7.8), E(11)),
                                              (E(15 + sg * 8.6), E(2.4))])
    h = (3.0, 5.0, 4.0, 6.0)[fase % 4]                                            # llama animada
    pygame.draw.polygon(s, (255, 150, 40), [(E(12.6), E(8.6)), (E(13.4), E(8.6 - h * 0.6)), (E(15), E(8.6 - h)),
                                            (E(16.6), E(8.6 - h * 0.6)), (E(17.4), E(8.6))])
    pygame.draw.polygon(s, (255, 236, 130), [(E(13.8), E(8.6)), (E(15), E(8.6 - h * 0.7)), (E(16.2), E(8.6))])
    pygame.draw.circle(s, osc, (E(15), E(16.5)), E(9.6))                          # cuerpo
    pygame.draw.circle(s, cue, (E(15), E(16.5)), E(8.8))
    pygame.draw.ellipse(s, cla, (E(10.2), E(17.6), E(9.6), E(6.8)))
    for sg, ph in ((-1, 1), (1, 0)):                                              # brazos
        oy = 1.2 if (fase + ph) % 2 == 0 else 0
        pygame.draw.circle(s, osc, (E(15 + sg * 10), E(18.4 + oy)), E(2.6))
        pygame.draw.circle(s, cue, (E(15 + sg * 10), E(18.4 + oy)), E(2))
    if d == "arriba":
        return
    ox, oy = dx * 1.3, dy * 0.8
    for ex in (11.6, 18.4):                                                       # ojos furiosos
        pygame.draw.ellipse(s, (255, 240, 120), (E(ex - 2 + ox), E(13.4 + oy), E(4), E(3.2)))
        pygame.draw.circle(s, (30, 10, 10), (E(ex + dx * 1.0 + ox * 0.3), E(15 + dy * 0.7 + oy * 0.3)), E(0.9))
    pygame.draw.line(s, (60, 20, 20), (E(8.6 + ox), E(12.4 + oy)), (E(13.4 + ox), E(14 + oy * 0)), E(1.3))
    pygame.draw.line(s, (60, 20, 20), (E(21.4 + ox), E(12.4 + oy)), (E(16.6 + ox), E(14 + oy * 0)), E(1.3))
    pygame.draw.ellipse(s, (60, 10, 15), (E(11.4 + ox), E(19 + oy), E(7.2), E(3.6)))
    for fx in (12.4, 16.0):
        pygame.draw.polygon(s, (255, 255, 255), [(E(fx + ox), E(19 + oy)), (E(fx + 1.6 + ox), E(19 + oy)),
                                                 (E(fx + 0.8 + ox), E(21.4 + oy))])


def f_yeti(s, e, pal, fase, d):
    E = _E(e)
    pel, osc, cla, acc = pal
    dx, dy = DIRS[d]
    for sg, ph in ((-1, 0), (1, 1)):                                              # pies
        off = 1.5 if (fase + ph) % 2 == 0 else 0
        pygame.draw.ellipse(s, osc, (E(15 + sg * 5 - 3.4), E(23.6 - off), E(6.8), E(5)))
    for sg, ph in ((-1, 1), (1, 0)):                                              # brazos
        oy = 1.8 if (fase + ph) % 2 == 0 else 0
        pygame.draw.circle(s, osc, (E(15 + sg * 11.2), E(17 + oy)), E(3.9))
        pygame.draw.circle(s, pel, (E(15 + sg * 11.2), E(17 + oy)), E(3.2))
    for k in range(12):                                                           # pelaje
        a = k * math.pi / 6
        pygame.draw.circle(s, osc, (E(15 + math.cos(a) * 9.6), E(16 + math.sin(a) * 9.8)), E(3.8))
    for k in range(12):
        a = k * math.pi / 6
        pygame.draw.circle(s, pel, (E(15 + math.cos(a) * 9.3), E(16 + math.sin(a) * 9.5)), E(3.2))
    pygame.draw.circle(s, pel, (E(15), E(16)), E(9))
    if d == "arriba":
        return
    ox, oy = dx * 1.3, dy * 0.8
    pygame.draw.ellipse(s, cla, (E(9 + ox), E(10.5 + oy), E(12), E(11)))
    for ex in (12.4, 17.6):
        pygame.draw.circle(s, (255, 255, 255), (E(ex + ox), E(14 + oy)), E(1.9))
        pygame.draw.circle(s, acc, (E(ex + dx * 0.7 + ox), E(14.3 + dy * 0.5 + oy)), E(1.0))
    pygame.draw.line(s, acc, (E(10.6 + ox), E(11.6 + oy)), (E(13.8 + ox), E(12.6 + oy)), E(1.1))
    pygame.draw.line(s, acc, (E(19.4 + ox), E(11.6 + oy)), (E(16.2 + ox), E(12.6 + oy)), E(1.1))
    pygame.draw.ellipse(s, (40, 50, 90), (E(11.6 + ox), E(17.2 + oy), E(6.8), E(3.8)))
    for fx in (12.6, 15.4):
        pygame.draw.polygon(s, (255, 255, 255), [(E(fx + ox), E(17.2 + oy)), (E(fx + 1.4 + ox), E(17.2 + oy)),
                                                 (E(fx + 0.7 + ox), E(19 + oy))])


def f_robot(s, e, pal, fase, d):
    E = _E(e)
    met, osc, cla, acc = pal
    dx, dy = DIRS[d]
    for sg in (-1, 1):                                                            # orugas
        x0 = 15 + sg * 6.2 - 3.4
        pygame.draw.rect(s, (35, 38, 48), (E(x0), E(21), E(6.8), E(7)), border_radius=E(2.4))
        for k in range(3):
            yy = 21.8 + ((k * 2.2 + fase * 1.6) % 6.4)
            pygame.draw.line(s, (96, 102, 118), (E(x0 + 0.8), E(yy)), (E(x0 + 6), E(yy)), E(0.9))
    pygame.draw.rect(s, osc, (E(6.4), E(12.6), E(17.2), E(11)), border_radius=E(2.6))   # cuerpo
    pygame.draw.rect(s, met, (E(7.2), E(13.2), E(15.6), E(9.6)), border_radius=E(2.2))
    pygame.draw.circle(s, acc if fase % 2 == 0 else mezcla(acc, 0.55), (E(15), E(18)), E(2.2))
    for sg in (-1, 1):
        pygame.draw.circle(s, osc, (E(15 + sg * 10.4), E(17.6)), E(2.5))
        pygame.draw.circle(s, met, (E(15 + sg * 10.4), E(17.6)), E(1.8))
    pygame.draw.rect(s, osc, (E(7.4), E(3.6), E(15.2), E(10)), border_radius=E(3))      # cabeza
    pygame.draw.rect(s, cla, (E(8.2), E(4.3), E(13.6), E(8.6)), border_radius=E(2.6))
    pygame.draw.rect(s, (15, 18, 30), (E(9.4), E(6.4), E(11.2), E(4.6)), border_radius=E(2))
    if d != "arriba":
        px = 15 + dx * 3.2
        pygame.draw.rect(s, acc, (E(px - 2.2), E(7.1), E(4.4), E(3.2)), border_radius=E(1.4))
    pygame.draw.line(s, osc, (E(15), E(3.6)), (E(15), E(1.7)), E(1.1))
    pygame.draw.circle(s, acc if fase % 2 == 0 else mezcla(acc, 0.5), (E(15), E(1.5)), E(1.3))


def f_rana(s, e, pal, fase, d):
    E = _E(e)
    piel, osc, cla, acc = pal
    dx, dy = DIRS[d]
    salto = (0, -3, -5, -3)[fase % 4]                                            # salta al moverse
    for sg in (-1, 1):                                                            # patas traseras
        pygame.draw.ellipse(s, osc, (E(15 + sg * 9 - 3), E(20 + salto * 0.3), E(7), E(5)))
        pygame.draw.ellipse(s, piel, (E(15 + sg * 9 - 2.3), E(20.4 + salto * 0.3), E(5.6), E(3.6)))
    pygame.draw.ellipse(s, osc, (E(6), E(12 + salto), E(18), E(13)))              # cuerpo
    pygame.draw.ellipse(s, piel, (E(6.8), E(12.6 + salto), E(16.4), E(11.4)))
    pygame.draw.ellipse(s, cla, (E(9), E(18 + salto), E(12), E(6)))               # panza
    for sg in (-1, 1):                                                            # patas delanteras
        pygame.draw.ellipse(s, osc, (E(15 + sg * 7.4 - 2.4), E(19 + salto), E(4.8), E(4.4)))
        pygame.draw.ellipse(s, piel, (E(15 + sg * 7.4 - 1.9), E(19.3 + salto), E(3.8), E(3.2)))
    for sg in (-1, 1):                                                            # ojos saltones arriba
        cx = 15 + sg * 5.4
        pygame.draw.circle(s, osc, (E(cx), E(7 + salto)), E(4.6))
        pygame.draw.circle(s, cla, (E(cx), E(7 + salto)), E(3.7))
        pygame.draw.circle(s, (20, 60, 20), (E(cx + dx * 1.4), E(7 + salto + dy * 1.2)), E(2.1))
        pygame.draw.circle(s, (255, 255, 255), (E(cx + dx * 0.6 - 0.6), E(6 + salto + dy * 0.5)), E(0.8))
    for x, y in ((10, 15), (19, 13), (13, 20), (18, 19)):                        # manchas
        pygame.draw.circle(s, acc, (E(x), E(y + salto)), E(1.1))
    if d != "arriba":
        oy = 1 if d == "abajo" else 0
        pygame.draw.arc(s, (30, 60, 20), (E(11), E(13.5 + salto + oy), E(8), E(4)), 3.6, 5.8, E(1.2))


def f_murcielago(s, e, pal, fase, d):
    E = _E(e)
    cue, osc, cla, acc = pal
    dx, dy = DIRS[d]
    bate = (0, 8, 14, 8)[fase % 4]                                               # aleteo
    for sg in (-1, 1):                                                            # alas
        base = (15 + sg * 4, 15)
        punta = (15 + sg * 13, 15 - bate * 0.6)
        medio = (15 + sg * 9, 11 - bate * 0.3)
        pygame.draw.polygon(s, osc, [base, medio, punta, (15 + sg * 7, 20)])
        pygame.draw.polygon(s, cue, [base, (15 + sg * 6, 13 - bate * 0.2), (15 + sg * 10.4, 16.4 - bate * 0.4)])
        for k in (0.35, 0.65):
            px = base[0] + (punta[0] - base[0]) * k
            py = base[1] + (punta[1] - base[1]) * k
            pygame.draw.line(s, osc, (E(px), E(py)), (E(15 + sg * 7), E(19)), E(0.9))
    pygame.draw.ellipse(s, osc, (E(10.5), E(11), E(9), E(11)))                    # cuerpo
    pygame.draw.ellipse(s, cue, (E(11.2), E(11.6), E(7.6), E(9.4)))
    for sg in (-1, 1):                                                            # orejas
        pygame.draw.polygon(s, osc, [(E(15 + sg * 2.4), E(9)), (E(15 + sg * 5.6), E(9.4)), (E(15 + sg * 3.4), E(3))])
        pygame.draw.polygon(s, cla, [(E(15 + sg * 2.8), E(8.2)), (E(15 + sg * 4.6), E(8.4)), (E(15 + sg * 3.4), E(4.6))])
    ox, oy = dx * 1.2, dy * 1.0
    for ex in (12.6, 17.4):
        pygame.draw.circle(s, (230, 40, 60), (E(ex + ox), E(13.6 + oy)), E(1.6))
    pygame.draw.polygon(s, acc, [(E(13.4 + ox), E(16.4 + oy)), (E(16.6 + ox), E(16.4 + oy)), (E(15 + ox), E(18.4 + oy))])
    for fx in (13.6, 16.4):
        pygame.draw.polygon(s, (255, 255, 255), [(E(fx + ox - 0.6), E(16.4 + oy)), (E(fx + ox + 0.6), E(16.4 + oy)),
                                                 (E(fx + ox), E(18 + oy))])


def f_aguila(s, e, pal, fase, d):
    E = _E(e)
    plu, osc, cla, pico = pal
    dx, dy = DIRS[d]
    bate = (0, -6, -9, -6)[fase % 4]                                             # aleteo (alas arriba/abajo)
    for sg in (-1, 1):                                                            # alas
        pygame.draw.polygon(s, osc, [(E(15 + sg * 3), E(15)), (E(15 + sg * 13), E(15 + bate * 0.5)),
                                    (E(15 + sg * 9), E(21 - bate * 0.2)), (E(15 + sg * 2), E(19))])
        pygame.draw.polygon(s, plu, [(E(15 + sg * 3.6), E(15.6)), (E(15 + sg * 10.4), E(15.6 + bate * 0.45)),
                                    (E(15 + sg * 7.4), E(20 - bate * 0.15))])
        for k in range(3):
            px = 15 + sg * (5 + k * 2.6)
            py = 16 + bate * 0.4 * (k + 1) / 3
            pygame.draw.line(s, cla, (E(px), E(py)), (E(px + sg * 2), E(py + 3)), E(0.8))
    pygame.draw.ellipse(s, osc, (E(10.8), E(11), E(8.4), E(12)))                  # cuerpo
    pygame.draw.ellipse(s, plu, (E(11.4), E(11.6), E(7.2), E(10.2)))
    pygame.draw.ellipse(s, cla, (E(12.4), E(17), E(5.2), E(5)))                   # pecho claro
    pygame.draw.circle(s, cla, (E(15), E(9)), E(4.4))                             # cabeza
    ox, oy = dx * 1.6, dy * 1.1
    pygame.draw.polygon(s, pico, [(E(15 + ox * 1.6), E(9 + oy * 1.2)), (E(15 + ox * 3.6), E(9.6 + oy * 1.6)),
                                 (E(15 + ox * 1.6), E(10.2 + oy * 1.2))])
    for ex in (13.2, 16.8):
        pygame.draw.circle(s, (30, 20, 10), (E(ex + ox * 0.4), E(7.6 + oy * 0.4)), E(1.1))
    for sg, ph in ((-1, 0), (1, 1)):                                              # garras
        off = 1.2 if (fase + ph) % 2 == 0 else 0
        pygame.draw.line(s, (230, 190, 60), (E(15 + sg * 2.4), E(22 - off)), (E(15 + sg * 3.4), E(25 - off)), E(1.3))


def f_alien(s, e, pal, fase, d):
    E = _E(e)
    cue, osc, cla, acc = pal
    dx, dy = DIRS[d]
    ondula = (0, 1.4, 0, -1.4)[fase % 4]
    for sg in (-1, 1):                                                            # tentaculos
        for k in range(2):
            base = (15 + sg * (5 + k * 3.4), 21)
            punta = (base[0] + sg * 2 + ondula, base[1] + 7 + k * 1.4)
            medio = (base[0] + sg * 3, base[1] + 3.6)
            pygame.draw.lines(s, osc, False, [base, medio, punta], E(2.4))
            pygame.draw.circle(s, acc, (E(punta[0]), E(punta[1])), E(1.3))
    pygame.draw.circle(s, osc, (E(15), E(15)), E(11))                             # cuerpo gelatinoso
    pygame.draw.circle(s, cue, (E(15), E(15)), E(9.8))
    pygame.draw.circle(s, cla, (E(12), E(11.6)), E(4.2))                          # brillo interno
    ox, oy = dx * 1.6, dy * 1.4
    pygame.draw.circle(s, (10, 10, 20), (E(15 + ox), E(14 + oy)), E(4.4))         # ojo central grande
    pygame.draw.circle(s, acc, (E(15 + ox), E(14 + oy)), E(3.2))
    pygame.draw.circle(s, (255, 255, 255), (E(15 + ox - 1), E(14 + oy - 1)), E(1.1))
    for k in range(6):                                                            # aro de luz
        a = fase * 0.6 + k * math.pi / 3
        pygame.draw.circle(s, acc, (E(15 + math.cos(a) * 10.4), E(15 + math.sin(a) * 10.4)), E(0.8))


# ------------------------------------------------------
# Esqueleto para el mundo Cripta (enemigos y jefe)
# ------------------------------------------------------
# Paletas del esqueleto: (hueso, oscuro, claro, ojos)
# orden: 0 perseguidor A, 1 emboscador, 2 perseguidor B, 3 cazador
PALETAS_ESQUELETO = [
    ((232, 226, 204), (110, 102, 84), (255, 252, 236), (255, 70, 70)),
    ((178, 190, 170), (76, 88, 72), (226, 236, 216), (110, 255, 140)),
    ((214, 196, 150), (112, 92, 56), (246, 234, 196), (90, 200, 255)),
    ((150, 150, 168), (60, 60, 78), (206, 206, 222), (255, 170, 40)),
]


def f_esqueleto(s, e, pal, fase, d):
    E = _E(e)
    hueso, osc, cla, ojo = pal
    dx, dy = DIRS[d]
    for sg, ph in ((-1, 0), (1, 1)):                                              # piernas
        off = 1.8 if (fase + ph) % 2 == 0 else 0
        x = 15 + sg * 3
        pygame.draw.line(s, osc, (E(x), E(20.5)), (E(x), E(26 - off)), E(3))
        pygame.draw.line(s, hueso, (E(x), E(20.5)), (E(x), E(26 - off)), E(1.8))
        pygame.draw.ellipse(s, osc, (E(x - 2.6 + sg * 0.6), E(25.2 - off), E(5.2), E(3.2)))
        pygame.draw.ellipse(s, hueso, (E(x - 1.9 + sg * 0.6), E(25.6 - off), E(3.8), E(2)))
    pygame.draw.ellipse(s, osc, (E(10.5), E(19), E(9), E(4.2)))                   # pelvis
    pygame.draw.ellipse(s, hueso, (E(11.3), E(19.5), E(7.4), E(2.8)))
    pygame.draw.rect(s, osc, (E(9.6), E(12.4), E(10.8), E(8.2)), border_radius=E(3))   # torso
    pygame.draw.rect(s, (26, 24, 36), (E(10.6), E(13.2), E(8.8), E(6.4)), border_radius=E(2.4))
    for yy in (14.2, 16.4, 18.6):                                                 # costillas
        pygame.draw.line(s, hueso, (E(10.8), E(yy)), (E(19.2), E(yy)), E(1.2))
    pygame.draw.line(s, hueso, (E(15), E(12.6)), (E(15), E(19.6)), E(1.5))        # columna
    for sg, ph in ((-1, 1), (1, 0)):                                              # brazos
        oy = 1.8 if (fase + ph) % 2 == 0 else 0
        hombro = (E(15 + sg * 5.4), E(13.8))
        mano = (E(15 + sg * 8.8), E(19.6 + oy))
        pygame.draw.line(s, osc, hombro, mano, E(2.8))
        pygame.draw.line(s, hueso, hombro, mano, E(1.6))
        pygame.draw.circle(s, osc, mano, E(2))
        pygame.draw.circle(s, hueso, mano, E(1.4))
    pygame.draw.circle(s, osc, (E(15), E(7.6)), E(7.4))                           # craneo
    pygame.draw.circle(s, hueso, (E(15), E(7.6)), E(6.6))
    if d == "arriba":
        pygame.draw.ellipse(s, cla, (E(11), E(3), E(8), E(4)))
        return
    ox, oy = dx * 1.3, dy * 0.8
    pygame.draw.ellipse(s, cla, (E(10.6 + ox), E(2.4 + oy), E(5), E(2.6)))
    pygame.draw.rect(s, osc, (E(11.2 + ox), E(11.8 + oy), E(7.6), E(3.4)), border_radius=E(1.2))   # mandibula
    pygame.draw.rect(s, hueso, (E(11.9 + ox), E(12.2 + oy), E(6.2), E(2.6)), border_radius=E(1))
    for x in (13.2, 15, 16.8):                                                    # dientes
        pygame.draw.line(s, osc, (E(x + ox), E(12.2 + oy)), (E(x + ox), E(14.6 + oy)), E(0.7))
    for ex in (11.8, 18.2):                                                       # ojos
        pygame.draw.ellipse(s, (20, 18, 28), (E(ex - 2.3 + ox), E(5.4 + oy), E(4.6), E(4.4)))
        pygame.draw.circle(s, ojo, (E(ex + dx * 0.7 + ox), E(7.6 + dy * 0.5 + oy)), E(1.2))
    pygame.draw.polygon(s, (40, 36, 48), [(E(14.2 + ox), E(9.6 + oy)), (E(15.8 + ox), E(9.6 + oy)),
                                          (E(15 + ox), E(11.2 + oy))])            # nariz


DIBUJOS = {1: f_lobo, 2: f_escorpion, 3: f_diablillo, 4: f_yeti, 5: f_robot,
           6: f_rana, 7: f_murcielago, 8: f_aguila, 9: f_alien}


# ======================================================
# Criaturas "acechador" para los mundos 6-9 (Pantano, Cueva, Cielo, Abismo).
# Sustituyen visualmente al enemigo de tipo "emboscador" en esos mundos: mismo
# comportamiento (se anticipan a tu camino), aspecto distinto.
# ======================================================
def f_sapo_toxico(s, e, pal, fase, d):
    """Pantano: sapo venenoso, hincha las mejillas y suelta burbujas de veneno."""
    E = _E(e)
    piel, osc, cla, acc = pal
    dx, dy = DIRS[d]
    salto = (0, -2, -4, -2)[fase % 4]
    for sg in (-1, 1):
        pygame.draw.ellipse(s, osc, (E(15 + sg * 8 - 3), E(21 + salto * 0.3), E(6), E(5)))
    pygame.draw.ellipse(s, osc, (E(6.5), E(11 + salto), E(17), E(13)))
    pygame.draw.ellipse(s, piel, (E(7.3), E(11.6 + salto), E(15.4), E(11.4)))
    infla = (0, 1.4, 2.2, 1.4)[fase % 4]                                      # mejillas hinchadas
    for sg in (-1, 1):
        pygame.draw.circle(s, acc, (E(15 + sg * 7.4), E(15 + salto)), E(3.4 + infla))
    for sg in (-1, 1):
        cx = 15 + sg * 4.6
        pygame.draw.circle(s, osc, (E(cx), E(6.4 + salto)), E(3.8))
        pygame.draw.circle(s, (200, 255, 80), (E(cx), E(6.4 + salto)), E(3.0))
        ox, oy = dx * 1.1, dy * 1.0
        pygame.draw.circle(s, (20, 40, 10), (E(cx + ox), E(6.4 + salto + oy)), E(1.5))
    if infla > 1.6:                                                           # burbuja venenosa
        pygame.draw.circle(s, mezcla(acc, 1.3), (E(15), E(22 + salto)), E(2.2))


def f_arana_cueva(s, e, pal, fase, d):
    """Cueva: arana que trepa por las paredes con ocho patas articuladas."""
    E = _E(e)
    cue, osc, cla, acc = pal
    dx, dy = DIRS[d]
    mov = 1.6 if fase % 2 == 0 else -1.2
    for i, ang in enumerate((-60, -30, 30, 60)):
        a = math.radians(ang)
        for sg in (-1, 1):
            base = (15 + sg * 4, 15)
            off = mov if (i + fase) % 2 == 0 else -mov * 0.6
            codo = (15 + sg * (9 + off * 0.3), 15 + math.sin(a) * 7)
            punta = (15 + sg * (15 + off), 15 + math.sin(a) * 13)
            pygame.draw.lines(s, osc, False, [base, codo, punta], E(1.6))
    pygame.draw.circle(s, osc, (E(15), E(17)), E(8.6))                        # abdomen
    pygame.draw.circle(s, cue, (E(15), E(17)), E(7.4))
    for x, y in ((12, 15), (18, 14), (15, 20)):
        pygame.draw.circle(s, acc, (E(x), E(y)), E(1.3))
    pygame.draw.circle(s, osc, (E(15), E(9)), E(5.4))                         # cabeza
    pygame.draw.circle(s, cue, (E(15), E(9)), E(4.6))
    ox, oy = dx * 1.2, dy * 1.0
    for ex, ey in ((12.4, 7.6), (17.6, 7.6), (13.4, 10.4), (16.6, 10.4)):
        pygame.draw.circle(s, (230, 40, 60), (E(ex + ox * 0.6), E(ey + oy * 0.6)), E(1.1))


def f_nube_tormenta(s, e, pal, fase, d):
    """Cielo: nube viva que chispea electricidad y flota sin patas."""
    E = _E(e)
    nube, osc, cla, rayo = pal
    dx, dy = DIRS[d]
    flota = math.sin(fase * math.pi / 2) * 2
    for cx, cy, r in ((10, 16, 6.4), (18, 15, 7.2), (14, 12, 6.8), (21, 17.5, 5)):
        pygame.draw.circle(s, osc, (E(cx), E(cy + flota)), E(r + 0.8))
    for cx, cy, r in ((10, 16, 6.4), (18, 15, 7.2), (14, 12, 6.8), (21, 17.5, 5)):
        pygame.draw.circle(s, nube, (E(cx), E(cy + flota)), E(r))
    pygame.draw.circle(s, cla, (E(12), E(11 + flota)), E(3.2))
    ox, oy = dx * 1.4, dy * 1.2
    for ex in (11.6, 18.4):
        pygame.draw.ellipse(s, (30, 20, 40), (E(ex - 2 + ox), E(15 + flota + oy), E(4), E(3.4)))
    if fase % 2 == 0:                                                          # rayo animado
        pts = [(15, 20 + flota), (12.6, 25 + flota), (15.4, 25 + flota), (13.4, 30 + flota)]
        pygame.draw.lines(s, rayo, False, [(E(x), E(y)) for x, y in pts], E(1.6))


def f_ojo_abismal(s, e, pal, fase, d):
    """Abismo: ojo flotante rodeado de tentaculos cortos que pulsa luz."""
    E = _E(e)
    cue, osc, cla, acc = pal
    dx, dy = DIRS[d]
    pulso = (0, 1, 2, 1)[fase % 4]
    for k in range(7):
        a = k * math.tau / 7 + fase * 0.5
        base = (15 + math.cos(a) * 9, 15 + math.sin(a) * 9)
        punta = (15 + math.cos(a) * (13 + pulso), 15 + math.sin(a) * (13 + pulso))
        pygame.draw.line(s, osc, (E(base[0]), E(base[1])), (E(punta[0]), E(punta[1])), E(1.8))
        pygame.draw.circle(s, acc, (E(punta[0]), E(punta[1])), E(1.1))
    pygame.draw.circle(s, osc, (E(15), E(15)), E(9.4 + pulso * 0.2))
    pygame.draw.circle(s, cue, (E(15), E(15)), E(8.2 + pulso * 0.2))
    ox, oy = dx * 1.6, dy * 1.6
    pygame.draw.circle(s, (250, 250, 255), (E(15 + ox), E(15 + oy)), E(5.2))
    pygame.draw.circle(s, acc, (E(15 + ox), E(15 + oy)), E(3.0))
    pygame.draw.circle(s, (10, 10, 20), (E(15 + ox), E(15 + oy)), E(1.4))


DIBUJOS_ALT = {6: f_sapo_toxico, 7: f_arana_cueva, 8: f_nube_tormenta, 9: f_ojo_abismal}


def _corona(s, e, cx=18):
    E = _E(e)
    pts = [(cx - 5.5, 6), (cx - 5.5, 1.8), (cx - 2.8, 3.9), (cx, 0.8), (cx + 2.8, 3.9), (cx + 5.5, 1.8), (cx + 5.5, 6)]
    pygame.draw.polygon(s, (150, 96, 10), [(E(x), E(y)) for x, y in pts])
    pts2 = [(cx - 4.6, 5.3), (cx - 4.6, 3.1), (cx - 2.5, 4.6), (cx, 2.1), (cx + 2.5, 4.6), (cx + 4.6, 3.1), (cx + 4.6, 5.3)]
    pygame.draw.polygon(s, (255, 212, 64), [(E(x), E(y)) for x, y in pts2])
    pygame.draw.circle(s, (230, 40, 70), (E(cx), E(4.4)), E(0.9))


def crear_sprite_jefe(fn, pal, fase, d, salida=60):
    """El enemigo del mundo, grande y con corona."""
    e = 4
    grande = pygame.Surface((36 * e, 36 * e), pygame.SRCALPHA)
    sub = grande.subsurface(pygame.Rect(3 * e, 5 * e, 30 * e, 30 * e))
    fn(sub, e, pal, fase, d)
    _corona(grande, e)
    return pygame.transform.smoothscale(grande, (salida, salida))


# ======================================================
# Iconos de poderes (28x28)
# ======================================================
def f_i_planta(s, e):
    E = _E(e)
    _badge(s, e, (90, 200, 90))
    pygame.draw.line(s, (50, 150, 60), (E(14), E(24)), (E(14), E(17)), E(2))
    pygame.draw.ellipse(s, (60, 170, 70), (E(6.5), E(20), E(7), E(3.4)))
    pygame.draw.ellipse(s, (60, 170, 70), (E(14.5), E(20), E(7), E(3.4)))
    pygame.draw.ellipse(s, (120, 14, 34), (E(7), E(11.5), E(14), E(7.5)))
    pygame.draw.ellipse(s, (210, 42, 66), (E(7), E(5.5), E(14), E(8)))
    for x in (9.5, 12.6, 15.7):
        pygame.draw.polygon(s, (255, 255, 255), [(E(x), E(12.6)), (E(x + 2), E(12.6)), (E(x + 1), E(15))])
    pygame.draw.circle(s, (255, 190, 200), (E(11), E(8.2)), E(1))
    pygame.draw.circle(s, (255, 190, 200), (E(16.5), E(7.8)), E(0.9))


def f_i_cactus(s, e):
    E = _E(e)
    _badge(s, e, (120, 200, 90))
    verde, osc = (70, 180, 90), (36, 110, 56)
    pygame.draw.rect(s, osc, (E(11), E(6.5), E(6), E(16.5)), border_radius=E(3))
    pygame.draw.rect(s, verde, (E(11.7), E(7), E(4.6), E(15.5)), border_radius=E(2.4))
    for sg in (-1, 1):
        x0 = 14 + sg * 5.6
        pygame.draw.rect(s, osc, (E(min(14, x0) - 0.5), E(14), E(5.6), E(3.6)), border_radius=E(1.8))
        pygame.draw.rect(s, osc, (E(x0 - 1.8), E(9.6), E(3.6), E(7.6)), border_radius=E(1.8))
        pygame.draw.rect(s, verde, (E(x0 - 1.1), E(10.2), E(2.2), E(6.6)), border_radius=E(1.1))
    pygame.draw.circle(s, (255, 130, 190), (E(14), E(6.2)), E(2.2))
    pygame.draw.circle(s, (255, 190, 220), (E(18), E(7.4)), E(2.3))
    pygame.draw.circle(s, (255, 230, 120), (E(18), E(7.4)), E(1.1))
    for x, y in ((15, 16), (21, 20), (8, 18)):
        pygame.draw.line(s, (255, 255, 230), (E(x), E(y)), (E(x + 1), E(y - 2)), E(0.8))


def f_i_meteoro(s, e):
    E = _E(e)
    _badge(s, e, (255, 120, 50))
    pygame.draw.polygon(s, (255, 130, 30), [(E(16.5), E(9)), (E(21), E(13.5)), (E(5), E(24)), (E(8), E(20))])
    pygame.draw.polygon(s, (255, 220, 90), [(E(16), E(11)), (E(19), E(13.5)), (E(9), E(21))])
    pygame.draw.circle(s, (90, 60, 50), (E(17.6), E(11.4)), E(5.2))
    pygame.draw.circle(s, (140, 96, 70), (E(17.2), E(11)), E(4.2))
    pygame.draw.circle(s, (70, 46, 40), (E(18.4), E(12.4)), E(1.3))


def f_i_avalancha(s, e):
    E = _E(e)
    _badge(s, e, (170, 220, 255))
    pygame.draw.circle(s, (150, 190, 230), (E(15.5), E(14)), E(8.6))
    pygame.draw.circle(s, (245, 250, 255), (E(14.8), E(13.4)), E(7.8))
    pygame.draw.circle(s, (200, 224, 246), (E(17), E(16)), E(3.6))
    pygame.draw.circle(s, (255, 255, 255), (E(12), E(11)), E(2))
    for y in (10, 14, 18):
        pygame.draw.line(s, (190, 225, 255), (E(2.6), E(y)), (E(6.4), E(y)), E(1))


def f_i_mina(s, e):
    E = _E(e)
    _badge(s, e, (255, 90, 210))
    for k in range(8):
        a = k * math.pi / 4
        pygame.draw.line(s, (120, 130, 150), (E(14 + math.cos(a) * 6.8), E(14.6 + math.sin(a) * 6.8)),
                         (E(14 + math.cos(a) * 9.6), E(14.6 + math.sin(a) * 9.6)), E(1.2))
    pygame.draw.circle(s, (70, 74, 92), (E(14), E(14.6)), E(7))
    pygame.draw.circle(s, (34, 36, 50), (E(14), E(14.6)), E(5.8))
    pygame.draw.circle(s, (80, 235, 255), (E(14), E(14.6)), E(2.6))
    pygame.draw.circle(s, (255, 255, 255), (E(13.4), E(14)), E(0.9))


def f_i_enredadera(s, e):
    E = _E(e)
    _badge(s, e, (90, 200, 90))
    pts = [(7, 22), (9, 16), (14, 13), (19, 15), (20, 10), (16, 6)]
    pygame.draw.lines(s, (40, 130, 50), False, [(E(x), E(y)) for x, y in pts], E(2.2))
    pygame.draw.lines(s, (90, 200, 90), False, [(E(x), E(y)) for x, y in pts], E(1.2))
    for x, y, w, h in ((6, 17, 5, 3), (17, 16, 5, 3), (17.5, 6.5, 5, 3), (10, 11, 5, 3)):
        pygame.draw.ellipse(s, (120, 220, 100), (E(x), E(y), E(w), E(h)))
    pygame.draw.circle(s, (250, 120, 160), (E(16), E(6)), E(1.6))


def f_i_arena(s, e):
    E = _E(e)
    _badge(s, e, (240, 200, 110))
    pygame.draw.ellipse(s, (150, 104, 44), (E(4.5), E(11), E(19), E(10)))
    pygame.draw.ellipse(s, (206, 160, 82), (E(6.5), E(12.2), E(15), E(7.4)))
    pygame.draw.ellipse(s, (150, 104, 44), (E(9), E(14), E(10), E(4.2)))
    pygame.draw.ellipse(s, (70, 44, 20), (E(11.4), E(15.2), E(5.2), E(2)))
    pygame.draw.circle(s, (255, 230, 150), (E(19), E(8)), E(1.1))
    pygame.draw.circle(s, (255, 230, 150), (E(9), E(8.6)), E(0.8))


def f_i_obsidiana(s, e):
    E = _E(e)
    _badge(s, e, (255, 110, 70))
    pts = [(14, 5), (21, 9), (22, 17), (16, 23), (8, 20), (6, 11)]
    pygame.draw.polygon(s, (28, 26, 36), [(E(x), E(y)) for x, y in pts])
    pygame.draw.polygon(s, (70, 66, 90), [(E(14), E(5)), (E(21), E(9)), (E(15), E(13))])
    pygame.draw.polygon(s, (50, 48, 66), [(E(6), E(11)), (E(14), E(5)), (E(15), E(13)), (E(8), E(20))])
    pygame.draw.lines(s, (255, 90, 50), False, [(E(15), E(13)), (E(13), E(17)), (E(16), E(20)), (E(15.6), E(22.6))], E(1.2))


def f_i_ventisca(s, e):
    E = _E(e)
    _badge(s, e, (170, 225, 255))
    for k, col in enumerate(((235, 246, 255), (160, 205, 240), (110, 170, 225))):
        r = 8 - k * 2.4
        pygame.draw.arc(s, col, pygame.Rect(E(14 - r), E(14 - r), E(r * 2), E(r * 2)), 0.6 + k * 1.3, 4.6 + k * 1.3, E(1.5))
    for x, y in ((7, 7), (21, 20), (20, 7), (8, 21)):
        pygame.draw.circle(s, (255, 255, 255), (E(x), E(y)), E(1.1))


def f_i_corto(s, e):
    E = _E(e)
    _badge(s, e, (255, 220, 60))
    pts = [(9, 5), (16, 12), (11, 14), (19, 23)]
    pygame.draw.lines(s, (255, 235, 90), False, [(E(x), E(y)) for x, y in pts], E(2.6))
    pygame.draw.lines(s, (255, 255, 220), False, [(E(x), E(y)) for x, y in pts], E(1.1))
    for x, y in ((20, 9), (7, 18), (21, 16)):
        pygame.draw.circle(s, (90, 235, 255), (E(x), E(y)), E(1.4))


def f_i_espinas(s, e):
    E = _E(e)
    _badge(s, e, (150, 230, 90))
    pygame.draw.ellipse(s, (40, 120, 50), (E(6), E(15), E(16), E(8)))
    pygame.draw.ellipse(s, (90, 200, 90), (E(7), E(15.6), E(14), E(6.4)))
    for x in (9, 12.6, 16.2, 19.6):
        pygame.draw.polygon(s, (60, 160, 60), [(E(x), E(16)), (E(x + 1.6), E(16)), (E(x + 0.8), E(9))])
    pygame.draw.circle(s, (255, 140, 190), (E(20), E(9)), E(2.4))
    pygame.draw.circle(s, (255, 190, 220), (E(20), E(9)), E(1.4))


def f_i_lodo(s, e):
    E = _E(e)
    _badge(s, e, (150, 120, 60))
    pygame.draw.ellipse(s, (70, 54, 24), (E(5), E(11), E(18), E(11)))
    pygame.draw.ellipse(s, (110, 86, 40), (E(6.5), E(12.4), E(15), E(8)))
    for x, y in ((10, 15), (16, 13), (20, 17)):
        pygame.draw.circle(s, (70, 54, 24), (E(x), E(y)), E(1.6))
    pygame.draw.arc(s, (140, 112, 56), (E(8), E(13), E(12), E(6)), 3.6, 5.8, E(1.2))


def f_i_estalactita(s, e):
    E = _E(e)
    _badge(s, e, (170, 150, 200))
    pygame.draw.polygon(s, (90, 76, 110), [(E(11), E(4)), (E(17), E(4)), (E(14), E(20))])
    pygame.draw.polygon(s, (150, 132, 180), [(E(12), E(5)), (E(16), E(5)), (E(14), E(15))])
    pygame.draw.circle(s, (230, 220, 245), (E(14), E(21)), E(1.6))


def f_i_cristal(s, e):
    E = _E(e)
    _badge(s, e, (190, 150, 255))
    pts = [(14, 4), (20, 12), (16, 24), (12, 24), (8, 12)]
    pygame.draw.polygon(s, (110, 80, 160), [(E(x), E(y)) for x, y in pts])
    pygame.draw.polygon(s, (190, 150, 255), [(E(14), E(6)), (E(18), E(12)), (E(14), E(20)), (E(10), E(12))])
    pygame.draw.line(s, (240, 220, 255), (E(14), E(6)), (E(14), E(20)), E(1))


def f_i_tornado(s, e):
    E = _E(e)
    _badge(s, e, (200, 220, 255))
    for k, r in enumerate((9, 6.4, 3.6)):
        y = 8 + k * 6
        pygame.draw.arc(s, (220, 236, 255), (E(14 - r), E(y - r * 0.5), E(r * 2), E(r)), 0.3, 5.9, E(1.6))
    pygame.draw.circle(s, (255, 255, 255), (E(14), E(22)), E(1.2))


def f_i_tormenta(s, e):
    E = _E(e)
    _badge(s, e, (140, 170, 230))
    pygame.draw.ellipse(s, (110, 130, 170), (E(6), E(6), E(16), E(9)))
    pygame.draw.ellipse(s, (150, 175, 215), (E(7), E(6.8), E(14), E(7.4)))
    pts = [(15.4, 13), (11.6, 19), (14.4, 19), (12.4, 25), (18, 17.4), (14.6, 17.4)]
    pygame.draw.polygon(s, (255, 225, 70), [(E(x), E(y)) for x, y in pts])


def f_i_agujero(s, e):
    E = _E(e)
    _badge(s, e, (150, 90, 220))
    for r, col in ((10, (30, 10, 50)), (7.4, (70, 30, 110)), (4.4, (10, 6, 20))):
        pygame.draw.circle(s, col, (E(14), E(14)), E(r))
    for k in range(3):
        a = k * 2.1
        pygame.draw.arc(s, (190, 130, 255), (E(14 - 10 + k), E(14 - 10 + k), E(20 - k * 2), E(20 - k * 2)),
                        a, a + 1.6, E(1.1))


def f_i_estatica(s, e):
    E = _E(e)
    _badge(s, e, (120, 255, 220))
    pts = [(9, 6), (15, 12), (10, 14), (19, 22)]
    pygame.draw.lines(s, (130, 255, 225), False, [(E(x), E(y)) for x, y in pts], E(2.4))
    for x, y in ((21, 8), (7, 18), (22, 17)):
        pygame.draw.circle(s, (255, 255, 255), (E(x), E(y)), E(1.2))


ICONOS_BOMBA = {1: f_i_planta, 2: f_i_cactus, 3: f_i_meteoro, 4: f_i_avalancha, 5: f_i_mina,
                6: f_i_espinas, 7: f_i_estalactita, 8: f_i_tornado, 9: f_i_agujero}
ICONOS_HIELO = {1: f_i_enredadera, 2: f_i_arena, 3: f_i_obsidiana, 4: f_i_ventisca, 5: f_i_corto,
                6: f_i_lodo, 7: f_i_cristal, 8: f_i_tormenta, 9: f_i_estatica}


# ======================================================
# Trampas y efectos
# ======================================================
def f_planta(s, e, frame):
    """Planta carnivora 44x44. frame: 0 boca abierta, 1 medio, 2 cerrada (masticando)."""
    E = _E(e)
    verde, vosc = (56, 160, 66), (28, 96, 40)
    for x in (3, 25):                                                              # hojas
        pygame.draw.ellipse(s, vosc, (E(x), E(31), E(16), E(8)))
        pygame.draw.ellipse(s, verde, (E(x + 1), E(31.7), E(14), E(6)))
    pygame.draw.rect(s, vosc, (E(19.4), E(22), E(5.2), E(17)), border_radius=E(2))
    pygame.draw.rect(s, verde, (E(20.2), E(22), E(3.6), E(17)), border_radius=E(1.6))
    ab = (10, 5, 0.5)[frame]
    pygame.draw.ellipse(s, (60, 6, 20), (E(9), E(13 - ab * 0.2), E(26), E(9 + ab * 0.9)))   # interior
    pygame.draw.ellipse(s, (120, 14, 34), (E(7), E(16 + ab * 0.5), E(30), E(15)))            # mandibula
    pygame.draw.ellipse(s, (196, 34, 60), (E(8), E(16.8 + ab * 0.5), E(28), E(12.4)))
    for x in (12, 17, 22, 27):
        pygame.draw.polygon(s, (255, 255, 255), [(E(x), E(17.6 + ab * 0.5)), (E(x + 3), E(17.6 + ab * 0.5)),
                                                 (E(x + 1.5), E(14 + ab * 0.5))])
    pygame.draw.ellipse(s, (120, 14, 34), (E(7), E(3 - ab * 0.5), E(30), E(17)))            # mandibula superior
    pygame.draw.ellipse(s, (226, 44, 72), (E(8), E(3.8 - ab * 0.5), E(28), E(14.4)))
    for x, y in ((14, 8), (22, 6.6), (29, 9.6)):
        pygame.draw.circle(s, (255, 196, 205), (E(x), E(y - ab * 0.5)), E(1.6))
    for x in (12, 17, 22, 27):
        pygame.draw.polygon(s, (255, 255, 255), [(E(x), E(16 - ab * 0.5)), (E(x + 3), E(16 - ab * 0.5)),
                                                 (E(x + 1.5), E(19.6 - ab * 0.5))])


def f_cactus(s, e):
    """Cactus torreta 36x40."""
    E = _E(e)
    verde, osc = (74, 186, 96), (34, 104, 54)
    pygame.draw.ellipse(s, (0, 0, 0, 70), (E(7), E(33), E(22), E(5)))
    pygame.draw.rect(s, osc, (E(12.6), E(8), E(10.8), E(28)), border_radius=E(5))
    pygame.draw.rect(s, verde, (E(13.6), E(8.6), E(8.8), E(26.8)), border_radius=E(4))
    for sg in (-1, 1):
        cx = 18 + sg * 9.4
        pygame.draw.rect(s, osc, (E(min(18, cx) - 1), E(20), E(10.6), E(6)), border_radius=E(3))
        pygame.draw.rect(s, osc, (E(cx - 3.2), E(12), E(6.4), E(13)), border_radius=E(3))
        pygame.draw.rect(s, verde, (E(cx - 2.2), E(12.6), E(4.4), E(11.6)), border_radius=E(2))
    pygame.draw.line(s, (50, 140, 70), (E(18), E(10)), (E(18), E(34)), E(1))
    pygame.draw.circle(s, (255, 130, 190), (E(18), E(7.4)), E(3.6))
    pygame.draw.circle(s, (255, 190, 220), (E(18), E(7.4)), E(2.3))
    pygame.draw.circle(s, (255, 230, 120), (E(18), E(7.4)), E(1.1))
    for x, y in ((15, 16), (21, 20), (15.5, 26), (20.6, 29), (8, 18), (28, 18)):
        pygame.draw.line(s, (255, 255, 230), (E(x), E(y)), (E(x + 1), E(y - 2)), E(0.8))


def f_bola_nieve(s, e):
    """Bola de nieve gigante 44x44."""
    E = _E(e)
    pygame.draw.circle(s, (120, 165, 215), (E(22), E(22)), E(21))
    pygame.draw.circle(s, (238, 246, 255), (E(21), E(21)), E(19.6))
    pygame.draw.circle(s, (196, 220, 244), (E(27), E(27)), E(11))
    pygame.draw.circle(s, (238, 246, 255), (E(25), E(25)), E(9.4))
    for x, y, r in ((12, 12, 3.4), (28, 10, 2.6), (10, 27, 2.4), (30, 31, 2)):
        pygame.draw.circle(s, (170, 200, 235), (E(x), E(y)), E(r))
    pygame.draw.ellipse(s, (255, 255, 255), (E(9), E(7), E(11), E(6)))


def f_meteoro(s, e):
    """Meteorito 40x40."""
    E = _E(e)
    pygame.draw.circle(s, (255, 120, 20), (E(20), E(20)), E(15))
    pygame.draw.circle(s, (255, 190, 60), (E(20), E(20)), E(12))
    pygame.draw.circle(s, (80, 54, 48), (E(20), E(20)), E(9.6))
    pygame.draw.circle(s, (130, 92, 70), (E(19), E(19)), E(8))
    for x, y, r in ((16, 16, 2), (23, 22, 2.6), (18, 24, 1.4)):
        pygame.draw.circle(s, (70, 46, 40), (E(x), E(y)), E(r))


# ======================================================
# Iconos sueltos: estrella y trofeo
# ======================================================
def f_estrella_simple(s, e):
    E = _E(e)
    for r1, r2, col in ((13, 5.6, (200, 140, 20)), (11, 4.6, (255, 208, 50)), (6.8, 2.8, (255, 244, 160))):
        pts = []
        for i in range(10):
            r = r1 if i % 2 == 0 else r2
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((E(14 + r * math.cos(a)), E(15 + r * math.sin(a))))
        pygame.draw.polygon(s, col, pts)


def f_trofeo(s, e, activo=True):
    E = _E(e)
    oro = (255, 208, 60) if activo else (110, 112, 130)
    osc = (170, 110, 20) if activo else (66, 68, 82)
    for sg in (-1, 1):
        pygame.draw.arc(s, osc, pygame.Rect(E(14 + sg * 8 - 4), E(5), E(8), E(9)),
                        math.pi / 2 if sg > 0 else -math.pi / 2, -math.pi / 2 if sg > 0 else math.pi / 2, E(1.8))
    pygame.draw.polygon(s, osc, [(E(6.4), E(4)), (E(21.6), E(4)), (E(18.4), E(15.6)), (E(9.6), E(15.6))])
    pygame.draw.polygon(s, oro, [(E(7.6), E(4.8)), (E(20.4), E(4.8)), (E(17.6), E(14.6)), (E(10.4), E(14.6))])
    pygame.draw.rect(s, osc, (E(12.6), E(15), E(2.8), E(5)))
    pygame.draw.rect(s, oro, (E(8.6), E(20), E(10.8), E(3.4)), border_radius=E(1.2))
    pygame.draw.rect(s, osc, (E(6.8), E(23), E(14.4), E(2.8)), border_radius=E(1))
    if activo:
        pygame.draw.ellipse(s, (255, 244, 170), (E(9.6), E(6), E(3), E(5)))


# ======================================================
# Skins del jugador (lienzo 28x28)
# ======================================================
OJOS_SKIN = {"abajo": ((9, 17), (19, 17)), "arriba": ((9, 12), (19, 12)),
             "izquierda": ((8, 15), (14, 15)), "derecha": ((14, 15), (20, 15))}


def _accesorio(s, e, acc, d, skin=None):
    E = _E(e)
    if acc is None:
        return
    dx, dy = DIRS[d]
    ojos = OJOS_SKIN[d]
    if acc == "gafas" or acc == "visor":
        y = {"abajo": 17, "arriba": 12, "izquierda": 15, "derecha": 15}[d]
        col = (25, 28, 40) if acc == "gafas" else (18, 22, 36)
        pygame.draw.rect(s, col, (E(4.6), E(y - 3.2), E(18.8), E(6.4)), border_radius=E(2.6))
        if d in ("abajo", "arriba"):
            for x in (9, 19):
                pygame.draw.rect(s, (60, 66, 86) if acc == "gafas" else (70, 235, 255),
                                 (E(x - 3.6), E(y - 2.2), E(7.2), E(4.4)), border_radius=E(2))
                pygame.draw.circle(s, (255, 255, 255), (E(x - 1.6), E(y - 0.8)), E(0.8))
        else:
            pygame.draw.rect(s, (70, 235, 255) if acc == "visor" else (60, 66, 86),
                             (E(6.2 if d == "izquierda" else 12), E(y - 2.2), E(9.8), E(4.4)), border_radius=E(2))
        if acc == "visor":
            pygame.draw.line(s, (60, 64, 80), (E(14), E(5.4)), (E(14), E(1.6)), E(1.1))
            pygame.draw.circle(s, (255, 80, 130), (E(14), E(1.4)), E(1.5))
    elif acc == "mago":
        pygame.draw.polygon(s, (60, 30, 110), [(E(8.6), E(8)), (E(19.4), E(8)), (E(15.6), E(0.4))])
        pygame.draw.polygon(s, (110, 60, 190), [(E(9.6), E(7.6)), (E(18.4), E(7.6)), (E(15.4), E(1.6))])
        pygame.draw.ellipse(s, (60, 30, 110), (E(4.4), E(6.2), E(19.2), E(4.2)))
        pygame.draw.ellipse(s, (90, 46, 160), (E(5.2), E(6.6), E(17.6), E(3.2)))
        pygame.draw.circle(s, (255, 226, 80), (E(14.6), E(4.6)), E(1.3))
    elif acc == "corona":
        _corona(s, e, 14)
        pygame.draw.rect(s, (255, 212, 64), (E(8.5), E(4.6), E(11), E(2.4)))
    elif acc == "gato" or acc == "orejas_lobo":
        col = (90, 96, 116) if acc == "orejas_lobo" else (170, 108, 50)
        alto = 0.4 if acc == "orejas_lobo" else 1.6
        for sg in (-1, 1):
            cx = 14 + sg * 8.4
            pygame.draw.polygon(s, col, [(E(cx - 3.6), E(9)), (E(cx + 3.6), E(9)), (E(cx - sg * 0.6), E(alto))])
            pygame.draw.polygon(s, (255, 170, 190) if acc == "gato" else (200, 204, 220),
                                [(E(cx - 1.8), E(8.4)), (E(cx + 1.8), E(8.4)), (E(cx - sg * 0.4), E(alto + 3))])
        if acc == "gato" and d != "arriba":
            for sg in (-1, 1):
                for dy2 in (-1.2, 1.2):
                    pygame.draw.line(s, (60, 40, 30), (E(14 + sg * 9), E(20.5 + dy2)), (E(14 + sg * 13.4), E(20.5 + dy2 * 2.4)), E(0.7))
    elif acc == "antena":
        pygame.draw.line(s, (60, 64, 80), (E(14), E(5.6)), (E(14), E(1.8)), E(1.2))
        pygame.draw.circle(s, (255, 80, 80), (E(14), E(1.6)), E(1.7))
        pygame.draw.circle(s, (255, 190, 190), (E(13.5), E(1.2)), E(0.6))
    elif acc == "aguijon":
        for cx, cy, r in ((22.6, 9, 2.4), (24, 5.6, 2.2), (21, 2.8, 2.0)):
            pygame.draw.circle(s, (130, 84, 30), (E(cx), E(cy)), E(r + 0.6))
            pygame.draw.circle(s, (226, 170, 82), (E(cx), E(cy)), E(r))
        pygame.draw.polygon(s, (230, 60, 50), [(E(17.4), E(2.2)), (E(19.6), E(3.8)), (E(17.6), E(5))])
    elif acc == "cuernos":
        for sg in (-1, 1):
            pygame.draw.polygon(s, (70, 30, 30), [(E(14 + sg * 3.6), E(7)), (E(14 + sg * 8), E(9)), (E(14 + sg * 9), E(0.8))])
            pygame.draw.polygon(s, (240, 110, 80), [(E(14 + sg * 4.6), E(7)), (E(14 + sg * 7.4), E(8.4)), (E(14 + sg * 8.4), E(2.4))])
    elif acc == "gorro":
        pygame.draw.ellipse(s, (60, 110, 200), (E(4.4), E(1.4), E(19.2), E(12)))
        pygame.draw.rect(s, (200, 226, 250), (E(4.4), E(7.6), E(19.2), E(3.4)), border_radius=E(1.6))
        pygame.draw.circle(s, (255, 255, 255), (E(14), E(1.6)), E(2))
    elif acc == "calavera":
        ojos_c = {"abajo": ((9, 17), (19, 17)), "arriba": ((9, 12), (19, 12)),
                  "izquierda": ((8, 15), (14, 15)), "derecha": ((14, 15), (20, 15))}[d]
        for ex, ey in ojos_c:                                 # cuencas oscuras con brillo rojo
            pygame.draw.circle(s, (24, 20, 30), (E(ex), E(ey)), E(4.1))
            pygame.draw.circle(s, (255, 70, 70), (E(ex + dx * 1.2), E(ey + dy * 1.2)), E(1.3))
        if d != "arriba":                                     # dientes
            mx = 14 + dx * 3.2
            my = 22.2 if d == "abajo" else 21.4
            pygame.draw.rect(s, (24, 20, 30), (E(mx - 5), E(my - 1.6), E(10), E(3.4)), border_radius=E(1))
            for k in range(5):
                pygame.draw.line(s, (255, 252, 236), (E(mx - 4 + k * 2), E(my - 1.4)),
                                 (E(mx - 4 + k * 2), E(my + 1.6)), E(0.9))
        else:                                                 # grieta en el craneo
            pygame.draw.lines(s, (110, 102, 84), False, [(E(15), E(7.6)), (E(13.6), E(10.4)), (E(15.6), E(12.4))], E(0.9))
    elif acc == "cinta":
        pygame.draw.rect(s, (220, 40, 50), (E(2.8), E(8.4), E(22.4), E(3.4)))
        pygame.draw.polygon(s, (220, 40, 50), [(E(3), E(9)), (E(-1.4), E(6.4)), (E(-0.6), E(11.4))])
        pygame.draw.circle(s, (255, 226, 80), (E(14), E(10)), E(1))
    elif acc == "pirata":
        pygame.draw.polygon(s, (24, 24, 32), [(E(2.6), E(9.6)), (E(25.4), E(9.6)), (E(20.6), E(1.8)), (E(7.4), E(1.8))])
        pygame.draw.polygon(s, (70, 70, 90), [(E(4.8), E(8.6)), (E(23.2), E(8.6)), (E(19.6), E(2.8)), (E(8.4), E(2.8))], E(0.7))
        pygame.draw.circle(s, (245, 245, 250), (E(14), E(5.4)), E(1.5))
        pygame.draw.line(s, (245, 245, 250), (E(11.4), E(7.4)), (E(16.6), E(4.2)), E(0.7))
        pygame.draw.line(s, (245, 245, 250), (E(11.4), E(4.2)), (E(16.6), E(7.4)), E(0.7))
        if d != "arriba":  # parche en un ojo
            px, py = ojos[1]
            pygame.draw.line(s, (24, 24, 32), (E(3), E(py - 5)), (E(25), E(py - 3)), E(0.9))
            pygame.draw.circle(s, (24, 24, 32), (E(px), E(py)), E(4.3))
    elif acc == "vaquero":
        pygame.draw.ellipse(s, (110, 66, 30), (E(0.6), E(6), E(26.8), E(5.4)))
        pygame.draw.ellipse(s, (166, 106, 54), (E(1.6), E(6.4), E(24.8), E(4)))
        pygame.draw.rect(s, (110, 66, 30), (E(7.6), E(0.8), E(12.8), E(8)), border_radius=E(3))
        pygame.draw.rect(s, (166, 106, 54), (E(8.4), E(1.4), E(11.2), E(6.6)), border_radius=E(2.6))
        pygame.draw.rect(s, (90, 46, 24), (E(8.4), E(5.6), E(11.2), E(1.8)))
        pygame.draw.circle(s, (255, 214, 70), (E(14), E(6.5)), E(0.9))
    elif acc == "chef":
        for cx, cy, r in ((8.4, 6, 3.6), (14, 4.4, 4.2), (19.6, 6, 3.6)):
            pygame.draw.circle(s, (176, 182, 200), (E(cx), E(cy)), E(r + 0.7))
        pygame.draw.rect(s, (176, 182, 200), (E(7.6), E(6.4), E(12.8), E(4.4)), border_radius=E(1))
        for cx, cy, r in ((8.4, 6, 3.6), (14, 4.4, 4.2), (19.6, 6, 3.6)):
            pygame.draw.circle(s, (255, 255, 255), (E(cx), E(cy)), E(r))
        pygame.draw.rect(s, (255, 255, 255), (E(8.3), E(6.4), E(11.4), E(3.8)), border_radius=E(1))
    elif acc == "astronauta":
        pygame.draw.circle(s, (150, 175, 210), (E(14), E(14.6)), E(12.8), E(1.8))
        pygame.draw.circle(s, (232, 244, 255), (E(14), E(14.6)), E(12.2), E(0.9))
        pygame.draw.arc(s, (255, 255, 255), pygame.Rect(E(4.6), E(5.6), E(12), E(12)), 1.6, 2.9, E(1.4))
        pygame.draw.rect(s, (255, 90, 90), (E(11), E(25.6), E(6), E(1.6)), border_radius=E(0.8))
    elif acc == "conejo":
        for sg in (-1, 1):
            cx = 14 + sg * 5
            pygame.draw.ellipse(s, skin["oscuro"], (E(cx - 2.9), E(0.2), E(5.8), E(11.6)))
            pygame.draw.ellipse(s, skin["cuerpo"], (E(cx - 2.3), E(0.7), E(4.6), E(10.4)))
            pygame.draw.ellipse(s, (255, 170, 190), (E(cx - 1.2), E(2.6), E(2.4), E(6.6)))
        if d != "arriba":
            pygame.draw.circle(s, (255, 130, 160), (E(14 + dx * 3.6), E(20.6 if d == "abajo" else 19.6)), E(1.3))
    elif acc == "oso":
        for sg in (-1, 1):
            cx = 14 + sg * 8.6
            pygame.draw.circle(s, skin["oscuro"], (E(cx), E(6.4)), E(4.2))
            pygame.draw.circle(s, skin["cuerpo"], (E(cx), E(6.4)), E(3.5))
            pygame.draw.circle(s, skin["medio"], (E(cx), E(6.8)), E(1.8))
        if d != "arriba":
            sx, sy = 14 + dx * 3.6, (21.4 if d == "abajo" else 20.4)
            pygame.draw.ellipse(s, (240, 220, 180), (E(sx - 4.4), E(sy - 3), E(8.8), E(6)))
            pygame.draw.ellipse(s, (50, 34, 28), (E(sx - 1.6), E(sy - 2.4), E(3.2), E(2.2)))
    elif acc == "angel":
        for sg in (-1, 1):
            x0 = 14 + sg * 12.6
            pygame.draw.ellipse(s, (170, 190, 220), (E(x0 - 3.4), E(10), E(6.8), E(11)))
            pygame.draw.ellipse(s, (255, 255, 255), (E(x0 - 2.6), E(10.8), E(5.2), E(9.2)))
        pygame.draw.ellipse(s, (255, 224, 90), (E(7.6), E(0.8), E(12.8), E(4.4)), E(1.3))
    elif acc == "flor":
        for k in range(5):
            a = k * math.tau / 5 - math.pi / 2
            pygame.draw.circle(s, (255, 140, 190), (E(14 + math.cos(a) * 3.2), E(5.4 + math.sin(a) * 3.2)), E(2.2))
        pygame.draw.circle(s, (255, 226, 90), (E(14), E(5.4)), E(1.8))
    elif acc == "vampiro":
        pygame.draw.polygon(s, (26, 20, 34), [(E(3.2), E(11.4)), (E(4.6), E(5.6)), (E(14), E(3.2)), (E(23.4), E(5.6)),
                                              (E(24.8), E(11.4)), (E(14), E(7.8))])
        if d != "arriba":
            mx, my = 14 + dx * 3.2, (22 if d == "abajo" else 21)
            pygame.draw.line(s, (40, 20, 30), (E(mx - 3.6), E(my)), (E(mx + 3.6), E(my)), E(0.9))
            for fx in (-2.4, 1.0):
                pygame.draw.polygon(s, (255, 255, 255), [(E(mx + fx), E(my)), (E(mx + fx + 1.4), E(my)),
                                                         (E(mx + fx + 0.7), E(my + 2.8))])
    elif acc == "unicornio":
        for sg in (-1, 1):
            cx = 14 + sg * 7.6
            pygame.draw.polygon(s, (255, 190, 220), [(E(cx - 2.4), E(8)), (E(cx + 2.4), E(8)), (E(cx), E(2.8))])
        for cx, cy, r, col in ((4.6, 9, 2.4, (255, 120, 170)), (3.6, 12.6, 2.2, (150, 130, 255)),
                               (3.8, 16, 2, (110, 220, 255))):
            pygame.draw.circle(s, col, (E(cx), E(cy)), E(r))
        pygame.draw.polygon(s, (200, 150, 30), [(E(11.4), E(8)), (E(16.6), E(8)), (E(14), E(0.2))])
        pygame.draw.polygon(s, (255, 236, 130), [(E(12.2), E(7.6)), (E(15.8), E(7.6)), (E(14), E(1.4))])
        for y, w in ((6.2, 3.4), (4.4, 2.4), (2.8, 1.4)):
            pygame.draw.line(s, (220, 160, 50), (E(14 - w / 2), E(y + 0.5)), (E(14 + w / 2), E(y - 0.5)), E(0.6))
    elif acc == "dino":
        for i, x in enumerate((6.4, 10.4, 14, 17.6, 21.6)):
            h = (4.6, 7, 7.8, 7, 4.6)[i]
            pygame.draw.polygon(s, (170, 120, 40), [(E(x - 2.5), E(8.6)), (E(x + 2.5), E(8.6)), (E(x), E(8.6 - h))])
            pygame.draw.polygon(s, (252, 236, 150), [(E(x - 1.4), E(8.2)), (E(x + 1.4), E(8.2)), (E(x), E(8.6 - h + 1.6))])
        if d != "arriba":  # dientecitos
            mx, my = 14 + dx * 3.2, (22 if d == "abajo" else 21)
            for fx in (-2.6, 0.2, 2.6 - 0.4):
                pygame.draw.polygon(s, (255, 255, 255), [(E(mx + fx), E(my)), (E(mx + fx + 1.2), E(my)), (E(mx + fx + 0.6), E(my + 1.8))])
    elif acc == "vikingo":
        for sg in (-1, 1):
            pygame.draw.polygon(s, (240, 232, 205), [(E(14 + sg * 8), E(9)), (E(14 + sg * 13), E(7.2)),
                                                     (E(14 + sg * 13.4), E(0.8)), (E(14 + sg * 11), E(4.8)),
                                                     (E(14 + sg * 8), E(5.8))])
        pygame.draw.ellipse(s, (84, 90, 108), (E(4), E(2.2), E(20), E(11.4)))
        pygame.draw.ellipse(s, (160, 168, 190), (E(4.8), E(2.8), E(18.4), E(9.6)))
        pygame.draw.rect(s, (110, 76, 46), (E(4.6), E(8), E(18.8), E(2.4)))
        for x in (7, 14, 21):
            pygame.draw.circle(s, (255, 226, 120), (E(x), E(9.2)), E(0.8))
        if d != "arriba":
            pygame.draw.rect(s, (130, 138, 160), (E(13), E(10.4), E(2), E(4.2)))
    elif acc == "fuego":
        pts = [(7.6, 9), (7.4, 4.6), (10.4, 6.4), (11.2, 1.4), (14, 5.4), (16.6, 0.6), (17.6, 5.6), (20.4, 3.4), (20.6, 9)]
        pygame.draw.polygon(s, (255, 110, 30), [(E(x), E(y)) for x, y in pts])
        pygame.draw.polygon(s, (255, 224, 80), [(E(10.6), E(9)), (E(11.6), E(5.8)), (E(14), E(7.6)), (E(16.4), E(5)), (E(17.4), E(9))])
    elif acc == "punk":
        for i, x in enumerate((7.8, 10.9, 14, 17.1, 20.2)):
            h = (4, 6.4, 7.8, 6.4, 4)[i]
            col = (255, 70, 170) if i % 2 == 0 else (110, 230, 255)
            pygame.draw.polygon(s, col, [(E(x - 1.9), E(9.4)), (E(x + 1.9), E(9.4)), (E(x), E(9.4 - h - 1))])
    elif acc == "caballero":
        pygame.draw.rect(s, (24, 24, 32), (E(9), E(0.6), E(10), E(7.6)), border_radius=E(1))
        pygame.draw.ellipse(s, (24, 24, 32), (E(4.4), E(6.4), E(19.2), E(3.6)))
        pygame.draw.rect(s, (200, 40, 60), (E(9), E(5.4), E(10), E(1.8)))
        pygame.draw.rect(s, (80, 80, 100), (E(10.2), E(1.4), E(1.6), E(3.6)))
        if d != "arriba":
            mx, my = 14 + dx * 3.2, (21.6 if d == "abajo" else 20.8)
            pygame.draw.ellipse(s, (60, 40, 30), (E(mx - 5.6), E(my - 1.4), E(5.6), E(2.8)))
            pygame.draw.ellipse(s, (60, 40, 30), (E(mx), E(my - 1.4), E(5.6), E(2.8)))
            px, py = ojos[1]
            pygame.draw.circle(s, (255, 214, 70), (E(px), E(py)), E(4.8), E(0.9))
    elif acc == "hongo":
        pygame.draw.ellipse(s, (150, 20, 30), (E(1.4), E(0.6), E(25.2), E(10.6)))
        pygame.draw.ellipse(s, (235, 50, 60), (E(2.2), E(1.2), E(23.6), E(9)))
        for x, y, r in ((7, 5.6, 2.2), (14, 3.4, 2.4), (20.6, 6, 2), (10.6, 8.2, 1.3), (17.4, 8.4, 1.3)):
            pygame.draw.circle(s, (255, 250, 240), (E(x), E(y)), E(r))
    elif acc == "auriculares":
        pygame.draw.arc(s, (40, 42, 56), pygame.Rect(E(3.4), E(1.6), E(21.2), E(19)), 0, math.pi, E(2.2))
        for x in (1.6, 22):
            pygame.draw.rect(s, (30, 32, 44), (E(x), E(9.4), E(4.4), E(8.2)), border_radius=E(1.8))
            pygame.draw.rect(s, (255, 80, 130), (E(x + 0.8 + (0.6 if x < 10 else -0.2)), E(10.6), E(2.2), E(5.8)), border_radius=E(1))
    elif acc == "fiesta":
        pygame.draw.polygon(s, (255, 90, 160), [(E(8.6), E(8.4)), (E(19.4), E(8.4)), (E(14), E(0.8))])
        pygame.draw.polygon(s, (255, 230, 80), [(E(10.6), E(5.6)), (E(17.4), E(5.6)), (E(16), E(3.8)), (E(12), E(3.8))])
        for x, y in ((11.4, 7.2), (16.6, 7.2), (14, 4.8)):
            pygame.draw.circle(s, (110, 230, 255), (E(x), E(y)), E(0.8))
        pygame.draw.circle(s, (110, 230, 255), (E(14), E(1.2)), E(1.5))
    elif acc == "bruja":
        pygame.draw.ellipse(s, (30, 24, 42), (E(3.6), E(6.6), E(20.8), E(4)))
        pygame.draw.polygon(s, (30, 24, 42), [(E(9), E(8.4)), (E(19), E(8.4)), (E(16.4), E(3.2)), (E(21.6), E(1.4)),
                                              (E(13), E(0.6))])
        pygame.draw.rect(s, (255, 130, 40), (E(9.6), E(6.2), E(8.8), E(1.8)))
        pygame.draw.rect(s, (255, 226, 90), (E(12.6), E(5.8), E(2.8), E(2.6)), E(0.6))
    elif acc == "ojos_saltones":
        for cx in (8, 20):
            pygame.draw.circle(s, skin["oscuro"], (E(cx), E(5.6)), E(4.6))
            pygame.draw.circle(s, (250, 250, 240), (E(cx), E(5.6)), E(3.8))
            pygame.draw.circle(s, (20, 40, 20), (E(cx + dx * 1.2), E(5.6 + dy * 1.0)), E(2))
            pygame.draw.circle(s, (255, 255, 255), (E(cx - 0.8), E(4.4)), E(0.8))
    elif acc == "orejas_murcielago":
        for sg in (-1, 1):
            cx = 14 + sg * 6.6
            pygame.draw.polygon(s, skin["oscuro"], [(E(cx - 3.6), E(9)), (E(cx + 3.6), E(9)), (E(cx + sg * 1.4), E(0.2))])
            pygame.draw.polygon(s, (230, 120, 170), [(E(cx - 1.8), E(8.6)), (E(cx + 1.8), E(8.6)), (E(cx + sg * 0.8), E(3))])
        if d != "arriba":
            mx, my = 14 + dx * 3.2, (22 if d == "abajo" else 21)
            for fx in (-2.4, 1.0):
                pygame.draw.polygon(s, (255, 255, 255), [(E(mx + fx), E(my)), (E(mx + fx + 1.4), E(my)),
                                                         (E(mx + fx + 0.7), E(my + 2.8))])
    elif acc == "aguila":
        for i, x in enumerate((10.2, 14, 17.8)):
            h = (5, 7, 5)[i]
            pygame.draw.polygon(s, (120, 84, 44), [(E(x - 2.4), E(8.6)), (E(x + 2.4), E(8.6)), (E(x), E(8.6 - h))])
            pygame.draw.polygon(s, (250, 240, 220), [(E(x - 1.3), E(8.2)), (E(x + 1.3), E(8.2)), (E(x), E(8.6 - h + 1.5))])
        if d != "arriba":
            if dx == 0:
                pts = [(14 - 2.8, 18.6), (14 + 2.8, 18.6), (14, 23.6)]
            else:
                bx = 14 + dx * 3
                pts = [(bx, 17.6), (bx, 21.8), (bx + dx * 5, 19.8)]
            pygame.draw.polygon(s, (190, 130, 20), [(E(x), E(y)) for x, y in pts])
            pygame.draw.polygon(s, (255, 206, 60), [(E(x), E(y)) for x, y in pts], E(0.8))
    elif acc == "ciclope":
        ex, ey = (ojos[0][0] + ojos[1][0]) / 2, ojos[0][1]
        pygame.draw.circle(s, skin["oscuro"], (E(ex), E(ey)), E(8.2))
        pygame.draw.circle(s, (250, 250, 255), (E(ex), E(ey)), E(7.4))
        pygame.draw.circle(s, (120, 255, 200), (E(ex + dx * 2), E(ey + dy * 2)), E(4.2))
        pygame.draw.circle(s, (12, 8, 24), (E(ex + dx * 2.4), E(ey + dy * 2.4)), E(2.2))
        pygame.draw.circle(s, (255, 255, 255), (E(ex + dx * 2 - 1.2), E(ey + dy * 2 - 1.4)), E(0.9))
    elif acc == "gorra":
        pygame.draw.ellipse(s, (150, 24, 34), (E(4.6), E(1.6), E(18.8), E(12)))
        pygame.draw.ellipse(s, (226, 48, 62), (E(5.4), E(2.2), E(17.2), E(10)))
        pygame.draw.circle(s, (150, 24, 34), (E(14), E(2.6)), E(1.4))
        if d == "arriba":
            pygame.draw.line(s, (150, 24, 34), (E(14), E(3)), (E(14), E(11)), E(0.8))
        elif dx == 0:
            pygame.draw.ellipse(s, (120, 18, 28), (E(5.6), E(8.4), E(16.8), E(4.8)))
            pygame.draw.ellipse(s, (190, 34, 48), (E(6.4), E(8.4), E(15.2), E(3.6)))
        else:
            pygame.draw.ellipse(s, (120, 18, 28), (E(14 + dx * 5 - 6), E(8.4), E(12), E(4)))
            pygame.draw.ellipse(s, (190, 34, 48), (E(14 + dx * 5 - 5.2), E(8.4), E(10.4), E(3)))


def f_jugador_skin(s, e, direccion, skin):
    E = _E(e)
    cu, osc, med, bri = skin["cuerpo"], skin["oscuro"], skin["medio"], skin["brillo"]
    pygame.draw.rect(s, osc, (E(2), E(5), E(24), E(22)), border_radius=E(10))
    pygame.draw.rect(s, cu, (E(3), E(6), E(22), E(20)), border_radius=E(9))
    pygame.draw.rect(s, med, (E(3), E(18), E(22), E(8)), border_bottom_left_radius=E(9), border_bottom_right_radius=E(9))
    pygame.draw.rect(s, bri, (E(6), E(7.2), E(11), E(4.4)), border_radius=E(2.2))
    ojos = OJOS_SKIN[direccion]
    dx, dy = DIRS[direccion]
    for ex, ey in ojos:
        pygame.draw.circle(s, (250, 250, 250), (E(ex), E(ey)), E(3.7))
        pygame.draw.circle(s, (20, 24, 30), (E(ex + dx * 1.3), E(ey + dy * 1.3)), E(2.1))
    _accesorio(s, e, skin.get("accesorio"), direccion, skin)


# ======================================================
# Audio: musica y efectos sintetizados por codigo (no necesita archivos .mp3/.wav)
# ======================================================
_NOTAS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def _midi(nombre):
    """'c6' -> numero MIDI"""
    return 12 * (int(nombre[-1]) + 1) + _NOTAS[nombre[0]]


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _tono(sr, tipo, f0, f1, dur, duty=0.5, vol=1.0, sost=0.75):
    """Una nota (o un barrido de f0 a f1). tipo: 'c' cuadrada, 't' triangulo, 's' seno."""
    n = max(1, int(dur * sr))
    out = [0.0] * n
    ph = 0.0
    att = max(1, int(0.004 * sr))
    rel = max(1, int(min(0.03, dur * 0.4) * sr))
    exp = math.exp
    for i in range(n):
        ph += (f0 + (f1 - f0) * i / n) / sr
        if ph >= 1.0:
            ph -= 1.0
        if tipo == "c":
            v = 1.0 if ph < duty else -1.0
        elif tipo == "t":
            v = 4.0 * abs(ph - 0.5) - 1.0
        else:
            v = math.sin(6.283185307 * ph)
        env = i / att if i < att else 1.0
        if i > n - rel:
            env *= (n - i) / rel
        env *= sost + (1.0 - sost) * exp(-i / sr * 12.0)
        out[i] = v * env * vol
    return out


_cache_notas = {}


def _nota(sr, tipo, m, dur, duty=0.5, sost=0.75):
    k = (tipo, m, round(dur, 4), duty, sost)
    if k not in _cache_notas:
        _cache_notas[k] = _tono(sr, tipo, _hz(m), _hz(m), dur, duty, 1.0, sost)
    return _cache_notas[k]


def _ruido(sr, rnd, dur, tau, agudo=False):
    n = int(dur * sr)
    out = [0.0] * n
    prev = 0.0
    for i in range(n):
        r = rnd.uniform(-1.0, 1.0)
        out[i] = ((r - prev) if agudo else r) * math.exp(-i / sr * tau)
        prev = r
    return out


def _bombo(sr):
    n = int(0.16 * sr)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / sr
        ph += (45 + 120 * math.exp(-t * 30)) / sr
        out[i] = math.sin(6.283185307 * ph) * math.exp(-t * 14)
    return out


def _caja(sr, rnd):
    ruido = _ruido(sr, rnd, 0.12, 28)
    return [v * 0.8 + math.sin(6.283185307 * 190 * i / sr) * math.exp(-i / sr * 35) * 0.5
            for i, v in enumerate(ruido)]


def _mezclar(buf, nota, ini, gan):
    fin = min(len(buf), ini + len(nota))
    for j in range(ini, fin):
        buf[j] += nota[j - ini] * gan


# Melodia: 16 compases x 8 corcheas. '.' = silencio, '-' = alarga la nota anterior
MELODIA = [
    "e5 g5 c6 g5 e5 g5 c6 -", "c6 a5 e5 a5 c6 e6 c6 -", "a5 c6 f6 c6 a5 c6 a5 f5", "g5 b5 d6 b5 g5 b5 d6 -",
    "e6 . c6 e6 g6 e6 c6 .", "c6 . a5 c6 e6 c6 a5 .", "f6 e6 d6 c6 a5 c6 f5 a5", "g5 a5 b5 d6 g6 - d6 b5",
    "a5 c6 e6 c6 a5 c6 e6 -", "f6 - a5 c6 f6 - c6 a5", "g5 c6 e6 g6 e6 c6 g5 -", "d6 - b5 d6 g6 - d6 b5",
    "e6 d6 c6 b5 a5 b5 c6 e6", "f6 e6 d6 c6 d6 c6 a5 f5", "g5 b5 d6 g6 f6 d6 b5 g5", "c6 e6 g6 c7 g6 e6 c6 -",
]
_C = (48, (64, 67, 72))
_AM = (45, (64, 69, 72))
_F = (41, (65, 69, 72))
_G = (43, (62, 67, 71))
PROGRESION = [_C, _AM, _F, _G, _C, _AM, _F, _G, _AM, _F, _C, _G, _AM, _F, _G, _C]


def _componer_musica(sr):
    rnd = random.Random(7)
    paso = int(0.2 * sr)  # corchea a 150 BPM
    pasos = 16 * 8
    buf = [0.0] * (paso * pasos)
    fichas = [t for compas in MELODIA for t in compas.split()]
    i = 0
    while i < pasos:  # melodia
        f = fichas[i]
        if f in (".", "-"):
            i += 1
            continue
        largo = 1
        while i + largo < pasos and fichas[i + largo] == "-":
            largo += 1
        _mezclar(buf, _nota(sr, "c", _midi(f), largo * 0.2 * 0.92, 0.5, 0.8), i * paso, 0.30)
        i += largo
    bombo, caja, hat = _bombo(sr), _caja(sr, rnd), [v * 1.0 for v in _ruido(sr, rnd, 0.05, 90, True)]
    for c, (raiz, acorde) in enumerate(PROGRESION):
        for s in range(8):
            ini = (c * 8 + s) * paso
            r = raiz + (0, 0, 12, 0, 0, 0, 7, 12)[s]  # bajo saltarin
            _mezclar(buf, _nota(sr, "t", r, 0.17, 0.5, 0.9), ini, 0.42)
            arp = acorde[(0, 1, 2, 1, 0, 1, 2, 1)[s]]  # arpegio brillante
            _mezclar(buf, _nota(sr, "c", arp - 12, 0.12, 0.125, 0.6), ini, 0.16)
            if s in (0, 4):
                _mezclar(buf, bombo, ini, 0.55)
            if s in (2, 6):
                _mezclar(buf, caja, ini, 0.28)
            if s % 2 == 1:
                _mezclar(buf, hat, ini, 0.13)
    return buf


ESCALAS = dict(mayor=(0, 2, 4, 5, 7, 9, 11), menor=(0, 2, 3, 5, 7, 8, 10), pent=(0, 2, 4, 7, 9),
               frigio=(0, 1, 4, 5, 7, 8, 10), menor_arm=(0, 2, 3, 5, 7, 8, 11), dorico=(0, 2, 3, 5, 7, 9, 10),
               lidio=(0, 2, 4, 6, 7, 9, 11), locrio=(0, 1, 3, 5, 6, 8, 10), pentmen=(0, 3, 5, 7, 10))
ACORDES = {"M": (0, 4, 7), "m": (0, 3, 7), "d": (0, 3, 6), "s": (0, 5, 7)}

# Una pista por mundo + jefe, furia y dimension. paso = duracion de una corchea (segundos).
PISTAS = {
    "bosque": dict(semilla=11, raiz=57, escala="pent", paso=0.25, prog=[(0, "M"), (5, "M"), (7, "M"), (5, "M"), (0, "M"), (9, "m"), (5, "M"), (7, "M")],
                   lead=("t", 0.5), bajo=2, arp=0, dens=0.7, bombo=(1, 0, 0, 0, 1, 0, 0, 0), caja=(0, 0, 0, 0, 0, 0, 1, 0), hat=(0, 1, 0, 1, 0, 1, 0, 1), vol_ritmo=0.5),
    "desierto": dict(semilla=22, raiz=50, escala="frigio", paso=0.27, prog=[(0, "m"), (1, "M"), (0, "m"), (10, "M"), (0, "m"), (1, "M"), (8, "M"), (7, "M")],
                     lead=("c", 0.25), bajo=1, arp=1, dens=0.6, bombo=(1, 0, 0, 1, 1, 0, 0, 0), caja=(0, 0, 1, 0, 0, 0, 1, 0), hat=(1, 0, 1, 0, 1, 0, 1, 1), vol_ritmo=0.8),
    "volcan": dict(semilla=33, raiz=45, escala="menor_arm", paso=0.2, prog=[(0, "m"), (0, "m"), (8, "M"), (7, "M"), (0, "m"), (5, "m"), (8, "M"), (7, "M")],
                   lead=("c", 0.5), bajo=1, arp=2, dens=0.8, bombo=(1, 0, 1, 0, 1, 0, 1, 1), caja=(0, 0, 1, 0, 0, 0, 1, 0), hat=(1, 1, 1, 1, 1, 1, 1, 1), vol_ritmo=1.0),
    "glaciar": dict(semilla=44, raiz=60, escala="lidio", paso=0.3, prog=[(0, "M"), (7, "M"), (9, "m"), (5, "M"), (0, "M"), (7, "M"), (4, "m"), (5, "M")],
                    lead=("s", 0.5), bajo=2, arp=0, dens=0.55, bombo=(1, 0, 0, 0, 0, 0, 0, 0), caja=(0, 0, 0, 0, 1, 0, 0, 0), hat=(0, 0, 1, 0, 0, 0, 1, 0), vol_ritmo=0.4),
    "neon": dict(semilla=55, raiz=48, escala="menor", paso=0.18, prog=[(0, "m"), (8, "M"), (3, "M"), (10, "M"), (0, "m"), (8, "M"), (5, "m"), (7, "M")],
                 lead=("c", 0.125), bajo=1, arp=2, dens=0.75, bombo=(1, 0, 0, 0, 1, 0, 0, 0), caja=(0, 0, 1, 0, 0, 0, 1, 0), hat=(1, 1, 1, 1, 1, 1, 1, 1), vol_ritmo=0.9),
    "pantano": dict(semilla=66, raiz=43, escala="dorico", paso=0.33, prog=[(0, "m"), (0, "m"), (5, "M"), (5, "M"), (0, "m"), (10, "M"), (5, "M"), (0, "m")],
                    lead=("t", 0.5), bajo=2, arp=1, dens=0.45, bombo=(1, 0, 0, 0, 0, 0, 1, 0), caja=(0, 0, 0, 0, 1, 0, 0, 0), hat=(0, 0, 0, 1, 0, 0, 0, 1), vol_ritmo=0.5),
    "cueva": dict(semilla=77, raiz=52, escala="pentmen", paso=0.36, prog=[(0, "m"), (3, "M"), (0, "m"), (8, "M"), (0, "m"), (3, "M"), (10, "M"), (0, "m")],
                  lead=("s", 0.5), bajo=2, arp=0, dens=0.35, bombo=(1, 0, 0, 0, 0, 0, 0, 0), caja=(0, 0, 0, 0, 0, 0, 0, 0), hat=(0, 0, 0, 0, 0, 0, 0, 0), vol_ritmo=0.35),
    "cielo": dict(semilla=88, raiz=62, escala="mayor", paso=0.2, prog=[(0, "M"), (7, "M"), (9, "m"), (4, "m"), (5, "M"), (0, "M"), (5, "M"), (7, "M")],
                  lead=("c", 0.5), bajo=0, arp=2, dens=0.85, bombo=(1, 0, 0, 0, 1, 0, 0, 0), caja=(0, 0, 1, 0, 0, 0, 1, 0), hat=(0, 1, 0, 1, 0, 1, 0, 1), vol_ritmo=0.7),
    "abismo": dict(semilla=99, raiz=40, escala="locrio", paso=0.19, prog=[(0, "d"), (1, "M"), (0, "d"), (6, "M"), (0, "d"), (1, "M"), (3, "m"), (6, "M")],
                   lead=("c", 0.25), bajo=1, arp=2, dens=0.7, bombo=(1, 0, 1, 0, 1, 0, 1, 0), caja=(0, 0, 1, 0, 0, 1, 1, 0), hat=(1, 0, 1, 1, 1, 0, 1, 1), vol_ritmo=1.0),
    "jefe": dict(semilla=111, raiz=45, escala="menor_arm", paso=0.17, prog=[(0, "m"), (1, "M"), (0, "m"), (7, "M"), (8, "M"), (7, "M"), (0, "m"), (1, "M")],
                 lead=("c", 0.5), bajo=1, arp=2, dens=0.9, bombo=(1, 0, 1, 1, 1, 0, 1, 0), caja=(0, 0, 1, 0, 0, 0, 1, 1), hat=(1, 1, 1, 1, 1, 1, 1, 1), vol_ritmo=1.1),
    "jefe3": dict(semilla=122, raiz=43, escala="frigio", paso=0.14, prog=[(0, "m"), (1, "M"), (0, "m"), (1, "M"), (6, "M"), (7, "M"), (0, "d"), (1, "M")],
                  lead=("c", 0.25), bajo=1, arp=2, dens=1.0, bombo=(1, 1, 1, 0, 1, 1, 1, 0), caja=(0, 0, 1, 0, 0, 1, 1, 1), hat=(1, 1, 1, 1, 1, 1, 1, 1), vol_ritmo=1.2),
    "furia": dict(semilla=133, raiz=47, escala="menor_arm", paso=0.13, prog=[(0, "m"), (8, "M"), (3, "M"), (7, "M")] * 2,
                  lead=("c", 0.125), bajo=1, arp=2, dens=1.0, bombo=(1, 0, 1, 0, 1, 0, 1, 1), caja=(0, 0, 1, 0, 0, 0, 1, 0), hat=(1, 1, 1, 1, 1, 1, 1, 1), vol_ritmo=1.2),
    "dimension": dict(semilla=144, raiz=38, escala="menor_arm", paso=0.3, prog=[(0, "m"), (0, "m"), (8, "M"), (7, "M"), (0, "m"), (5, "m"), (3, "M"), (7, "M")],
                      lead=("s", 0.5), bajo=2, arp=1, dens=0.5, bombo=(1, 0, 0, 1, 1, 0, 0, 0), caja=(0, 0, 0, 0, 0, 0, 0, 0), hat=(0, 0, 0, 0, 0, 0, 0, 1), vol_ritmo=0.8),
    "historia": dict(semilla=155, raiz=50, escala="menor", paso=0.4, prog=[(0, "m"), (8, "M"), (5, "m"), (7, "M")] * 2,
                     lead=("s", 0.5), bajo=2, arp=0, dens=0.4, bombo=(0, 0, 0, 0, 0, 0, 0, 0), caja=(0, 0, 0, 0, 0, 0, 0, 0), hat=(0, 0, 0, 0, 0, 0, 0, 0), vol_ritmo=0.0),
}
NOMBRE_PISTA_MUNDO = ["menu", "bosque", "desierto", "volcan", "glaciar", "neon", "pantano", "cueva", "cielo", "abismo", "dimension"]


def _componer_pista(sr, p):
    """Sintetiza una pista de 8 compases a partir de sus parametros."""
    rnd = random.Random(p["semilla"])
    paso = int(p["paso"] * sr)
    compases = len(p["prog"])
    pasos = compases * 8
    buf = [0.0] * (paso * pasos)
    esc = ESCALAS[p["escala"]]
    tipo_l, duty_l = p["lead"]
    bombo, caja, hat = _bombo(sr), _caja(sr, rnd), [v for v in _ruido(sr, rnd, 0.05, 90, True)]
    # notas de la escala en el registro de la melodia
    notas_esc = [p["raiz"] + 12 + o + 12 * oc for oc in (0, 1) for o in esc]
    pos = len(esc) // 2
    for c, (off, cal) in enumerate(p["prog"]):
        raiz = p["raiz"] + off
        acorde = [raiz + 12 + x for x in ACORDES[cal]]
        for st in range(8):
            ini = (c * 8 + st) * paso
            if p["bajo"] == 0:
                r = raiz - 12 + (0, 0, 12, 0, 0, 12, 0, 7)[st]
                _mezclar(buf, _nota(sr, "t", r, p["paso"] * 0.9, 0.5, 0.9), ini, 0.4)
            elif p["bajo"] == 1:
                r = raiz - 12 + (0, 0, 12, 0, 0, 0, 7, 12)[st]
                _mezclar(buf, _nota(sr, "t", r, p["paso"] * 0.85, 0.5, 0.9), ini, 0.42)
            elif st in (0, 4):
                _mezclar(buf, _nota(sr, "t", raiz - 12, p["paso"] * 3.6, 0.5, 0.9), ini, 0.42)
            if p["arp"] == 1 and st % 2 == 0:
                _mezclar(buf, _nota(sr, "c", acorde[(st // 2) % 3] - 12, p["paso"] * 1.6, 0.25, 0.6), ini, 0.12)
            elif p["arp"] == 2:
                _mezclar(buf, _nota(sr, "c", acorde[(0, 1, 2, 1, 0, 1, 2, 1)[st]] - 12, p["paso"] * 0.6, 0.125, 0.6), ini, 0.14)
            # melodia
            if rnd.random() < p["dens"] * (1.0 if st % 2 == 0 else 0.7):
                pos += rnd.choice((-2, -1, -1, 0, 1, 1, 2))
                pos = max(0, min(len(notas_esc) - 1, pos))
                n = notas_esc[pos]
                if st in (0, 4):  # tiempo fuerte: nota del acorde
                    n = min(acorde + [a + 12 for a in acorde], key=lambda a: abs(a - n))
                dur = p["paso"] * (1.8 if (st % 2 == 0 and rnd.random() < 0.4) else 0.9)
                _mezclar(buf, _nota(sr, tipo_l, n, dur, duty_l, 0.8), ini, 0.28)
            vr = p["vol_ritmo"]
            if vr > 0:
                if p["bombo"][st]:
                    _mezclar(buf, bombo, ini, 0.55 * vr)
                if p["caja"][st]:
                    _mezclar(buf, caja, ini, 0.26 * vr)
                if p["hat"][st]:
                    _mezclar(buf, hat, ini, 0.11 * vr)
    return buf


def _construir_efectos(sr):
    rnd = random.Random(3)
    fx = {}

    def cat(*partes):
        return [v for p in partes for v in p]

    def notas(lista, tipo="c", duty=0.5, vol=0.8):
        return cat(*[_tono(sr, tipo, _hz(n), _hz(n), d, duty, vol) for n, d in lista])

    for m in range(1, 6):  # recoger fruta: mas agudo con cada combo
        b = 76 + 2 * (m - 1)
        fx[f"fruta{m}"] = (cat(_tono(sr, "c", _hz(b), _hz(b), 0.06, 0.25, 0.8),
                               _tono(sr, "c", _hz(b + 5), _hz(b + 5), 0.11, 0.25, 0.8)), 0.55)
    fx["poder"] = (cat(*[_tono(sr, "c", _hz(n), _hz(n), 0.055, 0.5, 0.8) for n in (72, 76, 79, 84, 88, 91)]), 0.6)
    fx["disparo"] = (_tono(sr, "c", 1300, 300, 0.09, 0.25, 0.8, 0.5), 0.28)
    fx["matar"] = (cat(_tono(sr, "c", 700, 150, 0.16, 0.5, 0.8, 0.5), _tono(sr, "t", 200, 60, 0.1, 0.5, 0.8, 0.5)), 0.5)
    ruido = _ruido(sr, rnd, 0.6, 5)
    grave = _tono(sr, "s", 110, 35, 0.6, 0.5, 1.0, 0.3)
    fx["bomba"] = ([r * 0.7 + g * 0.9 for r, g in zip(ruido, grave)], 0.75)
    fx["golpe"] = (_tono(sr, "c", 620, 70, 0.42, 0.5, 0.9, 0.4), 0.6)
    fx["nivel"] = (cat(*[_tono(sr, "c", _hz(n), _hz(n), d, 0.5, 0.8) for n, d in
                         ((72, .1), (76, .1), (79, .1), (84, .22), (79, .08), (84, .4))]), 0.6)
    fx["victoria"] = (cat(*[_tono(sr, "c", _hz(n), _hz(n), d, 0.5, 0.8) for n, d in
                            ((72, .12), (76, .12), (79, .12), (84, .12), (88, .12), (91, .12),
                             (96, .5), (91, .12), (96, .8))]), 0.65)
    fx["vida"] = (cat(*[_tono(sr, "c", _hz(n), _hz(n), 0.07, 0.25, 0.8) for n in (79, 83, 86, 91)]), 0.6)
    fx["gameover"] = (cat(*[_tono(sr, "t", _hz(n), _hz(n), d, 0.5, 0.9, 0.8) for n, d in
                            ((76, .2), (72, .2), (69, .2), (64, .55))]), 0.65)
    # ---- nuevos en 2.0 ----
    fx["moneda"] = (notas(((88, 0.05), (95, 0.14)), "c", 0.25), 0.5)
    fx["curar"] = (notas(((72, .08), (76, .08), (79, .08), (84, .2)), "s"), 0.6)
    fx["legendaria"] = (notas(((72, .06), (79, .06), (84, .06), (88, .06), (91, .06), (96, .06), (100, .06),
                               (96, .06), (100, .06), (103, .3)), "c", 0.25), 0.65)
    fx["cristal"] = (cat(_tono(sr, "s", 2200, 2200, 0.1, 0.5, 0.8), _tono(sr, "s", 2960, 2960, 0.1, 0.5, 0.8),
                         _tono(sr, "s", 3520, 3520, 0.35, 0.5, 0.8, 0.3)), 0.5)
    fx["dorada"] = (notas(((79, .07), (79, .07), (79, .07), (84, .25), (82, .08), (84, .45)), "c", 0.5), 0.7)
    fx["corazon"] = (cat(_tono(sr, "s", 90, 60, 0.1, 0.5, 1.0), _tono(sr, "s", 90, 60, 0.12, 0.5, 1.0),
                         notas(((76, .1), (83, .3)), "s")), 0.7)
    fx["paralisis"] = (_tono(sr, "c", 900, 80, 0.4, 0.125, 0.8, 0.4), 0.5)
    fx["carga"] = (_tono(sr, "c", 200, 900, 0.5, 0.25, 0.6, 0.9), 0.4)
    fx["disparo_carga"] = (cat(_tono(sr, "c", 1800, 120, 0.25, 0.5, 0.9, 0.5), _tono(sr, "t", 150, 50, 0.2, 0.5, 0.9, 0.5)), 0.6)
    ray = _ruido(sr, rnd, 0.3, 9, True)
    fx["rayo"] = ([r * 0.8 + t for r, t in zip(ray, _tono(sr, "c", 2400, 200, 0.3, 0.125, 0.7, 0.3))], 0.6)
    fx["hielo"] = (cat(_tono(sr, "s", 3000, 2200, 0.08, 0.5, 0.8), _tono(sr, "s", 2200, 1500, 0.2, 0.5, 0.8, 0.3)), 0.45)
    fx["rafaga"] = (cat(*[_tono(sr, "c", 1400 - 120 * i, 400, 0.05, 0.25, 0.8) for i in range(5)]), 0.35)
    fx["especial"] = ([r * 0.6 + g for r, g in zip(_ruido(sr, rnd, 0.5, 6), _tono(sr, "s", 300, 40, 0.5, 0.5, 1.0, 0.3))], 0.7)
    fx["furia_on"] = (cat(_tono(sr, "t", 70, 160, 0.4, 0.5, 1.0, 0.9), notas(((79, .08), (83, .08), (86, .08), (91, .4)), "c", 0.5)), 0.75)
    fx["furia_off"] = (_tono(sr, "t", 300, 60, 0.5, 0.5, 0.9, 0.6), 0.5)
    fx["evento"] = (cat(*[_tono(sr, "c", f, f, 0.12, 0.5, 0.7) for f in (880, 660, 880, 660)]), 0.55)
    ra = _ruido(sr, rnd, 0.9, 3)
    fx["trueno"] = ([r * 0.9 + g * 0.7 for r, g in zip(ra, _tono(sr, "s", 80, 30, 0.9, 0.5, 1.0, 0.3))], 0.8)
    fx["portal"] = (_tono(sr, "s", 300, 1400, 0.3, 0.5, 0.9, 0.6), 0.5)
    fx["secreto"] = (notas(((67, .1), (71, .1), (74, .1), (79, .1), (83, .1), (86, .35)), "t"), 0.75)
    fx["cofre"] = (cat(_tono(sr, "t", 200, 200, 0.08, 0.5, 0.9), notas(((84, .06), (88, .06), (91, .06), (96, .3)), "c", 0.25)), 0.7)
    fx["fase"] = ([r * 0.5 + g for r, g in zip(_ruido(sr, rnd, 0.9, 4), _tono(sr, "s", 160, 30, 0.9, 0.5, 1.0, 0.5))], 0.85)
    fx["alerta"] = (cat(_tono(sr, "c", 500, 500, 0.1, 0.5, 0.8), _tono(sr, "c", 400, 400, 0.1, 0.5, 0.8), _tono(sr, "c", 500, 500, 0.1, 0.5, 0.8)), 0.5)
    fx["cazador"] = (cat(_tono(sr, "s", 160, 90, 0.5, 0.5, 1.0, 0.5), _tono(sr, "c", 120, 60, 0.4, 0.125, 0.6, 0.4)), 0.7)
    fx["logro"] = (notas(((72, .08), (79, .08), (84, .08), (88, .08), (91, .08), (96, .35)), "c", 0.5), 0.7)
    fx["ok"] = (_tono(sr, "c", 880, 1320, 0.07, 0.5, 0.7), 0.4)
    fx["mover"] = (_tono(sr, "c", 700, 700, 0.03, 0.5, 0.6), 0.25)
    fx["error"] = (_tono(sr, "c", 200, 120, 0.18, 0.5, 0.8), 0.45)
    fx["pet"] = (notas(((88, .05), (91, .07)), "t"), 0.4)
    fx["pinchos"] = (_tono(sr, "c", 600, 250, 0.08, 0.125, 0.8), 0.3)
    fx["lava"] = ([r * 0.5 + g for r, g in zip(_ruido(sr, rnd, 0.3, 8), _tono(sr, "s", 120, 60, 0.3, 0.5, 1.0, 0.5))], 0.5)
    return fx


class Audio:
    def __init__(self):
        self.ok = False
        self.sonidos = {}
        self.base = {}
        self.pistas = {}
        self.actual = None
        self.canal = None
        self.ultimo = {}
        self.pausado = False

    # compatibilidad: 'silencio' = la musica esta apagada
    @property
    def silencio(self):
        return not CONFIG["musica_on"]

    def iniciar(self):
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(22050, -16, 1, 512)
            self.freq, formato, self.canales = pygame.mixer.get_init()
            if formato != -16:
                raise RuntimeError("formato de audio no soportado")
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(1)  # canal 0 = musica
            self.canal = pygame.mixer.Channel(0)
            self.pistas["menu"] = self._a_sonido(_componer_musica(self.freq), 0.5)
            for nombre, (buf, vol) in _construir_efectos(self.freq).items():
                self.sonidos[nombre] = self._a_sonido(buf, vol)
                self.base[nombre] = vol
            self.ok = True
        except Exception as ex:  # sin tarjeta de sonido: el juego sigue mudo
            print("Audio desactivado:", ex)
            self.ok = False

    def _a_sonido(self, buf, vol):
        pico = max(1e-6, max(max(buf), -min(buf)))
        k = 0.9 * 32767 / pico
        datos = array("h", [int(v * k) for v in buf])
        if self.canales == 2:
            est = array("h", [0]) * (len(datos) * 2)
            est[0::2] = datos
            est[1::2] = datos
            datos = est
        snd = pygame.mixer.Sound(buffer=datos.tobytes())
        snd.set_volume(vol)
        return snd

    def _pista(self, nombre):
        if nombre not in self.pistas:
            try:
                self.pistas[nombre] = self._a_sonido(_componer_pista(self.freq, PISTAS[nombre]), 0.5)
            except Exception as ex:
                print("No se pudo crear la pista", nombre, ex)
                return self.pistas.get("menu")
        return self.pistas[nombre]

    def _volumen(self):
        if self.ok:
            self.canal.set_volume(CONFIG["vol_musica"] if CONFIG["musica_on"] else 0.0)

    def musica(self, nombre="menu", forzar=False):
        """Reproduce la pista indicada (si ya suena, no la reinicia)."""
        if not self.ok:
            return
        if nombre == self.actual and not forzar and self.canal.get_busy():
            self._volumen()
            return
        snd = self._pista(nombre) if nombre != "menu" else self.pistas["menu"]
        self.actual = nombre
        self.canal.play(snd, loops=-1, fade_ms=250)
        self._volumen()
        if self.pausado:
            self.canal.pause()

    def musica_mundo(self, mundo):
        self.musica(NOMBRE_PISTA_MUNDO[min(mundo, len(NOMBRE_PISTA_MUNDO) - 1)])

    def parar_musica(self):
        if self.ok:
            self.canal.fadeout(400)
            self.actual = None

    def pausar(self, pausa):
        self.pausado = pausa
        if self.ok:
            (self.canal.pause if pausa else self.canal.unpause)()

    def alternar(self):
        """Tecla M: musica ON/OFF."""
        CONFIG["musica_on"] = not CONFIG["musica_on"]
        self._volumen()

    def set_vol_musica(self, v):
        CONFIG["vol_musica"] = max(0.0, min(1.0, v))
        self._volumen()

    def sfx(self, nombre):
        if not self.ok or not CONFIG["efectos_on"] or nombre not in self.sonidos:
            return
        ahora = pygame.time.get_ticks()
        if ahora - self.ultimo.get(nombre, -999) < 60:  # evita apilar el mismo sonido
            return
        self.ultimo[nombre] = ahora
        snd = self.sonidos[nombre]
        snd.set_volume(self.base.get(nombre, 0.6) * CONFIG["vol_efectos"])
        snd.play()


AUDIO = Audio()


def dibujar_indicador_musica(pos):
    if AUDIO.ok:
        texto(pantalla, f"[M] Música: {'OFF' if AUDIO.silencio else 'ON'}", F_PEQ, (230, 230, 245), pos, desp=1)


# ======================================================
# Progreso guardado: estrellas, trofeos, skins y tareas
# ======================================================
def _skin(id_, nombre, precio, cuerpo, oscuro, medio, brillo, accesorio=None, jefe=None, mon=0):
    return dict(id=id_, nombre=nombre, precio=precio, cuerpo=cuerpo, oscuro=oscuro, medio=medio,
                brillo=brillo, accesorio=accesorio, jefe=jefe, mon=mon)


def _skin_auto(id_, nombre, precio, cuerpo, accesorio=None, jefe=None, mon=0):
    """Como _skin, pero calcula oscuro / medio / brillo a partir del color base."""
    brillo = tuple(int(c + (255 - c) * 0.55) for c in cuerpo)
    return _skin(id_, nombre, precio, cuerpo, mezcla(cuerpo, 0.45), mezcla(cuerpo, 0.78), brillo, accesorio, jefe, mon)


SKINS = [
    _skin("verde", "Slime Verde", 0, (66, 205, 100), (28, 110, 52), (46, 165, 78), (130, 240, 160)),
    _skin("azul", "Slime Azul", 20, (70, 150, 235), (30, 70, 150), (50, 110, 200), (150, 200, 255)),
    _skin("rojo", "Slime Rojo", 20, (235, 80, 80), (140, 30, 40), (200, 55, 60), (255, 170, 170)),
    _skin("morado", "Slime Morado", 30, (160, 100, 225), (84, 44, 140), (130, 74, 190), (215, 175, 250)),
    _skin("rosa", "Slime Rosa", 30, (250, 140, 200), (170, 60, 120), (225, 105, 170), (255, 205, 230)),
    _skin("naranja", "Slime Naranja", 30, (250, 160, 50), (160, 86, 14), (225, 125, 30), (255, 215, 150)),
    _skin("dorado", "Slime Dorado", 120, (250, 205, 60), (150, 105, 10), (220, 170, 30), (255, 240, 160)),
    _skin("arcoiris", "Arcoíris", 200, (255, 120, 120), (120, 40, 40), (200, 90, 90), (255, 200, 200)),
    _skin("ninja", "Ninja", 90, (52, 54, 66), (20, 20, 28), (36, 38, 48), (110, 114, 132), "cinta"),
    _skin("genial", "Genial", 50, (66, 205, 100), (28, 110, 52), (46, 165, 78), (130, 240, 160), "gafas"),
    _skin("mago", "Mago", 80, (150, 100, 230), (76, 40, 140), (120, 70, 200), (205, 170, 250), "mago"),
    _skin("rey", "Rey Slime", 120, (66, 205, 100), (28, 110, 52), (46, 165, 78), (130, 240, 160), "corona"),
    _skin("gatito", "Gatito", 60, (250, 190, 120), (160, 100, 40), (225, 150, 70), (255, 225, 180), "gato"),
    _skin("robotito", "Robotito", 70, (150, 158, 176), (60, 64, 80), (110, 118, 138), (210, 218, 235), "antena"),
    # trajes de jefe: se consiguen derrotando al jefe de cada mundo
    _skin("t_esqueleto", "Traje Esqueleto", 0, (232, 226, 204), (110, 102, 84), (190, 182, 160), (255, 252, 236), "calavera", 0),
    _skin("t_lobo", "Traje Lobo", 0, (150, 152, 168), (78, 80, 98), (112, 114, 134), (222, 224, 234), "orejas_lobo", 1),
    _skin("t_escorpion", "Traje Escorpión", 0, (226, 170, 82), (138, 88, 30), (190, 130, 50), (250, 222, 152), "aguijon", 2),
    _skin("t_demonio", "Traje Demonio", 0, (222, 62, 52), (130, 26, 26), (180, 44, 40), (250, 150, 110), "cuernos", 3),
    _skin("t_yeti", "Traje Yeti", 0, (226, 238, 250), (120, 150, 190), (176, 204, 232), (255, 255, 255), "gorro", 4),
    _skin("t_robot", "Traje Robot", 0, (150, 158, 176), (58, 62, 78), (100, 108, 128), (196, 204, 220), "visor", 5),
    # --- trajes de jefe de los mundos 7-10 ---
    _skin_auto("t_rana", "Traje Rana", 0, (90, 176, 86), "ojos_saltones", 6),
    _skin_auto("t_murcielago", "Traje Murciélago", 0, (110, 90, 140), "orejas_murcielago", 7),
    _skin_auto("t_aguila", "Traje Águila", 0, (210, 150, 80), "aguila", 8),
    _skin_auto("t_vacio", "Traje del Vacío", 0, (110, 220, 170), "ciclope", 9),
    # --- colores lisos ---
    _skin_auto("celeste", "Slime Celeste", 20, (90, 210, 235)),
    _skin_auto("amarillo", "Slime Amarillo", 20, (245, 220, 70)),
    _skin_auto("chocolate", "Chocolate", 25, (150, 98, 64)),
    _skin_auto("blanco", "Nube", 30, (240, 242, 250)),
    _skin_auto("negro", "Sombra", 40, (62, 62, 80)),
    _skin_auto("plata", "Slime Plata", 100, (196, 204, 220)),
    # --- con accesorios ---
    _skin_auto("brote", "Flor Silvestre", 40, (150, 220, 120), "flor"),
    _skin_auto("deportista", "Deportista", 40, (90, 140, 235), "gorra"),
    _skin_auto("fiesta", "Fiestero", 50, (250, 215, 80), "fiesta"),
    _skin_auto("hongo", "Hongo", 60, (238, 224, 196), "hongo"),
    _skin_auto("chef", "Chef", 60, (250, 250, 252), "chef"),
    _skin_auto("conejito", "Conejito", 60, (250, 225, 232), "conejo"),
    _skin_auto("osito", "Osito", 60, (172, 118, 76), "oso"),
    _skin_auto("vaquero", "Vaquero", 70, (214, 170, 110), "vaquero"),
    _skin_auto("punk", "Punk", 70, (120, 70, 170), "punk"),
    _skin_auto("dino", "Dino", 80, (110, 190, 70), "dino"),
    _skin_auto("gamer", "Gamer", 80, (58, 64, 96), "auriculares"),
    _skin_auto("pirata", "Pirata", 90, (190, 62, 60), "pirata"),
    _skin_auto("bruja", "Brujita", 90, (120, 200, 90), "bruja"),
    _skin_auto("fueguito", "Fueguito", 90, (250, 130, 60), "fuego"),
    _skin_auto("vampiro", "Vampiro", 100, (216, 206, 226), "vampiro"),
    _skin_auto("vikingo", "Vikingo", 100, (224, 160, 100), "vikingo"),
    _skin_auto("angel", "Ángel", 110, (250, 246, 236), "angel"),
    _skin_auto("caballero", "Caballero", 110, (186, 198, 222), "caballero"),
    _skin_auto("astronauta", "Astronauta", 130, (236, 240, 248), "astronauta"),
    _skin_auto("unicornio", "Unicornio", 150, (252, 232, 244), "unicornio"),
]
# --- skins premium: se compran con Frutacoins ---
SKINS += [
    _skin_auto("galaxia", "Galaxia", 0, (86, 64, 200), "astronauta", mon=250),
    _skin_auto("lava_s", "Slime de Lava", 0, (255, 100, 40), "fuego", mon=180),
    _skin_auto("cristal_s", "Cristal de Hielo", 0, (160, 232, 255), "gorro", mon=180),
    _skin_auto("neon_s", "Neón Rosa", 0, (255, 80, 220), "auriculares", mon=220),
    _skin_auto("esmeralda", "Esmeralda Real", 0, (40, 200, 120), "corona", mon=300),
    _skin_auto("sombra_real", "Sombra Real", 0, (64, 42, 96), "vampiro", mon=280),
    _skin_auto("rey_oro", "Rey Dorado", 0, (255, 212, 60), "corona", mon=500),
    _skin_auto("cazador_s", "Cazador Verde", 0, (60, 130, 74), "vaquero", mon=200),
    _skin_auto("samurai", "Samurái", 0, (200, 60, 70), "caballero", mon=260),
    _skin_auto("corazon_s", "Traje del Corazón", 0, (232, 52, 96), "cuernos", mon=450),
]
SKINS.append(_skin_auto("traje_guardian", "Traje del Guardián", 0, (200, 40, 90), "cuernos", jefe=10))
SKIN_POR_ID = {s["id"]: s for s in SKINS}

# --- efectos del personaje (estela / aura): se compran con Frutacoins ---
EFECTOS = [
    dict(id="fuego", nombre="Estela de fuego", precio=120, color=(255, 140, 40), tipo="estela"),
    dict(id="hielo", nombre="Estela helada", precio=120, color=(150, 225, 255), tipo="estela"),
    dict(id="arcoiris", nombre="Estela arcoíris", precio=220, color=(255, 255, 255), tipo="arcoiris"),
    dict(id="estrellas", nombre="Lluvia de estrellas", precio=160, color=(255, 232, 110), tipo="estrellas"),
    dict(id="corazones", nombre="Corazones", precio=140, color=(255, 100, 150), tipo="corazones"),
    dict(id="rayos", nombre="Chispas eléctricas", precio=180, color=(255, 240, 90), tipo="chispas"),
    dict(id="aura_dorada", nombre="Aura dorada", precio=300, color=(255, 215, 80), tipo="aura"),
    dict(id="aura_sombra", nombre="Aura de sombras", precio=300, color=(150, 80, 220), tipo="aura"),
]
EFECTO_POR_ID = {e["id"]: e for e in EFECTOS}

# --- mejoras permanentes (se compran por niveles con Frutacoins) ---
MEJORAS = [
    dict(id="velocidad", nombre="Velocidad", texto="+5% de velocidad por nivel", precios=[60, 120, 200, 320, 500]),
    dict(id="vida", nombre="Vida máxima", texto="+1 corazón por nivel", precios=[150, 350, 700]),
    dict(id="dano", nombre="Daño", texto="+0,5 de daño por nivel", precios=[100, 220, 400, 650]),
    dict(id="energia", nombre="Energía", texto="+20 de energía máxima por nivel", precios=[50, 100, 170, 260, 400]),
    dict(id="rareza", nombre="Suerte frutal", texto="+25% de frutas raras por nivel", precios=[80, 160, 260, 400, 600]),
]
MEJORA_POR_ID = {m["id"]: m for m in MEJORAS}

# --- mascotas ---
MASCOTAS = [
    dict(id="perro", nombre="Perro", precio=200, texto="Recoge las monedas cercanas", color=(190, 130, 70)),
    dict(id="gato", nombre="Gato", texto="Más probabilidad de objetos raros", precio=250, color=(250, 170, 80)),
    dict(id="dragon", nombre="Dragón", texto="Aumenta tu daño", precio=500, color=(110, 200, 90)),
    dict(id="zorro", nombre="Zorro", texto="Aumenta tu velocidad", precio=350, color=(240, 130, 50)),
]
MASCOTA_POR_ID = {m["id"]: m for m in MASCOTAS}


# ------------------------------------------------------
# TAREAS EN CADENA
# Cada serie es una cadena: al completar un paso aparece el siguiente,
# con una meta mas dificil y mas estrellas de premio.
# tiers: (meta, premio_estrellas [, id_antiguo])
# Los ids antiguos se conservan para no perder el progreso guardado.
# Para anadir tareas: agrega un tier a una serie o una serie nueva.
# ------------------------------------------------------
SERIES = [
    dict(id="fr", stat="frutas", texto="Recoge {n} frutas",
         tiers=[(50, 10, "fr50"), (150, 20), (300, 40, "fr300"), (600, 70), (1000, 120, "fr1000"),
                (2000, 200), (5000, 400)]),
    dict(id="en", stat="enemigos", texto="Elimina {n} enemigos",
         tiers=[(25, 10, "en25"), (75, 20), (150, 50, "en150"), (400, 90), (1000, 200)]),
    dict(id="tr", stat="trampas", texto="Elimina {n} enemigos con trampas",
         tiers=[(10, 25, "tr10"), (30, 40), (75, 70), (200, 120)]),
    dict(id="ni", stat="niveles", texto="Completa {n} niveles",
         tiers=[(5, 10, "ni5"), (15, 40, "ni15"), (30, 100, "ni30"), (50, 150), (100, 300)]),
    dict(id="nm", stat="nivel_max", texto="Llega al nivel {n}",
         tiers=[(10, 30), (20, 60), (30, 90), (40, 150), (50, 250)]),
    dict(id="jf", stat="jefes", texto="Derrota a {n} jefes", texto1="Derrota a tu primer jefe",
         tiers=[(1, 20, "jf1"), (3, 50, "jf3"), (10, 100), (25, 200)]),
    dict(id="jd", stat="jefes_distintos", texto="Derrota a {n} jefes distintos",
         tiers=[(3, 30), (6, 150, "jf6"), (10, 300)]),
    dict(id="cb", stat="combo_max", texto="Logra un combo de {n} frutas",
         tiers=[(5, 15, "cb5"), (10, 30), (20, 60), (40, 120)]),
    dict(id="ca", stat="cadena_max", texto="Come {n} enemigos seguidos con la estrella",
         tiers=[(2, 15), (4, 30), (8, 60)]),
    dict(id="bo", stat="bombas", texto="Usa {n} bombas",
         tiers=[(10, 15, "bo10"), (30, 30), (100, 80)]),
    dict(id="po", stat="poderes", texto="Recoge {n} poderes",
         tiers=[(15, 20, "po15"), (50, 40), (150, 90)]),
    dict(id="pe", stat="poder_estrella", texto="Usa la estrella {n} veces",
         tiers=[(5, 15), (20, 40), (60, 100)]),
    dict(id="ph", stat="poder_hielo", texto="Usa el hielo {n} veces",
         tiers=[(5, 15), (20, 40), (60, 100)]),
    dict(id="pr", stat="poder_rafaga", texto="Usa la ráfaga {n} veces",
         tiers=[(5, 15), (20, 40), (60, 100)]),
    dict(id="pv", stat="poder_rayo", texto="Usa la velocidad {n} veces",
         tiers=[(5, 15), (20, 40), (60, 100)]),
    dict(id="pt", stat="puntos_max", texto="Consigue {n} puntos en una partida",
         tiers=[(5000, 20, "pt5k"), (30000, 80, "pt30k"), (60000, 150), (100000, 300)]),
    dict(id="sd", stat="sin_dano", texto="Pasa {n} niveles sin recibir daño",
         texto1="Pasa un nivel sin recibir daño",
         tiers=[(1, 15, "sd1"), (5, 45, "sd5"), (15, 100), (30, 200)]),
    dict(id="vi", stat="victorias", texto="Termina el juego {n} veces",
         texto1="Termina el juego completo",
         tiers=[(1, 200, "vic"), (3, 300), (10, 600)]),
    dict(id="sc", stat="skins_compradas", texto="Compra {n} skins en la tienda",
         tiers=[(3, 20, "sk3"), (10, 60), (25, 150)]),
    dict(id="st", stat="skins_total", texto="Colecciona {n} skins",
         tiers=[(10, 60, "sk10"), (25, 80, "sk25"), (50, 250, "sk50")]),
    dict(id="eg", stat="estrellas_ganadas", texto="Gana {n} estrellas en total",
         tiers=[(100, 20), (500, 60), (1500, 150)]),
]


SERIES[1]["tiers"].insert(0, (20, 8))   # "Derrota 20 enemigos"
SERIES += [
    dict(id="ma", stat="manzanas", texto="Recoge {n} manzanas",
         tiers=[(50, 15), (150, 35), (400, 80)]),
    dict(id="mo", stat="monedas_total", texto="Consigue {n} Frutacoins",
         tiers=[(100, 15), (500, 40), (2000, 100), (10000, 300)]),
    dict(id="hs", stat="habitaciones", texto="Encuentra {n} habitaciones secretas",
         tiers=[(3, 25), (10, 70), (25, 180)]),
    dict(id="jp", stat="jefes_perfectos", texto="Derrota {n} jefes sin perder vidas", texto1="Derrota un jefe sin perder vidas",
         tiers=[(1, 40), (3, 100), (10, 250)]),
    dict(id="cz", stat="cazador_derrotado", texto="Derrota a El Cazador {n} veces", texto1="Derrota a El Cazador",
         tiers=[(1, 40), (5, 100), (15, 220)]),
    dict(id="ev", stat="eventos", texto="Sobrevive a {n} eventos aleatorios",
         tiers=[(3, 20), (10, 60), (30, 150)]),
    dict(id="fu", stat="furias", texto="Activa el Modo Furia {n} veces", texto1="Activa el Modo Furia",
         tiers=[(1, 20), (10, 60), (30, 150)]),
    dict(id="fl", stat="legendarias", texto="Recoge {n} frutas legendarias", texto1="Recoge una fruta legendaria",
         tiers=[(1, 40), (5, 120)]),
    dict(id="tp", stat="rapidos", texto="Completa {n} niveles bajo el tiempo objetivo",
         tiers=[(3, 25), (10, 70), (30, 180)]),
    dict(id="mm", stat="minimisiones", texto="Completa {n} misiones de nivel",
         tiers=[(5, 20), (20, 60), (60, 160)]),
]


def _construir_tareas():
    out = []
    for s in SERIES:
        for i, tier in enumerate(s["tiers"]):
            meta, premio = tier[0], tier[1]
            id_ = tier[2] if len(tier) > 2 else f"{s['id']}{meta}"
            txt = s["texto1"] if (meta == 1 and "texto1" in s) else s["texto"].format(n=meta)
            out.append(dict(id=id_, texto=txt, stat=s["stat"], meta=meta, premio=premio,
                            serie=s["id"], paso=i + 1, pasos=len(s["tiers"])))
    return out


TAREAS = _construir_tareas()

# nombre, descripcion, estadistica, meta, premio en Frutacoins
LOGROS = [
    dict(id="l_primer", nombre="Primer paso", texto="Completa el nivel 1", stat="nivel_max", meta=1, premio=10),
    dict(id="l_frutas", nombre="Cazador de frutas", texto="Recoge 1.000 frutas", stat="frutas", meta=1000, premio=100),
    dict(id="l_destructor", nombre="Destructor", texto="Derrota 500 enemigos", stat="enemigos", meta=500, premio=120),
    dict(id="l_explorador", nombre="Explorador", texto="Encuentra 20 secretos", stat="secretos", meta=20, premio=150),
    dict(id="l_maestro", nombre="Maestro del laberinto", texto="Completa los 50 niveles", stat="nivel_max", meta=50, premio=300),
    dict(id="l_dim", nombre="Dimensión secreta", texto="Descubre el mundo oculto", stat="dimension", meta=1, premio=200),
    dict(id="l_imparable", nombre="Imparable", texto="Completa un nivel sin recibir daño", stat="sin_dano", meta=1, premio=25),
    dict(id="l_corazon", nombre="Corazón valiente", texto="Derrota al guardián del Corazón", stat="dimension_completa", meta=1, premio=400),
    dict(id="l_cazador", nombre="Cazador cazado", texto="Derrota a El Cazador", stat="cazador_derrotado", meta=1, premio=60),
    dict(id="l_combo", nombre="Maestro del combo", texto="Logra un combo de 20", stat="combo_max", meta=20, premio=80),
    dict(id="l_furia", nombre="Furioso", texto="Activa el Modo Furia 10 veces", stat="furias", meta=10, premio=70),
    dict(id="l_jefe3", nombre="Sin rasguños", texto="Derrota un jefe sin perder vidas", stat="jefes_perfectos", meta=1, premio=100),
    dict(id="l_ricos", nombre="Millonario frutal", texto="Consigue 1.000 Frutacoins", stat="monedas_total", meta=1000, premio=100),
    dict(id="l_coleccion", nombre="Coleccionista", texto="Colecciona 20 skins", stat="skins_total", meta=20, premio=100),
    dict(id="l_domador", nombre="Domador", texto="Compra una mascota", stat="mascotas_total", meta=1, premio=40),
    dict(id="l_legend", nombre="Suerte legendaria", texto="Recoge una fruta legendaria", stat="legendarias", meta=1, premio=60),
    dict(id="l_evento", nombre="Superviviente", texto="Sobrevive a 10 eventos", stat="eventos", meta=10, premio=70),
    dict(id="l_secretojefe", nombre="Cazador de leyendas", texto="Derrota a un guardián secreto", stat="guardianes", meta=1, premio=120),
    dict(id="l_rapido", nombre="Velocista", texto="Termina 10 niveles bajo el tiempo objetivo", stat="rapidos", meta=10, premio=90),
    dict(id="l_portales", nombre="Viajero dimensional", texto="Usa 50 portales", stat="portales", meta=50, premio=60),
    dict(id="l_mejoras", nombre="Siempre mejorando", texto="Compra 10 mejoras", stat="mejoras_total", meta=10, premio=100),
    dict(id="l_historia", nombre="Historiador", texto="Descubre 15 fragmentos de la historia", stat="fragmentos_total", meta=15, premio=150),
]
LOGRO_POR_ID = {l["id"]: l for l in LOGROS}

# ------------------------------------------------------
# Historia: fragmentos que se descubren jugando
# ------------------------------------------------------
HISTORIA = [
    ("intro", "El Jardinero", "Hace mil años, el Jardinero Eterno construyó un laberinto para proteger algo muy frágil: la última semilla de la vida."),
    ("mundo_0", "La Cripta", "Los esqueletos fueron guardianes que no quisieron olvidar. Aún custodian la primera puerta del laberinto."),
    ("mundo_1", "El Bosque", "Las frutas no son comida: son recuerdos del jardín original. Por eso brillan cuando las tocas."),
    ("mundo_2", "El Desierto", "Cada tormenta de arena borra un camino. El Jardinero quería que solo los pacientes llegaran al final."),
    ("mundo_3", "El Volcán", "Los diablillos nacieron del fuego que el Jardinero usó para forjar el laberinto. Protegen su forja."),
    ("mundo_4", "El Glaciar", "El hielo conserva los pasos de quienes entraron antes. Algunos nunca salieron."),
    ("mundo_5", "El Neón", "Los robots fueron construidos para vigilar los portales. Nadie les dijo que el Jardinero ya no volvería."),
    ("mundo_6", "El Pantano", "Aquí el laberinto respira. Lo que se esconde en el lodo ya estaba aquí antes que las paredes."),
    ("mundo_7", "La Cueva", "Los murciélagos ven sin luz porque el Jardinero les quitó el miedo a la oscuridad."),
    ("mundo_8", "El Cielo", "Las águilas guardan el último mundo visible. Más allá solo hay vacío... y algo que late."),
    ("mundo_9", "El Abismo", "El Abismo no es un enemigo: es el laberinto mismo, vivo, intentando recordar para qué fue creado."),
    ("cazador", "El Cazador", "El Cazador fue el aprendiz del Jardinero. Se quedó atrapado y desde entonces aprende cada camino para escapar."),
    ("fin_50", "El Latido", "Completaste los 50 niveles. Bajo el último suelo, algo late. El laberinto tiene un corazón."),
    ("secreto_1", "Nota del aprendiz", "«Hoy el Maestro me dijo que las paredes cambian porque el laberinto sueña.»"),
    ("secreto_2", "Nota del aprendiz", "«Probé todos los caminos. Todos me traen de vuelta aquí. ¿Será que yo soy parte del mapa?»"),
    ("secreto_3", "Diario del Jardinero", "«Plantaré las frutas donde el camino sea más difícil. Que el valor sea recompensado.»"),
    ("secreto_4", "Diario del Jardinero", "«Si alguien llega al Corazón, que sepa que no hay tesoro. El tesoro es el jardín.»"),
    ("secreto_5", "Voz del Abismo", "«Cada vez que mueres, el laberinto te recuerda un poco más. Eso lo hace querer protegerte.»"),
    ("secreto_6", "Carta sin remitente", "«El Cazador no te odia. Te sigue porque eres la primera persona que ve el final.»"),
    ("secreto_7", "Piedra grabada", "«Los guardianes aceptaron ser enemigos para que ningún ladrón llegara al Corazón.»"),
    ("secreto_8", "Última página", "«Quien lea esto ya conoce la verdad: el laberinto no se vence... se completa.»"),
    ("fin_dim", "El Corazón del Laberinto", "Derrotaste al Guardián. El Cazador se detuvo, por fin libre. El laberinto latió una vez más... y floreció."),
]
HISTORIA_POR_ID = {h[0]: h for h in HISTORIA}
FRAGMENTOS_SECRETOS = [h[0] for h in HISTORIA if h[0].startswith("secreto_")]

CINEMATICAS = {
    "intro": [
        "Hace mil años, el Jardinero Eterno plantó una semilla y construyó un laberinto para protegerla.",
        "Las frutas son recuerdos de aquel jardín. Los guardianes de cada mundo aún las custodian.",
        "Un cazador sin rostro recorre los pasillos, aprendiendo cada camino... buscando la salida.",
        "Tú eres un pequeño slime. Recoge frutas, descubre secretos y llega al final del laberinto.",
    ],
    "fin_50": [
        "El último guardián cae. El silencio llena el laberinto.",
        "Bajo tus pies, algo late. Un latido lento, antiguo, vivo.",
        "Las paredes se abren. Se ha desbloqueado la DIMENSIÓN OCULTA: EL CORAZÓN DEL LABERINTO.",
    ],
    "fin_dim": [
        "El Guardián del Corazón se desvanece en luz dorada.",
        "El Cazador aparece una última vez. Ya no persigue: te mira, y asiente.",
        "El laberinto no se vence... se completa. Gracias por jugar, valiente slime.",
    ],
}


class Progreso:
    """Todo lo que se guarda: estrellas, Frutacoins, skins, mejoras, mascotas, logros, records,
    historia, partida en curso y configuracion. Se guarda en un archivo .json junto al juego."""

    RECORDS_DEF = dict(mejor_combo=0, max_frutas=0, max_enemigos=0, tiempo_rapido=0, nivel_max=0, jefes=0, monedas_total=0)

    def __init__(self):
        self.estrellas = 0
        self.monedas = 0
        self.trofeos = []
        self.skins = ["verde"]
        self.equipada = "verde"
        self.stats = {}
        self.jefes = []
        self.mejor_puntos = 0
        self.mejoras = {}
        self.mascotas = []
        self.mascota = None
        self.efectos = []
        self.efecto = None
        self.logros = []
        self.records = dict(self.RECORDS_DEF)
        self.frutas_desc = []
        self.fragmentos = []
        self.dim_desbloqueada = False
        self.dim_completa = False
        self.partida = None
        self.logros_nuevos = []
        self.cargar()

    def cargar(self):
        d = DATOS_GUARDADO
        try:
            self.estrellas = max(0, int(d.get("estrellas", 0)))
            self.monedas = max(0, int(d.get("monedas", 0)))
            ids_tareas = {x["id"] for x in TAREAS}
            self.trofeos = [t for t in d.get("trofeos", []) if t in ids_tareas]
            self.skins = [s for s in d.get("skins", ["verde"]) if s in SKIN_POR_ID] or ["verde"]
            self.equipada = d.get("equipada", "verde")
            self.stats = {k: int(v) for k, v in d.get("stats", {}).items()}
            self.jefes = [int(j) for j in d.get("jefes", [])]
            self.mejor_puntos = int(d.get("mejor_puntos", 0))
            self.mejoras = {k: int(v) for k, v in d.get("mejoras", {}).items() if k in MEJORA_POR_ID}
            self.mascotas = [m for m in d.get("mascotas", []) if m in MASCOTA_POR_ID]
            self.mascota = d.get("mascota") if d.get("mascota") in self.mascotas else None
            self.efectos = [e for e in d.get("efectos", []) if e in EFECTO_POR_ID]
            self.efecto = d.get("efecto") if d.get("efecto") in self.efectos else None
            self.logros = [l for l in d.get("logros", []) if l in LOGRO_POR_ID]
            rc = d.get("records", {})
            for k in self.RECORDS_DEF:
                self.records[k] = int(rc.get(k, 0))
            self.frutas_desc = [f for f in d.get("frutas_desc", []) if f in [x[0] for x in FRUTAS]]
            self.fragmentos = [f for f in d.get("fragmentos", []) if f in HISTORIA_POR_ID]
            self.dim_desbloqueada = bool(d.get("dim_desbloqueada", False))
            self.dim_completa = bool(d.get("dim_completa", False))
            p = d.get("partida")
            self.partida = p if isinstance(p, dict) and "nivel" in p else None
        except (ValueError, TypeError, AttributeError):
            pass
        if "verde" not in self.skins:
            self.skins.insert(0, "verde")
        if self.equipada not in self.skins:
            self.equipada = "verde"
        self.records["nivel_max"] = max(self.records["nivel_max"], self.stats.get("nivel_max", 0))
        self.records["jefes"] = max(self.records["jefes"], len(self.jefes))

    def guardar(self):
        datos = dict(estrellas=self.estrellas, monedas=self.monedas, trofeos=self.trofeos, skins=self.skins,
                     equipada=self.equipada, stats=self.stats, jefes=self.jefes, mejor_puntos=self.mejor_puntos,
                     mejoras=self.mejoras, mascotas=self.mascotas, mascota=self.mascota, efectos=self.efectos,
                     efecto=self.efecto, logros=self.logros, records=self.records, frutas_desc=self.frutas_desc,
                     fragmentos=self.fragmentos, dim_desbloqueada=self.dim_desbloqueada,
                     dim_completa=self.dim_completa, partida=self.partida,
                     config=dict(CONFIG, controles=CONTROLES))
        try:
            tmp = RUTA_PROGRESO + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=1)
            os.replace(tmp, RUTA_PROGRESO)
        except OSError:
            pass  # si no se puede escribir, el juego sigue igual

    # ---------- tareas y logros ----------
    @staticmethod
    def monedas_tarea(t):
        return t["premio"] // 2 + 3

    def _revisar(self):
        """Marca como completadas las tareas y logros cuya meta ya se alcanzo. Devuelve las tareas nuevas."""
        self.stats["skins_total"] = len(self.skins)
        self.stats["jefes_distintos"] = len(self.jefes)
        self.stats["fragmentos_total"] = len(self.fragmentos)
        nuevas = []
        for t in TAREAS:
            if t["id"] not in self.trofeos and self.stats.get(t["stat"], 0) >= t["meta"]:
                self.trofeos.append(t["id"])
                self.estrellas += t["premio"]
                self._sumar_monedas_directo(self.monedas_tarea(t))
                nuevas.append(t)
        for l in LOGROS:
            if l["id"] not in self.logros and self.stats.get(l["stat"], 0) >= l["meta"]:
                self.logros.append(l["id"])
                self._sumar_monedas_directo(l["premio"])
                self.logros_nuevos.append(l)
        return nuevas

    def _sumar_monedas_directo(self, n):
        self.monedas += n
        self.stats["monedas_total"] = self.stats.get("monedas_total", 0) + n
        self.records["monedas_total"] = self.stats["monedas_total"]

    def sumar(self, clave, n=1):
        self.stats[clave] = self.stats.get(clave, 0) + n
        return self._revisar()

    def maximo(self, clave, valor):
        if valor > self.stats.get(clave, 0):
            self.stats[clave] = int(valor)
        return self._revisar()

    def avance(self, tarea):
        return min(self.stats.get(tarea["stat"], 0), tarea["meta"]), tarea["meta"]

    def tiene(self, skin_id):
        return skin_id in self.skins

    def ganar_estrellas(self, n):
        self.estrellas += n
        self.stats["estrellas_ganadas"] = self.stats.get("estrellas_ganadas", 0) + n

    def ganar_monedas(self, n):
        """Suma Frutacoins (se guardan para siempre). Devuelve las tareas nuevas que complete."""
        self._sumar_monedas_directo(n)
        return self._revisar()

    def pop_logros(self):
        out, self.logros_nuevos = self.logros_nuevos, []
        return out

    def record(self, clave, valor, menor=False):
        """Guarda un record si lo mejora. Devuelve True si es nuevo record."""
        actual = self.records.get(clave, 0)
        if valor <= 0:
            return False
        if (menor and (actual == 0 or valor < actual)) or (not menor and valor > actual):
            self.records[clave] = int(valor)
            return True
        return False

    def descubrir_fruta(self, nombre):
        if nombre not in self.frutas_desc:
            self.frutas_desc.append(nombre)
            return True
        return False

    def desbloquear_fragmento(self, id_):
        """True si el fragmento es nuevo."""
        if id_ in HISTORIA_POR_ID and id_ not in self.fragmentos:
            self.fragmentos.append(id_)
            self._revisar()
            return True
        return False

    def tareas_activas(self):
        """Por cada serie: (tarea_actual, serie_completa). La actual es la primera sin completar."""
        res = []
        for s in SERIES:
            ts = [t for t in TAREAS if t["serie"] == s["id"]]
            pend = [t for t in ts if t["id"] not in self.trofeos]
            res.append((pend[0] if pend else ts[-1], not pend))
        return res

    def siguiente(self, tarea):
        """La tarea que aparece despues de completar 'tarea' (o None si era la ultima)."""
        for t in TAREAS:
            if t["serie"] == tarea["serie"] and t["id"] not in self.trofeos:
                return t
        return None

    # ---------- tienda ----------
    def comprar(self, skin_id):
        """Devuelve (ok, mensaje, tareas_nuevas). Las skins normales cuestan estrellas; las premium, Frutacoins."""
        sk = SKIN_POR_ID[skin_id]
        if self.tiene(skin_id):
            return False, "Ya la tienes", []
        if sk["mon"]:
            if self.monedas < sk["mon"]:
                return False, f"Te faltan {sk['mon'] - self.monedas} Frutacoins", []
            self.monedas -= sk["mon"]
        else:
            if self.estrellas < sk["precio"]:
                return False, f"Te faltan {sk['precio'] - self.estrellas} estrellas", []
            self.estrellas -= sk["precio"]
        self.skins.append(skin_id)
        self.equipada = skin_id
        self.stats["skins_compradas"] = self.stats.get("skins_compradas", 0) + 1
        nuevas = self._revisar()
        self.guardar()
        return True, f"¡Compraste {sk['nombre']}!", nuevas

    def equipar(self, skin_id):
        if self.tiene(skin_id):
            self.equipada = skin_id
            self.guardar()

    def nivel_mejora(self, id_):
        return self.mejoras.get(id_, 0)

    def precio_mejora(self, id_):
        m = MEJORA_POR_ID[id_]
        n = self.nivel_mejora(id_)
        return m["precios"][n] if n < len(m["precios"]) else None

    def comprar_mejora(self, id_):
        precio = self.precio_mejora(id_)
        if precio is None:
            return False, "Mejora al máximo", []
        if self.monedas < precio:
            return False, f"Te faltan {precio - self.monedas} Frutacoins", []
        self.monedas -= precio
        self.mejoras[id_] = self.nivel_mejora(id_) + 1
        self.stats["mejoras_total"] = sum(self.mejoras.values())
        nuevas = self._revisar()
        self.guardar()
        return True, f"¡{MEJORA_POR_ID[id_]['nombre']} sube al nivel {self.mejoras[id_]}!", nuevas

    def comprar_mascota(self, id_):
        if id_ in self.mascotas:
            return False, "Ya la tienes", []
        precio = MASCOTA_POR_ID[id_]["precio"]
        if self.monedas < precio:
            return False, f"Te faltan {precio - self.monedas} Frutacoins", []
        self.monedas -= precio
        self.mascotas.append(id_)
        self.mascota = id_
        self.stats["mascotas_total"] = len(self.mascotas)
        nuevas = self._revisar()
        self.guardar()
        return True, f"¡Ahora te acompaña: {MASCOTA_POR_ID[id_]['nombre']}!", nuevas

    def equipar_mascota(self, id_):
        if id_ is None or id_ in self.mascotas:
            self.mascota = id_
            self.guardar()

    def comprar_efecto(self, id_):
        if id_ in self.efectos:
            return False, "Ya lo tienes", []
        precio = EFECTO_POR_ID[id_]["precio"]
        if self.monedas < precio:
            return False, f"Te faltan {precio - self.monedas} Frutacoins", []
        self.monedas -= precio
        self.efectos.append(id_)
        self.efecto = id_
        nuevas = self._revisar()
        self.guardar()
        return True, f"¡Efecto {EFECTO_POR_ID[id_]['nombre']} equipado!", nuevas

    def equipar_efecto(self, id_):
        if id_ is None or id_ in self.efectos:
            self.efecto = id_
            self.guardar()

    # ---------- bonus de mejoras y mascotas ----------
    def vel_mult(self):
        return 1.0 + 0.05 * self.nivel_mejora("velocidad") + (0.10 if self.mascota == "zorro" else 0.0)

    def vidas_max(self):
        return VIDAS_MAX + self.nivel_mejora("vida")

    def dano(self):
        return 1.0 + 0.5 * self.nivel_mejora("dano") + (0.5 if self.mascota == "dragon" else 0.0)

    def energia_max(self):
        return 100 + 20 * self.nivel_mejora("energia")

    def rareza(self):
        return 1.0 + 0.25 * self.nivel_mejora("rareza") + (0.5 if self.mascota == "gato" else 0.0)

    def desbloquear_jefe(self, mundo):
        """Registra el jefe derrotado y da su traje. Devuelve (skin_nueva_o_None, tareas_nuevas)."""
        skin = None
        if mundo not in self.jefes:
            self.jefes.append(mundo)
        self.records["jefes"] = len(self.jefes)
        for s in SKINS:
            if s["jefe"] == mundo and s["id"] not in self.skins:
                self.skins.append(s["id"])
                skin = s
        return skin, self._revisar()


PROG = Progreso()




# ======================================================
# Mundos: cada uno con su enemigo, su jefe y sus poderes
# ======================================================
MUNDOS = [
    dict(nombre="Cripta", enemigo="Esqueleto", plural="esqueletos", jefe="Rey Esqueleto",
         habilidad="invoca esqueletos", bomba="Onda expansiva", hielo="Congelar"),
    dict(nombre="Bosque", enemigo="Lobo", plural="lobos", jefe="Lobo Alfa",
         habilidad="embiste a toda velocidad", bomba="Planta carnívora", hielo="Enredaderas"),
    dict(nombre="Desierto", enemigo="Escorpión", plural="escorpiones", jefe="Escorpión Rey",
         habilidad="lanza veneno", bomba="Cactus", hielo="Arenas movedizas"),
    dict(nombre="Volcán", enemigo="Diablillo", plural="diablillos", jefe="Demonio de Lava",
         habilidad="deja charcos de lava", bomba="Meteoritos", hielo="Obsidiana"),
    dict(nombre="Glaciar", enemigo="Yeti", plural="yetis", jefe="Yeti Gigante",
         habilidad="pisotea el suelo", bomba="Avalancha", hielo="Ventisca"),
    dict(nombre="Neón", enemigo="Robot", plural="robots", jefe="Robot Supremo",
         habilidad="dispara rayos láser", bomba="Mina láser", hielo="Cortocircuito"),
    dict(nombre="Pantano", enemigo="Rana", plural="ranas", jefe="Rana Real",
         habilidad="te persigue sin descanso", bomba="Mina láser", hielo="Lodo pegajoso"),
    dict(nombre="Cueva", enemigo="Murciélago", plural="murciélagos", jefe="Murciélago Ancestral",
         habilidad="te persigue sin descanso", bomba="Mina láser", hielo="Cristalización"),
    dict(nombre="Cielo", enemigo="Águila", plural="águilas", jefe="Águila Tormenta",
         habilidad="te persigue sin descanso", bomba="Mina láser", hielo="Nube de tormenta"),
    dict(nombre="Abismo", enemigo="Criatura del Vacío", plural="criaturas del vacío", jefe="Devorador Cósmico",
         habilidad="te persigue sin descanso", bomba="Mina láser", hielo="Campo estático"),
]
TEXTOS_MUNDO = {  # lo que aparece al recoger el hielo (1) / la bomba (2) de cada mundo
    0: {1: "¡CONGELADOS!", 2: "+1 BOMBA"},
    1: {1: "¡ENREDADERAS!", 2: "+1 PLANTA"},
    2: {1: "¡ARENAS MOVEDIZAS!", 2: "+1 CACTUS"},
    3: {1: "¡OBSIDIANA!", 2: "+1 METEORITOS"},
    4: {1: "¡VENTISCA!", 2: "+1 AVALANCHA"},
    5: {1: "¡CORTOCIRCUITO!", 2: "+1 MINA LÁSER"},
    6: {1: "¡ATRAPADOS EN EL LODO!", 2: "+1 MINA LÁSER"},
    7: {1: "¡CRISTALIZADOS!", 2: "+1 MINA LÁSER"},
    8: {1: "¡TORMENTA ELÉCTRICA!", 2: "+1 MINA LÁSER"},
    9: {1: "¡CAMPO ESTÁTICO!", 2: "+1 MINA LÁSER"},
}
ESTADOS_HIELO = ["hielo", "enredado", "arena", "obsidiana", "ventisca", "corto",
                 "lodo", "cristal", "tormenta", "estatica"]

TEMAS.append(dict(nombre="Corazón", fondo=(14, 2, 10), piso=(46, 14, 32), piso2=(54, 18, 38),
                  pared=(124, 30, 62), luz=(224, 92, 124), sombra=(62, 14, 36), acento=(255, 200, 90)))
MUNDOS.append(dict(nombre="El Corazón del Laberinto", enemigo="Sombra", plural="sombras", jefe="Guardián del Corazón",
                   habilidad="late y desata ondas de sombra", bomba="Mina láser", hielo="Campo estático"))
TEXTOS_MUNDO[10] = {1: "¡LATIDO CONGELADO!", 2: "+1 MINA LÁSER"}
ESTADOS_HIELO.append("corazon")

PALETAS_ENEMIGO = {0: PALETAS_ESQUELETO}  # mundo 0: esqueletos
PALETAS_ENEMIGO.update(PALETAS)
# el jefe de la Cripta (Rey Esqueleto) usa una paleta de esqueleto: (hueso, oscuro, claro, ojos)
PALETAS_JEFE_TODOS = {0: ((222, 214, 190), (96, 84, 120), (255, 250, 235), (255, 70, 70))}
PALETAS_JEFE_TODOS.update(PALETAS_JEFE)
PALETAS_JEFE_TODOS[10] = ((200, 40, 90), (70, 8, 36), (255, 150, 180), (255, 220, 100))
PALETAS_ENEMIGO[10] = [((120, 24, 70), (40, 4, 28), (230, 100, 150), (255, 210, 90)),
                       ((70, 20, 110), (24, 6, 52), (170, 100, 230), (255, 120, 200)),
                       ((150, 40, 40), (60, 8, 20), (255, 140, 120), (255, 230, 120)),
                       ((40, 40, 90), (14, 12, 44), (130, 130, 240), (255, 90, 120))]

TINTES = {  # (multiplicar, sumar) sobre el sprite normal
    "asustado": ((90, 120, 255), (0, 10, 70)),
    "parpadeo": ((255, 255, 255), (110, 110, 120)),
    "golpe": ((255, 255, 255), (120, 120, 120)),
    "hielo": ((150, 200, 255), (20, 40, 70)),
    "enredado": ((190, 235, 190), (0, 15, 0)),
    "arena": ((235, 205, 150), (20, 10, 0)),
    "obsidiana": ((85, 85, 100), (0, 0, 0)),
    "ventisca": ((205, 228, 255), (15, 25, 40)),
    "corto": ((170, 170, 200), (0, 0, 25)),
    "lodo": ((170, 140, 90), (10, 5, 0)),
    "cristal": ((200, 170, 255), (20, 0, 40)),
    "tormenta": ((160, 180, 230), (0, 0, 30)),
    "estatica": ((150, 255, 225), (0, 30, 20)),
}
TINTES["corazon"] = ((255, 170, 190), (40, 0, 10))
TINTES["tanque"] = ((210, 182, 140), (24, 14, 0))
TINTES["tirador"] = ((255, 208, 208), (34, 0, 0))
TINTES["fantasma"] = ((185, 206, 255), (24, 24, 60))
_cache_enemigos = {}


def _dibujo_enemigo(mundo, alt=False):
    if alt and mundo in DIBUJOS_ALT:
        return DIBUJOS_ALT[mundo]
    if mundo == 0:
        return f_esqueleto
    return DIBUJOS[mundo]


def _dibujo_jefe(mundo):
    """Todos los jefes usan el dibujo de su mundo (el de la Cripta es un esqueleto con corona)."""
    if mundo == 0:
        return f_esqueleto
    return DIBUJOS[mundo]


def _tenir(spr, estado):
    mult, suma = TINTES[estado]
    t = spr.copy()
    t.fill(mult, special_flags=pygame.BLEND_RGB_MULT)
    if any(suma):
        t.fill(suma, special_flags=pygame.BLEND_RGB_ADD)
    return t


def sprite_enemigo(mundo, color, frame, d, estado=None, alt=False):
    """Sprite del enemigo del mundo (se crea la primera vez que se necesita)."""
    alt = alt and mundo in DIBUJOS_ALT
    clave = (mundo, color, frame, d, estado, alt)
    spr = _cache_enemigos.get(clave)
    if spr is None:
        base = _cache_enemigos.get((mundo, color, frame, d, None, alt))
        if base is None:
            base = hacer_sprite(_dibujo_enemigo(mundo, alt), 30, 30, PALETAS_ENEMIGO[mundo][color], frame, d)
            _cache_enemigos[(mundo, color, frame, d, None, alt)] = base
        spr = base if estado is None else _tenir(base, estado)
        _cache_enemigos[clave] = spr
    return spr


def sprite_jefe(mundo, frame, d, estado=None):
    clave = ("jefe", mundo, frame, d, estado)
    spr = _cache_enemigos.get(clave)
    if spr is None:
        base = _cache_enemigos.get(("jefe", mundo, frame, d, None))
        if base is None:
            base = crear_sprite_jefe(_dibujo_jefe(mundo), PALETAS_JEFE_TODOS[mundo], frame, d, 60)
            _cache_enemigos[("jefe", mundo, frame, d, None)] = base
        spr = base if estado is None else _tenir(base, estado)
        _cache_enemigos[clave] = spr
    return spr


_cache_iconos = {}


def iconos_poderes(mundo):
    """Iconos de los 5 poderes; la bomba y el hielo cambian con el mundo."""
    if mundo not in _cache_iconos:
        base = list(SPR_PODERES)
        if mundo > 0:
            mi = min(mundo, 9)
            base[1] = hacer_sprite(ICONOS_HIELO[mi], 28, 28)
            base[2] = hacer_sprite(ICONOS_BOMBA[mi], 28, 28)
        _cache_iconos[mundo] = base
    return _cache_iconos[mundo]


_cache_skin = {}


def sprite_jugador(d, t=0, skin_id=None, tam=28):
    skin_id = skin_id or PROG.equipada
    if skin_id == "arcoiris":  # esta skin cambia de color con el tiempo
        paso = (t // 6) % 18
        h = paso / 18.0

        def c(sat, val, dh=0.0):
            r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, sat, val)
            return int(r * 255), int(g * 255), int(b * 255)

        skin = dict(SKIN_POR_ID["arcoiris"], cuerpo=c(0.65, 0.95), oscuro=c(0.85, 0.5),
                    medio=c(0.75, 0.78), brillo=c(0.25, 1.0, 0.05))
        clave = ("arco", d, paso, tam)
    else:
        skin = SKIN_POR_ID[skin_id]
        clave = (skin_id, d, tam)
    spr = _cache_skin.get(clave)
    if spr is None:
        spr = hacer_sprite(f_jugador_skin, 28, tam, d, skin)
        _cache_skin[clave] = spr
    return spr


ICONO_ESTRELLA = hacer_sprite(f_estrella_simple, 28, 24)
ICONO_TROFEO = hacer_sprite(f_trofeo, 28, 26, True)
ICONO_TROFEO_GRIS = hacer_sprite(f_trofeo, 28, 26, False)
SPR_PLANTA = [hacer_sprite(f_planta, 44, 44, fr) for fr in range(3)]
SPR_CACTUS = hacer_sprite(f_cactus, 40, 40)
SPR_BOLA = hacer_sprite(f_bola_nieve, 44, 44)
SPR_METEORO = hacer_sprite(f_meteoro, 40, 40)
BRILLO_JEFE = crear_brillo(56, (255, 70, 110))
SOMBRA_JEFE = crear_sombra(44, 14, 100)


def dibujar_inmovil(m, cx, cy, mundo, t):
    """Efecto sobre un enemigo inmovilizado, segun el mundo."""
    cx, cy = int(cx), int(cy)
    if mundo == 0:  # cristales de hielo
        for ddx, h in ((-9, 7), (0, 10), (9, 7)):
            pygame.draw.polygon(m, (190, 235, 255), [(cx + ddx - 3, cy + 12), (cx + ddx + 3, cy + 12),
                                                     (cx + ddx, cy + 12 - int(h * 1.4))])
            pygame.draw.polygon(m, (255, 255, 255), [(cx + ddx - 1, cy + 12), (cx + ddx + 1, cy + 12),
                                                     (cx + ddx, cy + 12 - h)])
    elif mundo == 1:  # enredaderas
        for k in range(3):
            r = pygame.Rect(cx - 15, cy - 13 + k * 8, 30, 12)
            pygame.draw.arc(m, (46, 150, 58), r, 0.2 + k * 0.9, 3.5 + k * 0.9, 3)
            pygame.draw.arc(m, (120, 220, 100), r, 0.2 + k * 0.9, 3.5 + k * 0.9, 1)
        for k in range(4):
            a = k * 1.6 + 0.4
            pygame.draw.ellipse(m, (120, 220, 100), (int(cx + math.cos(a) * 14 - 3), int(cy + math.sin(a) * 11 - 2), 6, 4))
    elif mundo == 2:  # arenas movedizas
        pygame.draw.ellipse(m, (150, 104, 44), (cx - 18, cy + 3, 36, 16))
        pygame.draw.ellipse(m, (206, 160, 82), (cx - 15, cy + 5, 30, 11))
        pygame.draw.arc(m, (120, 80, 30), (cx - 9, cy + 7, 18, 7), t * 0.1, t * 0.1 + 3.5, 2)
    elif mundo == 3:  # obsidiana agrietada
        col = (255, 110 + int(60 * math.sin(t * 0.2)), 40)
        pygame.draw.lines(m, col, False, [(cx - 6, cy - 8), (cx - 2, cy - 2), (cx - 6, cy + 5)], 2)
        pygame.draw.lines(m, col, False, [(cx + 5, cy - 9), (cx + 2, cy), (cx + 7, cy + 7)], 2)
    elif mundo == 4:  # ventisca
        for k in range(5):
            a = t * 0.09 + k * 1.26
            pygame.draw.circle(m, (255, 255, 255), (int(cx + math.cos(a) * 16), int(cy + math.sin(a) * 12)), 2)
    elif mundo == 5 and (t // 3) % 2 == 0:  # cortocircuito
        pygame.draw.lines(m, (255, 240, 90), False, [(cx - 12, cy - 6), (cx - 4, cy - 2), (cx - 8, cy + 3), (cx + 2, cy + 8)], 2)
        pygame.draw.lines(m, (90, 235, 255), False, [(cx + 12, cy - 8), (cx + 5, cy - 1), (cx + 9, cy + 4)], 2)


# ======================================================
# Sprites nuevos 2.0: sombra del Corazon, El Cazador, monedas, cofres, pergaminos y mascotas
# ======================================================
def f_sombra(s, e, pal, fase, d):
    """Enemigo de la dimension oculta: llama de sombra con un corazon."""
    E = _E(e)
    cue, osc, cla, acc = pal
    dx, dy = DIRS[d]
    o = (0, 1.4, 0, -1.4)[fase % 4]
    pts = [(15, 2), (21, 9 + o), (24, 17), (21, 25), (15, 28 + o * 0.5), (9, 25), (6, 17), (9, 9 - o)]
    pygame.draw.polygon(s, osc, [(E(x), E(y)) for x, y in pts])
    pts2 = [(15, 4.5), (20, 10 + o), (22, 17), (19.6, 24), (15, 26.4 + o * 0.4), (10.4, 24), (8, 17), (10, 10 - o)]
    pygame.draw.polygon(s, cue, [(E(x), E(y)) for x, y in pts2])
    for sg in (-1, 1):  # puntas laterales
        pygame.draw.polygon(s, osc, [(E(15 + sg * 6), E(8)), (E(15 + sg * 11), E(3 + o * sg)), (E(15 + sg * 8.4), E(11))])
    pygame.draw.circle(s, cla, (E(13.3), E(18)), E(2.2))
    pygame.draw.circle(s, cla, (E(16.7), E(18)), E(2.2))
    pygame.draw.polygon(s, cla, [(E(11.4), E(19)), (E(18.6), E(19)), (E(15), E(23))])
    ox, oy = dx * 1.0, dy * 0.8
    for ex in (12, 18):
        pygame.draw.ellipse(s, acc, (E(ex - 1.6 + ox), E(11 + oy), E(3.2), E(4)))
        pygame.draw.ellipse(s, (20, 0, 10), (E(ex - 0.5 + ox), E(11.8 + oy), E(1.1), E(2.6)))


DIBUJOS[10] = f_sombra


def f_cazador(s, e, frame, mood):
    """EL CAZADOR: una capa oscura con un enorme ojo. mood 0 = calmado, 1 = cazando."""
    E = _E(e)
    w = (0, 1.5, 0, -1.5)[frame % 4]
    capa = [(15, 3), (23, 9), (25, 20), (22, 27 + w), (18.5, 24), (15, 28 - w), (11.5, 24), (8, 27 - w), (5, 20), (7, 9)]
    pygame.draw.polygon(s, (22, 10, 36), [(E(x), E(y)) for x, y in capa])
    capa2 = [(15, 5), (21, 10), (23, 20), (20.4, 25.4 + w), (15, 22.6), (9.6, 25.4 - w), (7, 20), (9, 10)]
    pygame.draw.polygon(s, (52, 24, 82), [(E(x), E(y)) for x, y in capa2])
    pygame.draw.ellipse(s, (240, 235, 245), (E(7.2), E(9.4), E(15.6), E(10.6)))
    iris = (255, 50, 70) if mood else (150, 90, 255)
    pygame.draw.circle(s, iris, (E(15), E(14.7)), E(4.5))
    pygame.draw.circle(s, mezcla(iris, 0.5), (E(15), E(14.7)), E(4.5), E(0.8))
    ancho = 0.9 if mood else 1.5
    pygame.draw.ellipse(s, (10, 4, 16), (E(15 - ancho), E(11), E(ancho * 2), E(7.4)))
    pygame.draw.circle(s, (255, 255, 255), (E(13.2), E(12.6)), E(0.9))
    pygame.draw.polygon(s, (22, 10, 36), [(E(6), E(10)), (E(24), E(10)), (E(21), E(8.4 if mood else 9)), (E(9), E(8.4 if mood else 9))])


def f_moneda(s, e):
    E = _E(e)
    pygame.draw.circle(s, (150, 96, 8), (E(14), E(14)), E(12))
    pygame.draw.circle(s, (250, 196, 40), (E(14), E(14)), E(10.8))
    pygame.draw.circle(s, (255, 232, 120), (E(14), E(14)), E(8.2))
    pygame.draw.circle(s, (230, 160, 20), (E(14), E(14)), E(8.2), E(0.9))
    pygame.draw.circle(s, (255, 130, 60), (E(14), E(14.6)), E(3.6))
    pygame.draw.line(s, (90, 150, 50), (E(14), E(11.2)), (E(15.4), E(8.4)), E(1.3))
    pygame.draw.ellipse(s, (255, 255, 230), (E(8.4), E(7.8), E(3.4), E(2)))


def f_cofre(s, e, abierto=False):
    E = _E(e)
    pygame.draw.rect(s, (80, 46, 18), (E(3), E(12), E(22), E(13)), border_radius=E(2))
    pygame.draw.rect(s, (150, 92, 40), (E(4), E(13), E(20), E(11)), border_radius=E(1.5))
    pygame.draw.rect(s, (255, 205, 60), (E(12), E(13), E(4), E(11)))
    if abierto:
        pygame.draw.polygon(s, (110, 64, 26), [(E(3), E(12)), (E(25), E(12)), (E(23), E(4)), (E(5), E(4))])
        pygame.draw.rect(s, (255, 236, 120), (E(6), E(11), E(16), E(2)))
    else:
        pygame.draw.rect(s, (110, 64, 26), (E(3), E(5), E(22), E(8)), border_top_left_radius=E(6), border_top_right_radius=E(6))
        pygame.draw.rect(s, (255, 205, 60), (E(12), E(5), E(4), E(8)))
        pygame.draw.circle(s, (255, 235, 130), (E(14), E(13)), E(1.8))


def f_pergamino(s, e):
    E = _E(e)
    pygame.draw.rect(s, (120, 80, 40), (E(5), E(4), E(18), E(20)), border_radius=E(3))
    pygame.draw.rect(s, (238, 220, 170), (E(6.4), E(5.4), E(15.2), E(17.2)), border_radius=E(2))
    for i in range(4):
        pygame.draw.line(s, (150, 110, 70), (E(8.6), E(9 + i * 3.2)), (E(19.4 - (i % 2) * 3), E(9 + i * 3.2)), E(0.9))
    pygame.draw.circle(s, (210, 50, 70), (E(19), E(20)), E(2))


def f_perro(s, e, frame):
    E = _E(e)
    c, o, cl = (190, 130, 70), (110, 66, 28), (240, 200, 150)
    pata = (0, 1.6)[frame % 2]
    for x, dy in ((9, pata), (12.5, -pata), (18, pata), (21, -pata)):
        pygame.draw.rect(s, o, (E(x), E(19), E(2.4), E(5 + dy)), border_radius=E(1))
    pygame.draw.ellipse(s, c, (E(6), E(11), E(19), E(11)))
    pygame.draw.circle(s, c, (E(23), E(11)), E(5))
    pygame.draw.polygon(s, o, [(E(21), E(8)), (E(19.4), E(14)), (E(23), E(12))])
    pygame.draw.ellipse(s, cl, (E(22), E(11), E(6), E(4.4)))
    pygame.draw.circle(s, (20, 14, 10), (E(27), E(12)), E(1.3))
    pygame.draw.circle(s, (20, 14, 10), (E(24), E(9.6)), E(1))
    pygame.draw.line(s, c, (E(7), E(13)), (E(3), E(8 + frame * 2)), E(2.4))


def f_gato(s, e, frame):
    E = _E(e)
    c, o, cl = (250, 170, 80), (170, 96, 30), (255, 230, 190)
    pygame.draw.arc(s, o, (E(1), E(5), E(10), E(14)), 0.6, 4.2 + frame * 0.3, E(2.4))
    pygame.draw.ellipse(s, c, (E(6), E(12), E(17), E(11)))
    for x in (9, 19):
        pygame.draw.rect(s, o, (E(x), E(20), E(2.6), E(5)), border_radius=E(1))
    pygame.draw.circle(s, c, (E(22), E(11)), E(5.4))
    for sg in (-1, 1):
        pygame.draw.polygon(s, c, [(E(22 + sg * 1.4), E(7)), (E(22 + sg * 5.2), E(7.6)), (E(22 + sg * 3.8), E(2.4))])
    pygame.draw.ellipse(s, (60, 220, 90), (E(21.6), E(9.4), E(2.6), E(3.2)))
    pygame.draw.ellipse(s, (60, 220, 90), (E(25), E(9.4), E(2.6), E(3.2)))
    pygame.draw.circle(s, (255, 140, 160), (E(27), E(13)), E(1))
    pygame.draw.ellipse(s, cl, (E(10), E(17), E(8), E(5)))


def f_dragon(s, e, frame):
    E = _E(e)
    c, o, cl = (110, 200, 90), (50, 110, 44), (255, 230, 130)
    ala = (-4, 2)[frame % 2]
    pygame.draw.polygon(s, (170, 100, 220), [(E(11), E(13)), (E(8), E(3 + ala)), (E(16), E(6 + ala)), (E(18), E(13))])
    pygame.draw.polygon(s, o, [(E(1), E(22)), (E(8), E(17)), (E(8), E(22))])
    pygame.draw.ellipse(s, c, (E(6), E(12), E(17), E(11)))
    pygame.draw.ellipse(s, cl, (E(10), E(17), E(9), E(6)))
    for x in (9, 18):
        pygame.draw.rect(s, o, (E(x), E(20), E(3), E(5)), border_radius=E(1))
    pygame.draw.circle(s, c, (E(23), E(12)), E(5))
    pygame.draw.ellipse(s, c, (E(24), E(11), E(5), E(4)))
    pygame.draw.polygon(s, (255, 210, 80), [(E(21), E(8)), (E(22), E(3)), (E(24), E(8))])
    pygame.draw.circle(s, (255, 230, 60), (E(24), E(10.4)), E(1.5))
    pygame.draw.circle(s, (30, 20, 10), (E(24.4), E(10.4)), E(0.7))


def f_zorro(s, e, frame):
    E = _E(e)
    c, o, cl = (240, 130, 50), (150, 64, 20), (255, 245, 230)
    pygame.draw.ellipse(s, c, (E(0), E(10 + frame), E(12), E(8)))
    pygame.draw.ellipse(s, cl, (E(0), E(10 + frame), E(4), E(8)))
    for x in (9, 19):
        pygame.draw.rect(s, o, (E(x), E(20), E(2.6), E(5)), border_radius=E(1))
    pygame.draw.ellipse(s, c, (E(7), E(12), E(17), E(10)))
    pygame.draw.circle(s, c, (E(22.5), E(11.5)), E(5))
    for sg in (-1, 1):
        pygame.draw.polygon(s, c, [(E(22.5 + sg * 1.2), E(8)), (E(22.5 + sg * 5), E(8.4)), (E(22.5 + sg * 3.4), E(2.6))])
        pygame.draw.polygon(s, o, [(E(22.5 + sg * 2), E(7.4)), (E(22.5 + sg * 4), E(7.6)), (E(22.5 + sg * 3.4), E(4.4))])
    pygame.draw.ellipse(s, cl, (E(22), E(11.6), E(6.4), E(4.4)))
    pygame.draw.circle(s, (20, 14, 10), (E(27.6), E(12.6)), E(1.2))
    pygame.draw.circle(s, (20, 14, 10), (E(24.2), E(10)), E(0.9))


SPR_MONEDA = hacer_sprite(f_moneda, 28, 22)
SPR_COFRE = [hacer_sprite(f_cofre, 28, 30, False), hacer_sprite(f_cofre, 28, 30, True)]
SPR_PERGAMINO = hacer_sprite(f_pergamino, 28, 26)
BRILLO_MONEDA = crear_brillo(18, (255, 215, 70))
BRILLO_CAZADOR = crear_brillo(34, (170, 90, 255))
BRILLO_CAZADOR_ROJO = crear_brillo(34, (255, 60, 80))
_FN_MASCOTA = {"perro": f_perro, "gato": f_gato, "dragon": f_dragon, "zorro": f_zorro}
_cache_extra = {}


def sprite_cazador(frame, mood):
    k = ("cazador", frame % 4, mood)
    if k not in _cache_extra:
        _cache_extra[k] = hacer_sprite(f_cazador, 30, 38, frame % 4, mood)
    return _cache_extra[k]


def sprite_mascota(id_, frame, tam=30, izq=False):
    k = ("pet", id_, frame % 2, tam, izq)
    if k not in _cache_extra:
        spr = hacer_sprite(_FN_MASCOTA[id_], 30, tam, frame % 2)
        _cache_extra[k] = pygame.transform.flip(spr, True, False) if izq else spr
    return _cache_extra[k]


def sprite_escalado(spr, k):
    key = ("esc", id(spr), round(k, 2))
    if key not in _cache_extra:
        _cache_extra[key] = pygame.transform.smoothscale(spr, (int(spr.get_width() * k), int(spr.get_height() * k)))
    return _cache_extra[key]


class Poder:
    """Poder que se recoge del suelo (estrella, hielo, bomba, rafaga, rayo)."""

    def __init__(self, celda, tipo, mundo=0):
        self.cx = celda[0] * TAM + TAM / 2
        self.cy = celda[1] * TAM + TAM / 2
        self.tipo = tipo
        self.mundo = mundo
        self.fase = random.uniform(0, math.tau)

    def dibujar(self, m, t):
        b = math.sin(t * 0.07 + self.fase)
        glow = BRILLOS_PODER[self.tipo]
        glow.set_alpha(int(170 + 80 * math.sin(t * 0.09 + self.fase)))
        m.blit(glow, (int(self.cx - 28), int(self.cy - 28)))
        m.blit(SOMBRA_FRUTA, (int(self.cx - 9), int(self.cy + 11)))
        color = PODERES[self.tipo][2]
        for i in range(3):  # puntitos orbitando: los distinguen de las frutas
            a = t * 0.06 + self.fase + i * math.tau / 3
            pygame.draw.circle(m, color, (int(self.cx + math.cos(a) * 19), int(self.cy - 2 * b + math.sin(a) * 19)), 2)
        m.blit(iconos_poderes(self.mundo)[self.tipo], (int(self.cx - 14), int(self.cy - 14 - 2 * b)))


# ======================================================
# Enemigos y jefes
# ======================================================
VECINOS = ((1, 0), (-1, 0), (0, 1), (0, -1))

# tipos: 0 perseguidor, 1 emboscador, 2 rapido, 3 tanque, 4 tirador, 5 fantasma, 6 el cazador
ENEMIGO_INFO = {
    0: dict(nombre="Perseguidor", hp=1.0, vel=1.0, pts=100, monedas=1, tinte=None),
    1: dict(nombre="Emboscador", hp=1.0, vel=1.0, pts=120, monedas=1, tinte=None),
    2: dict(nombre="Rápido", hp=1.0, vel=1.12, pts=150, monedas=1, tinte=None),
    3: dict(nombre="Tanque", hp=3.0, vel=0.78, pts=250, monedas=3, tinte="tanque"),
    4: dict(nombre="Tirador", hp=1.0, vel=0.9, pts=200, monedas=2, tinte="tirador"),
    5: dict(nombre="Fantasma", hp=2.0, vel=0.92, pts=220, monedas=2, tinte="fantasma"),
    6: dict(nombre="El Cazador", hp=4.0, vel=1.0, pts=500, monedas=12, tinte=None),
}
TIPO_CAZADOR = 6


def linea_libre(a, b):
    """True si las casillas a y b estan en la misma fila/columna sin paredes entre ellas."""
    if a[0] != b[0] and a[1] != b[1]:
        return False
    dc = (b[0] > a[0]) - (b[0] < a[0])
    df = (b[1] > a[1]) - (b[1] < a[1])
    c = a
    while c != b:
        c = (c[0] + dc, c[1] + df)
        if not (0 <= c[0] < COLS and 0 <= c[1] < FILAS) or MAPA[c[1]][c[0]] == "#":
            return False
    return True


class Enemigo:
    es_jefe = False

    def __init__(self, celda, velocidad, color_idx, tipo=0, mundo=0, alt=False):
        self.tipo = tipo
        self.mundo = mundo
        self.alt = alt  # True: usa la criatura nueva del mundo (sapo/arana/nube/ojo)
        self.cx = celda[0] * TAM + TAM / 2
        self.cy = celda[1] * TAM + TAM / 2
        self.vel = velocidad
        self.color = color_idx
        self.destino = None
        self.previa = None
        self.dir = (0.0, 1.0)
        self.fase = random.uniform(0, math.tau)
        self.offset = random.randint(0, 3)
        info = ENEMIGO_INFO.get(tipo, ENEMIGO_INFO[0])
        self.info = info
        self.hp = self.hp_max = info["hp"]
        self.tinte = info["tinte"]
        self.flash = 0        # destello al recibir un golpe
        self.congelado = 0    # inmovilizado por el disparo de hielo
        self.paralizado = 0   # inmovilizado por el limon
        self.invasor = 0      # >0: se retira cuando llega a 0 (evento invasion)
        self.oculto = False   # escondido en el lodo (pantano)
        self.carga = 0
        self.cd = random.randint(30, 90)
        self.etereo = False

    def celda(self):
        return (int(self.cx // TAM), int(self.cy // TAM))

    def rect(self):
        t = 20 if self.tipo == 3 else 16
        return pygame.Rect(int(self.cx - t // 2), int(self.cy - t // 2), t, t)

    def teletransportar(self, celda):
        self.cx = celda[0] * TAM + TAM / 2
        self.cy = celda[1] * TAM + TAM / 2
        self.destino = None

    def _avanzar(self, tx, ty, vel):
        dx, dy = tx - self.cx, ty - self.cy
        dist = math.hypot(dx, dy)
        if dist <= vel:
            self.cx, self.cy = tx, ty
            return True
        self.cx += dx / dist * vel
        self.cy += dy / dist * vel
        self.dir = (dx / dist, dy / dist)
        return False

    def actualizar(self, mapa_dist, celda_j, centro_j, huir=False, mult=1.0):
        """Sigue el mapa de distancias (BFS) hacia su meta. Si 'huir', se aleja del jugador."""
        vel = self.vel * (0.7 if huir else 1.0) * mult
        if vel <= 0:
            return
        if self.destino is None:
            c = self.celda()
            if huir:
                ops = [(mapa_dist[(c[0] + dc, c[1] + df)], (c[0] + dc, c[1] + df))
                       for dc, df in VECINOS if (c[0] + dc, c[1] + df) in mapa_dist]
                sin_volver = [o for o in ops if o[1] != self.previa]
                ops = sin_volver or ops
                if ops:
                    mx = max(o[0] for o in ops)
                    self.destino = random.choice([o[1] for o in ops if o[0] == mx])
                self.previa = c
            else:
                if c == celda_j:
                    self._avanzar(centro_j[0], centro_j[1], vel)
                    return
                cands, md = [], mapa_dist.get(c, 10 ** 9)
                for dc, df in VECINOS:
                    n = (c[0] + dc, c[1] + df)
                    if n in mapa_dist:
                        if mapa_dist[n] < md:
                            cands, md = [n], mapa_dist[n]
                        elif cands and mapa_dist[n] == md:
                            cands.append(n)  # empate: caminos igual de cortos
                self.destino = random.choice(cands) if cands else None  # asi no se apilan en fila
                self.previa = c
        if self.destino is not None:
            tx = self.destino[0] * TAM + TAM / 2
            ty = self.destino[1] * TAM + TAM / 2
            if self._avanzar(tx, ty, vel):
                self.destino = None

    def inmovil(self):
        """Gestiona congelacion / paralisis. True si no se puede mover este frame."""
        if self.flash > 0:
            self.flash -= 1
        if self.congelado > 0:
            self.congelado -= 1
            return True
        if self.paralizado > 0:
            self.paralizado -= 1
            return True
        return False

    def ia(self, j, cj, centro, huir, mult):
        """Comportamiento: perseguidor / emboscador / rapido / tanque (los demas lo sobreescriben)."""
        if self.inmovil():
            return
        mapa, meta = j.dist_jugador, cj
        if self.tipo == 1 and not huir and j.dist_jugador.get(self.celda(), 0) > 4:
            meta = j.celda_emboscada(cj)  # se anticipa a tu camino
            mapa = j.dist_desde(meta)
        self.actualizar(mapa, cj, centro, huir, mult)

    def direccion_visual(self):
        dx, dy = self.dir
        if abs(dx) > abs(dy):
            return "derecha" if dx > 0 else "izquierda"
        return "abajo" if dy > 0 else "arriba"

    def dibujar(self, m, t, estado=None):
        """estado: None | 'asustado' | 'parpadeo' | uno de ESTADOS_HIELO"""
        frame = (t // 8 + self.offset) % 4
        d = self.direccion_visual()
        bob = math.sin(t * 0.1 + self.fase) * 2
        if self.congelado > 0:
            estado = "hielo"
        if estado in ESTADOS_HIELO and estado != "ventisca":
            frame, bob = 0, 0
        if estado == "parpadeo" and (t // 6) % 2 == 1:
            estado = "asustado"
        if self.flash > 0 and (self.flash // 2) % 2 == 0:
            estado = "golpe"
        elif estado is None:
            estado = self.tinte
        if self.oculto:  # escondido en el lodo: solo se ven burbujas
            for k in range(3):
                pygame.draw.circle(m, (150, 200, 120), (int(self.cx - 6 + k * 6), int(self.cy + 4 - ((t // 6 + k) % 4) * 2)), 2, 1)
            return
        spr = sprite_enemigo(self.mundo, self.color, frame, d, estado, self.alt)
        if self.tipo == 3:
            spr = sprite_escalado(spr, 1.3)
        w, h = spr.get_size()
        base = self.cy + 13
        m.blit(SOMBRA, (int(self.cx - 12 * (1.3 if self.tipo == 3 else 1)), int(self.cy + 9)))
        if self.etereo or self.tipo == 5:
            spr = spr.copy()
            spr.set_alpha(110 if self.etereo else 190)
        m.blit(spr, (int(self.cx - w / 2), int(base - h + bob)))
        if self.congelado > 0:
            dibujar_inmovil(m, self.cx, self.cy, 0, t)
        elif estado in ESTADOS_HIELO and self.paralizado <= 0:
            dibujar_inmovil(m, self.cx, self.cy, self.mundo, t)
        if self.paralizado > 0 and (t // 4) % 2 == 0:  # chispas de paralisis
            pygame.draw.line(m, (255, 240, 90), (int(self.cx - 8), int(self.cy - 12)), (int(self.cx + 2), int(self.cy - 4)), 2)
            pygame.draw.line(m, (255, 240, 90), (int(self.cx + 2), int(self.cy - 4)), (int(self.cx - 3), int(self.cy + 4)), 2)
        if self.hp_max > 1:  # barrita de vida
            w2 = 20
            pygame.draw.rect(m, (30, 10, 20), (int(self.cx - w2 / 2), int(base - h - 3 + bob), w2, 4))
            pygame.draw.rect(m, (255, 90, 90), (int(self.cx - w2 / 2), int(base - h - 3 + bob), max(1, int(w2 * self.hp / self.hp_max)), 4))
        if self.carga > 0:  # el tirador apunta
            pygame.draw.circle(m, (255, 80, 80), (int(self.cx), int(self.cy)), 10 + self.carga // 3, 1)


class Tirador(Enemigo):
    """Ataca desde lejos: se queda a unas casillas y dispara en linea recta."""

    def ia(self, j, cj, centro, huir, mult):
        if self.inmovil():
            return
        c = self.celda()
        d = j.dist_jugador.get(c, 99)
        if self.cd > 0:
            self.cd -= 1
        if self.carga > 0:
            self.carga -= 1
            if self.carga == 0:
                dx = (cj[0] > c[0]) - (cj[0] < c[0])
                dy = (cj[1] > c[1]) - (cj[1] < c[1])
                j.disparar_enemigo(self.cx, self.cy, dx, dy, "bala", 5.5)
            return
        if d <= 3 and not huir:
            self.actualizar(j.dist_jugador, cj, centro, True, mult * 1.1)  # se aleja para mantener distancia
        elif linea_libre(c, cj) and 3 <= d <= 9 and not huir:
            self.dir = (float((cj[0] > c[0]) - (cj[0] < c[0])), float((cj[1] > c[1]) - (cj[1] < c[1])))
            if self.cd <= 0:
                self.carga = 24
                self.cd = 120
        else:
            self.actualizar(j.dist_jugador, cj, centro, huir, mult)


class Fantasma(Enemigo):
    """Persigue por el laberinto y, a ratos, se vuelve etereo y atraviesa las paredes."""

    def ia(self, j, cj, centro, huir, mult):
        if self.inmovil():
            return
        ciclo = (j.t + self.offset * 55) % 360
        dentro = es_pared(self.cx, self.cy)
        if (ciclo >= 250 or dentro) and not huir:
            self.etereo = True
            dx, dy = centro[0] - self.cx, centro[1] - self.cy
            dist = math.hypot(dx, dy) or 1
            v = self.vel * 0.85 * mult
            self.cx = max(TAM + 6, min(ANCHO - TAM - 6, self.cx + dx / dist * v))
            self.cy = max(TAM + 6, min(ALTO_MAPA - TAM - 6, self.cy + dy / dist * v))
            self.dir = (dx / dist, dy / dist)
            self.destino = None
        else:
            self.etereo = False
            self.actualizar(j.dist_jugador, cj, centro, huir, mult)


class Cazador(Enemigo):
    """EL CAZADOR. Observa por donde pasas, recuerda tus caminos favoritos, se anticipa y te bloquea.
    nivel_ia (1-5) decide cuanto aprende y que tan agresivo es."""

    OBS_COMPLETO = 260   # observaciones (1 cada 6 frames) para "haber aprendido" del todo

    def __init__(self, celda, nivel_ia, mundo, vel_base, habito=None):
        super().__init__(celda, vel_base * (0.72 + 0.07 * nivel_ia), 0, TIPO_CAZADOR, mundo)
        self.nivel_ia = nivel_ia
        self.hp = self.hp_max = 2.0 + nivel_ia
        self.calor = {}
        self.habito = dict(habito) if habito else {d: 1 for d in DIRS}
        self.obs = 0
        self.modo = "perseguir"
        self.modo_t = 0
        self.meta = None
        self.bloqueando = False
        self.aparicion = 50
        self.mood = 0

    @property
    def aprendizaje(self):
        return min(1.0, self.obs / self.OBS_COMPLETO)

    def observar(self, celda, direccion, moviendo):
        self.calor[celda] = self.calor.get(celda, 0) + 1
        if moviendo:
            self.habito[direccion] = self.habito.get(direccion, 0) + 1
        self.obs += 1

    def dir_habitual(self, direccion_actual):
        """La direccion que mas usa el jugador (mezclada con la actual)."""
        mejor = max(self.habito, key=self.habito.get)
        return DIRS[mejor] if random.random() < 0.5 * self.aprendizaje else DIRS[direccion_actual]

    def elegir_modo(self):
        ia, ap = self.nivel_ia, 0.35 + 0.65 * self.aprendizaje
        pesos = {1: (85, 15, 0), 2: (60, 40, 0), 3: (38, 42, 20), 4: (24, 44, 32), 5: (14, 44, 42)}[ia]
        p_pers = pesos[0] + (100 - pesos[0]) * (1 - ap)
        r = random.uniform(0, 100)
        if r < p_pers:
            return "perseguir"
        return "anticipar" if random.random() * (pesos[1] + pesos[2] + 0.001) < pesos[1] else "bloquear"

    def meta_anticipar(self, j, cj):
        dx, dy = self.dir_habitual(j.direccion)
        mejor, mp = None, 0.0
        for c, d in j.dist_jugador.items():
            if 2 <= d <= 8:
                p = self.calor.get(c, 0)
                if p > 0:
                    if (c[0] - cj[0]) * dx + (c[1] - cj[1]) * dy > 0:
                        p *= 1.7
                    p /= 1 + 0.15 * d
                    if p > mp:
                        mejor, mp = c, p
        if mejor is None or mp < 1.5:
            return j.celda_emboscada(cj)
        return mejor

    def meta_bloquear(self, j, cj):
        """Un cruce de caminos unas casillas por delante del jugador."""
        dx, dy = self.dir_habitual(j.direccion)
        c, prev = cj, None
        for _ in range(10):
            vec = [(c[0] + a, c[1] + b) for a, b in VECINOS if (c[0] + a, c[1] + b) in j.dist_jugador and (c[0] + a, c[1] + b) != prev]
            if not vec:
                break
            if len(vec) >= 2 and c != cj:
                return c
            sig = (c[0] + dx, c[1] + dy)
            nuevo = sig if sig in vec else max(vec, key=lambda v: j.dist_jugador.get(v, 0))
            prev, c = c, nuevo
        return c

    def ia(self, j, cj, centro, huir, mult):
        if self.aparicion > 0:
            self.aparicion -= 1
            return
        if self.inmovil():
            return
        self.modo_t -= 1
        if self.modo_t <= 0 or self.meta is None:
            self.modo = self.elegir_modo()
            self.modo_t = random.randint(70, 140) - 8 * self.nivel_ia
            self.meta = None if self.modo == "perseguir" else (
                self.meta_anticipar(j, cj) if self.modo == "anticipar" else self.meta_bloquear(j, cj))
            self.mood = 0 if self.modo == "perseguir" and self.aprendizaje < 0.6 else 1
        self.bloqueando = False
        if huir:
            self.actualizar(j.dist_jugador, cj, centro, True, mult)
            return
        if self.modo == "perseguir" or self.meta is None:
            self.actualizar(j.dist_jugador, cj, centro, False, mult)
            return
        c = self.celda()
        if j.dist_jugador.get(c, 99) <= 3:        # el jugador esta cerca: ataca
            self.modo_t = 0
            self.actualizar(j.dist_jugador, cj, centro, False, mult * 1.1)
            return
        mapa = j.dist_desde(self.meta)
        if c == self.meta:
            self.bloqueando = True                 # esperando en su emboscada
            return
        self.actualizar(mapa, self.meta, (self.meta[0] * TAM + TAM / 2, self.meta[1] * TAM + TAM / 2), False, mult)

    def dibujar(self, m, t, estado=None):
        bob = math.sin(t * 0.07) * 3
        glow = BRILLO_CAZADOR_ROJO if self.mood else BRILLO_CAZADOR
        glow.set_alpha(int(140 + 90 * math.sin(t * 0.1)))
        m.blit(glow, (int(self.cx - 34), int(self.cy - 34 + bob)))
        spr = sprite_cazador(t // 10, self.mood)
        if self.flash > 0 and (self.flash // 2) % 2 == 0:
            spr = spr.copy()
            spr.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)
        if self.congelado > 0:
            spr = spr.copy()
            spr.fill((90, 120, 190), special_flags=pygame.BLEND_RGB_ADD)
        if self.aparicion > 0:
            spr = spr.copy()
            spr.set_alpha(int(255 * (1 - self.aparicion / 50)))
        m.blit(SOMBRA, (int(self.cx - 12), int(self.cy + 12)))
        m.blit(spr, (int(self.cx - 19), int(self.cy - 22 + bob)))
        if self.paralizado > 0 and (t // 4) % 2 == 0:
            pygame.draw.line(m, (255, 240, 90), (int(self.cx - 8), int(self.cy - 12)), (int(self.cx + 2), int(self.cy - 4)), 2)
        x0, y0 = int(self.cx - 15), int(self.cy - 30 + bob)
        pygame.draw.rect(m, (30, 10, 20), (x0, y0, 30, 4))
        pygame.draw.rect(m, (255, 80, 100), (x0, y0, max(1, int(30 * self.hp / self.hp_max)), 4))
        pygame.draw.rect(m, (30, 10, 40), (x0, y0 - 4, 30, 3))
        pygame.draw.rect(m, (190, 120, 255), (x0, y0 - 4, int(30 * self.aprendizaje), 3))
        if self.bloqueando:
            texto(m, "!", F_MED, (255, 90, 90), (int(self.cx), int(self.cy - 42)), centro=True)


FASE2_HP = 0.5
FASE3_HP = 0.22


class Jefe(Enemigo):
    es_jefe = True

    def __init__(self, celda, mundo):
        super().__init__(celda, 2.0 + 0.12 * min(mundo, 9), 0, 0, mundo)
        self.hp_max = 24 + 8 * min(mundo, 10)
        self.hp = float(self.hp_max)
        self.inv = 0       # frames en que no recibe dano
        self.t = 0
        self.mult = 1.0    # multiplicador de velocidad (habilidades)
        self.aviso = False
        self.fase = 1
        self.fase_t = 0    # frames desde el ultimo cambio de fase
        self.final_hecho = False

    def fase_actual(self):
        k = self.hp / self.hp_max
        return 3 if k <= FASE3_HP else (2 if k <= FASE2_HP else 1)

    def rect(self):
        return pygame.Rect(int(self.cx - 14), int(self.cy - 14), 28, 28)

    def ia(self, j, cj, centro, huir, mult):
        self.actualizar(j.dist_jugador, cj, centro, False, mult)

    def dibujar(self, m, t, estado=None):
        frame = (t // (10 if self.fase == 1 else 6)) % 4
        d = self.direccion_visual()
        bob = math.sin(t * 0.08) * 2
        if estado in ESTADOS_HIELO and estado != "ventisca":
            frame, bob = 0, 0
        col = ((255, 70, 110), (255, 140, 40), (255, 240, 240))[self.fase - 1]
        brillo = crear_brillo_cache(56, col)
        brillo.set_alpha(int(150 + 90 * math.sin(t * (0.1 if self.fase == 1 else 0.25))))
        m.blit(brillo, (int(self.cx - 56), int(self.cy - 56)))
        m.blit(SOMBRA_JEFE, (int(self.cx - 22), int(self.cy + 14)))
        if self.inv > 0 and (self.inv // 2) % 2 == 0:
            spr = sprite_jefe(self.mundo, frame, d, "golpe")
        else:
            spr = sprite_jefe(self.mundo, frame, d, estado if estado in TINTES else None)
        m.blit(spr, (int(self.cx - 30), int(self.cy - 38 + bob)))
        if estado in ESTADOS_HIELO:
            dibujar_inmovil(m, self.cx, self.cy, min(self.mundo, 9), t)
        if self.fase == 3:  # anillo de energia
            pygame.draw.circle(m, (255, 255, 255), (int(self.cx), int(self.cy)), 34 + int(3 * math.sin(t * 0.3)), 1)
        if self.aviso:
            texto(m, "!", F_GRANDE, (255, 70, 70), (int(self.cx), int(self.cy - 52)), centro=True)


_cache_brillos = {}


def crear_brillo_cache(radio, color):
    k = (radio, color)
    if k not in _cache_brillos:
        _cache_brillos[k] = crear_brillo(radio, color)
    return _cache_brillos[k]


# ======================================================
# Arma del jugador (ataque normal, cargado, hielo, rafaga, furia...)
# ======================================================
COLORES_ATAQUE = dict(normal=(110, 200, 255), multi=(235, 140, 255), carga=(255, 230, 120), hielo=(160, 232, 255),
                      rafaga=(255, 170, 255), furia=(255, 90, 60), dragon=(255, 150, 50))


class Arma:
    def __init__(self, velocidad=10, cooldown=15, radio=5):
        self.vel, self.cooldown, self.radio = velocidad, cooldown, radio
        self.espera = 0
        self.proyectiles = []
        self.golpes_pared = []   # casillas de pared alcanzadas este frame (para los secretos)

    def lanzar(self, x, y, dx, dy, dano=1.0, radio=None, vel=None, perfora=False, tipo="normal", congela=0):
        self.proyectiles.append({"x": x, "y": y, "dx": dx, "dy": dy, "estela": [], "perfora": perfora,
                                 "dano": dano, "radio": radio or self.radio, "vel": vel or self.vel,
                                 "tipo": tipo, "congela": congela, "golpeados": set()})

    def disparar(self, x, y, direccion, multi=False, dano=1.0):
        """multi=True (poder Rafaga): dispara en las 4 direcciones y atraviesa enemigos."""
        if self.espera > 0:
            return False
        for d in (list(DIRS) if multi else [direccion]):
            dx, dy = DIRS[d]
            self.lanzar(x, y, dx, dy, dano, perfora=multi, tipo="multi" if multi else "normal")
        self.espera = 9 if multi else self.cooldown
        return True

    def actualizar(self, particulas):
        if self.espera > 0:
            self.espera -= 1
        self.golpes_pared = []
        vivos = []
        for p in self.proyectiles:
            p["estela"].append((p["x"], p["y"]))
            p["estela"] = p["estela"][-8:]
            p["x"] += p["dx"] * p["vel"]
            p["y"] += p["dy"] * p["vel"]
            r = p["radio"]
            px, py = p["x"] + p["dx"] * r, p["y"] + p["dy"] * r
            if es_pared(px, py):
                self.golpes_pared.append((int(px // TAM), int(py // TAM)))
                chispas(particulas, p["x"], p["y"], COLORES_ATAQUE.get(p["tipo"], (140, 225, 255)), 8, 2.5, 20, 2, 0.0)
                continue
            vivos.append(p)
        self.proyectiles = vivos

    def revisar_impactos(self, enemigos):
        """Devuelve [(enemigo, proyectil)] de los impactos de este frame."""
        res = []
        for p in list(self.proyectiles):
            for e in enemigos:
                if e in p["golpeados"]:
                    continue
                r = e.rect().inflate(8, 8)
                cx = max(r.left, min(p["x"], r.right))
                cy = max(r.top, min(p["y"], r.bottom))
                if (p["x"] - cx) ** 2 + (p["y"] - cy) ** 2 <= p["radio"] ** 2:
                    p["golpeados"].add(e)
                    res.append((e, p))
                    if not p["perfora"]:
                        self.proyectiles.remove(p)
                        break
        return res

    def dibujar(self, m):
        for p in self.proyectiles:
            col = COLORES_ATAQUE.get(p["tipo"], (110, 200, 255))
            n = len(p["estela"])
            r0 = p["radio"]
            for i, (ex, ey) in enumerate(p["estela"]):
                k = (i + 1) / (n + 1)
                pygame.draw.circle(m, mezcla(col, 0.5 + 0.5 * k), (int(ex), int(ey)), max(1, int(r0 * k * 0.8)))
            g = crear_brillo_cache(16 if r0 <= 6 else 26, col)
            m.blit(g, (int(p["x"] - g.get_width() / 2), int(p["y"] - g.get_height() / 2)))
            pygame.draw.circle(m, col, (int(p["x"]), int(p["y"])), r0)
            pygame.draw.circle(m, (255, 255, 255), (int(p["x"]), int(p["y"])), max(2, r0 - 2))


# ======================================================
# Trampas: la "bomba" cambia con cada mundo
# ======================================================
class PlantaCarnivora:
    """Bosque: se queda plantada y se come a los lobos que pasan cerca."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vida = 900          # 15 segundos
        self.mastica = 0
        self.bocados = 0

    def actualizar(self, j):
        self.vida -= 1
        if self.mastica > 0:
            self.mastica -= 1
        else:
            for e in list(j.enemigos):
                if math.hypot(e.cx - self.x, e.cy - self.y) < 28:
                    AUDIO.sfx("matar")
                    chispas(j.particulas, self.x, self.y - 6, (210, 40, 70), 14, 3.5, 30, 3)
                    j.golpear(e, 5, 100, trampa=True)
                    self.mastica = 75
                    self.bocados += 1
                    break
        if self.bocados >= 4 and self.mastica == 0:
            return False
        return self.vida > 0

    def dibujar(self, m, t):
        if self.vida < 120 and (self.vida // 6) % 2 == 0:
            return
        if self.mastica > 55:
            frame = 2
        elif self.mastica > 0:
            frame = 1
        else:
            frame = 1 if (t // 25) % 3 == 0 else 0
        m.blit(SOMBRA, (int(self.x - 12), int(self.y + 6)))
        m.blit(SPR_PLANTA[frame], (int(self.x - 22), int(self.y - 33)))


class CactusTorreta:
    """Desierto: un cactus que dispara espinas en las 4 direcciones."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vida = 660
        self.cd = 20
        self.espinas = []

    def actualizar(self, j):
        self.vida -= 1
        self.cd -= 1
        if self.cd <= 0 and self.vida > 30:
            self.cd = 40
            AUDIO.sfx("disparo")
            for dx, dy in DIRS.values():
                self.espinas.append([self.x, self.y, dx, dy])
        vivas = []
        for p in self.espinas:
            p[0] += p[2] * 7.5
            p[1] += p[3] * 7.5
            if es_pared(p[0] + p[2] * 4, p[1] + p[3] * 4):
                chispas(j.particulas, p[0], p[1], (200, 255, 180), 4, 2, 14, 2, 0.0)
                continue
            impacto = False
            for e in j.enemigos:
                if e.rect().inflate(8, 8).collidepoint(p[0], p[1]):
                    j.golpear(e, 1, 60, trampa=True)
                    impacto = True
                    break
            if not impacto:
                vivas.append(p)
        self.espinas = vivas
        return self.vida > 0 or bool(self.espinas)

    def dibujar(self, m, t):
        for p in self.espinas:
            pygame.draw.line(m, (235, 255, 205), (int(p[0] - p[2] * 5), int(p[1] - p[3] * 5)),
                             (int(p[0] + p[2] * 5), int(p[1] + p[3] * 5)), 3)
            pygame.draw.circle(m, (255, 130, 190), (int(p[0] + p[2] * 5), int(p[1] + p[3] * 5)), 2)
        if self.vida > 0 and not (self.vida < 90 and (self.vida // 6) % 2 == 0):
            m.blit(SPR_CACTUS, (int(self.x - 20), int(self.y - 30)))


class Meteoros:
    """Volcan: llueven meteoritos sobre los enemigos."""

    def __init__(self):
        self.pend = 6
        self.espera = 6
        self.imp = []  # [x, y, frames_restantes]

    def actualizar(self, j):
        self.espera -= 1
        if self.pend > 0 and self.espera <= 0:
            self.espera = 15
            self.pend -= 1
            if j.enemigos:
                objetivo = j.jefe if (j.jefe is not None and random.random() < 0.6) else random.choice(j.enemigos)
                x, y = objetivo.cx, objetivo.cy
            else:
                c = celda_lejana(j.celda_jugador(), 3)
                x, y = c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2
            self.imp.append([x, y, 50])
        resto = []
        for mt in self.imp:
            mt[2] -= 1
            if mt[2] <= 0:
                AUDIO.sfx("bomba")
                chispas(j.particulas, mt[0], mt[1], (255, 150, 40), 28, 5, 40, 5)
                chispas(j.particulas, mt[0], mt[1], (255, 230, 120), 10, 3, 25, 3)
                j.temblor = max(j.temblor, 10)
                j.ondas.append([mt[0], mt[1], 18, 18, (255, 150, 60), 60])
                for e in list(j.enemigos):
                    if math.hypot(e.cx - mt[0], e.cy - mt[1]) < 60:
                        j.golpear(e, 3, 100, trampa=True)
            else:
                resto.append(mt)
        self.imp = resto
        return self.pend > 0 or bool(self.imp)

    def dibujar(self, m, t):
        for x, y, f in self.imp:
            r = int(60 * (0.5 + 0.5 * f / 50))
            pygame.draw.circle(m, (255, 80, 60), (int(x), int(y)), r, 2)
            pygame.draw.circle(m, (255, 170, 90), (int(x), int(y)), max(2, r // 3), 1)
            if f < 28:  # el meteorito cae desde arriba
                caida = (f / 28) ** 1.6 * 260
                pygame.draw.line(m, (255, 190, 80), (int(x), int(y - caida)), (int(x + caida * 0.15), int(y - caida - 44)), 5)
                m.blit(SPR_METEORO, (int(x - 20), int(y - 20 - caida)))


class Avalancha:
    """Glaciar: una bola de nieve gigante que arrasa con todo lo que toca."""

    def __init__(self, x, y, dx, dy):
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.ang = 0

    def actualizar(self, j):
        self.x += self.dx * 6.5
        self.y += self.dy * 6.5
        self.ang += 14 * (self.dx + self.dy)
        if random.random() < 0.5:
            chispas(j.particulas, self.x, self.y, (235, 245, 255), 1, 2.0, 22, 4, 0.0)
        for e in list(j.enemigos):
            if math.hypot(e.cx - self.x, e.cy - self.y) < 28:
                j.golpear(e, 6, 100, trampa=True)
        if es_pared(self.x + self.dx * 20, self.y + self.dy * 20):
            chispas(j.particulas, self.x, self.y, (235, 245, 255), 22, 4, 36, 4)
            j.temblor = max(j.temblor, 6)
            return False
        return True

    def dibujar(self, m, t):
        spr = pygame.transform.rotate(SPR_BOLA, self.ang)
        m.blit(spr, spr.get_rect(center=(int(self.x), int(self.y))))


class MinaLaser:
    """Neon y mundos siguientes: una mina que explota cuando un enemigo se le acerca."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vida = 1500
        self.arma = 45

    def actualizar(self, j):
        self.vida -= 1
        self.arma -= 1
        if self.arma <= 0 and any(math.hypot(e.cx - self.x, e.cy - self.y) < 26 for e in j.enemigos):
            dist = j.dist_desde((int(self.x // TAM), int(self.y // TAM)))
            AUDIO.sfx("bomba")
            j.temblor = max(j.temblor, 14)
            j.ondas.append([self.x, self.y, 26, 26, (90, 235, 255), TAM * 2.5])
            chispas(j.particulas, self.x, self.y, (90, 235, 255), 24, 5, 40, 4)
            chispas(j.particulas, self.x, self.y, (255, 90, 210), 16, 4, 34, 3)
            for e in list(j.enemigos):
                if dist.get(e.celda(), 99) <= 2:
                    j.golpear(e, 8, 100, trampa=True)
            return False
        return self.vida > 0

    def dibujar(self, m, t):
        if self.vida < 90 and (self.vida // 6) % 2 == 0:
            return
        x, y = int(self.x), int(self.y)
        m.blit(SOMBRA, (x - 12, y + 4))
        for k in range(8):
            a = k * math.pi / 4
            pygame.draw.line(m, (120, 130, 150), (x + int(math.cos(a) * 9), y + int(math.sin(a) * 9)),
                             (x + int(math.cos(a) * 13), y + int(math.sin(a) * 13)), 2)
        pygame.draw.circle(m, (70, 74, 92), (x, y), 10)
        pygame.draw.circle(m, (34, 36, 50), (x, y), 8)
        if self.arma > 0:
            luz = (255, 80, 80) if (t // 8) % 2 == 0 else (90, 30, 30)
        else:
            luz = (90, 235, 255) if (t // 15) % 2 == 0 else (255, 90, 210)
        pygame.draw.circle(m, luz, (x, y), 4)


# ======================================================
# Objetos del suelo: monedas, cofres, fragmentos de historia
# ======================================================
class Moneda:
    """Frutacoin: moneda del juego. Se queda un rato en el suelo."""

    def __init__(self, x, y, valor=1, ttl=1000, vx=0.0, vy=0.0):
        self.x, self.y, self.valor, self.ttl = x, y, valor, ttl
        self.vx, self.vy = vx, vy
        self.fase = random.uniform(0, math.tau)

    def actualizar(self, j):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.9
        self.vy *= 0.9
        if es_pared(self.x, self.y):
            self.x -= self.vx * 3
            self.y -= self.vy * 3
            self.vx = self.vy = 0
        self.ttl -= 1
        return self.ttl > 0

    def dibujar(self, m, t):
        if self.ttl < 150 and (self.ttl // 5) % 2 == 0:
            return
        w = max(3, int(22 * abs(math.cos(t * 0.09 + self.fase))))
        bob = math.sin(t * 0.08 + self.fase) * 2
        g = BRILLO_MONEDA
        g.set_alpha(150)
        m.blit(g, (int(self.x - 18), int(self.y - 18 + bob)))
        spr = pygame.transform.scale(SPR_MONEDA, (w, 22)) if self.valor == 1 else pygame.transform.scale(SPR_MONEDA, (int(w * 1.3), 29))
        m.blit(spr, (int(self.x - spr.get_width() / 2), int(self.y - spr.get_height() / 2 + bob)))


class Cofre:
    """Cofre de una habitacion secreta."""

    def __init__(self, x, y, monedas, puntos=500, fragmento=None, poder=None):
        self.x, self.y = x, y
        self.monedas, self.puntos, self.fragmento, self.poder = monedas, puntos, fragmento, poder
        self.abierto = False

    def dibujar(self, m, t):
        if not self.abierto:
            g = crear_brillo_cache(30, (255, 215, 80))
            g.set_alpha(int(120 + 80 * math.sin(t * 0.07)))
            m.blit(g, (int(self.x - 30), int(self.y - 30)))
        m.blit(SOMBRA, (int(self.x - 12), int(self.y + 8)))
        m.blit(SPR_COFRE[1 if self.abierto else 0], (int(self.x - 15), int(self.y - 17)))


class Fragmento:
    """Pergamino con un trozo de la historia."""

    def __init__(self, x, y, id_):
        self.x, self.y, self.id = x, y, id_

    def dibujar(self, m, t):
        g = crear_brillo_cache(26, (255, 235, 150))
        g.set_alpha(int(110 + 90 * math.sin(t * 0.08)))
        m.blit(g, (int(self.x - 26), int(self.y - 26)))
        m.blit(SPR_PERGAMINO, (int(self.x - 13), int(self.y - 13 + math.sin(t * 0.07) * 3)))


# ======================================================
# Peligros: impactos con aviso, pinchos, cuchillas
# ======================================================
class Impacto:
    """Algo cae (roca, rayo, charco...) en un punto: primero avisa y luego golpea."""

    def __init__(self, x, y, retardo=60, radio=30, color=(255, 120, 60), dej_lava=0, dano_enemigos=0, sonido="bomba"):
        self.x, self.y, self.t0 = x, y, retardo
        self.t = retardo
        self.radio, self.color, self.dej_lava = radio, color, dej_lava
        self.dano_enemigos, self.sonido = dano_enemigos, sonido

    def actualizar(self, j):
        self.t -= 1
        if self.t > 0:
            return True
        AUDIO.sfx(self.sonido)
        chispas(j.particulas, self.x, self.y, self.color, 22, 5, 36, 4)
        chispas(j.particulas, self.x, self.y, (255, 255, 255), 8, 3, 22, 2)
        j.ondas.append([self.x, self.y, 16, 16, self.color, self.radio * 1.5])
        j.temblor = max(j.temblor, 8)
        cx, cy = j.centro_jugador()
        if math.hypot(cx - self.x, cy - self.y) < self.radio + 6 and j.vulnerable():
            j.golpe("impacto")
        if self.dano_enemigos:
            for e in list(j.enemigos):
                if not e.es_jefe and math.hypot(e.cx - self.x, e.cy - self.y) < self.radio + 10:
                    j.golpear(e, self.dano_enemigos, 100, trampa=True)
        if self.dej_lava:
            j.lavas.append([self.x, self.y, self.dej_lava, self.color])
        return False

    def dibujar(self, m, t):
        k = self.t / max(1, self.t0)
        r = int(self.radio * (0.4 + 0.6 * (1 - k)))
        a = 255 if (self.t // 4) % 2 == 0 else 150
        pygame.draw.circle(m, mezcla(self.color, 0.9), (int(self.x), int(self.y)), self.radio, 2)
        pygame.draw.circle(m, self.color, (int(self.x), int(self.y)), max(2, r), 0 if self.t < 14 else 1)
        if self.t < 26:  # el objeto cae desde arriba
            caida = (self.t / 26) ** 1.5 * 240
            pygame.draw.circle(m, (255, 255, 255), (int(self.x), int(self.y - caida)), 7)
            pygame.draw.circle(m, self.color, (int(self.x), int(self.y - caida)), 5)
            pygame.draw.line(m, self.color, (int(self.x), int(self.y - caida)), (int(self.x), int(self.y - caida - 30)), 3)


class Pinchos:
    """Pinchos que salen y se esconden. Hacen dano al jugador y a los enemigos normales."""
    CICLO = 210

    def __init__(self, celdas):
        self.celdas = [(c, random.randrange(self.CICLO)) for c in celdas]
        self.golpeados = {}

    def estado(self, t, off):
        f = (t + off) % self.CICLO
        return 0 if f < 110 else (1 if f < 140 else 2)

    def actualizar(self, j):
        cx, cy = j.centro_jugador()
        for c, off in self.celdas:
            est = self.estado(j.t, off)
            if est == 2:
                px, py = c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2
                if (j.t + off) % self.CICLO == 140:
                    AUDIO.sfx("pinchos")
                if abs(cx - px) < 14 and abs(cy - py) < 14 and j.vulnerable():
                    j.golpe("pinchos")
                for e in list(j.enemigos):
                    if not e.es_jefe and e.tipo != TIPO_CAZADOR and abs(e.cx - px) < 12 and abs(e.cy - py) < 12:
                        if self.golpeados.get(id(e), -99) < j.t - 60:
                            self.golpeados[id(e)] = j.t
                            j.golpear(e, 99, 100, trampa=True)

    def dibujar(self, m, t):
        for c, off in self.celdas:
            est = self.estado(t, off)
            x, y = c[0] * TAM, c[1] * TAM
            pygame.draw.rect(m, (46, 46, 62), (x + 6, y + 6, TAM - 12, TAM - 12), border_radius=3)
            for i in range(3):
                for k in range(3):
                    px, py = x + 10 + i * 10, y + 10 + k * 10
                    if est == 0:
                        pygame.draw.circle(m, (20, 20, 30), (px, py), 2)
                    else:
                        alt = 5 if est == 1 else 12
                        col = (255, 90, 90) if est == 1 else (225, 230, 240)
                        pygame.draw.polygon(m, col, [(px - 3, py + 2), (px + 3, py + 2), (px, py + 2 - alt)])


class Cuchilla:
    """Sierra giratoria que patrulla un pasillo recto (dimension oculta)."""

    def __init__(self, seg, eje):
        self.pts = sorted(seg)
        if eje == "v":
            self.pts = sorted(seg, key=lambda c: c[1])
        self.a = (self.pts[0][0] * TAM + TAM / 2, self.pts[0][1] * TAM + TAM / 2)
        self.b = (self.pts[-1][0] * TAM + TAM / 2, self.pts[-1][1] * TAM + TAM / 2)
        self.k = random.random()
        self.dir = 1
        self.ang = 0

    def pos(self):
        return (self.a[0] + (self.b[0] - self.a[0]) * self.k, self.a[1] + (self.b[1] - self.a[1]) * self.k)

    def actualizar(self, j):
        largo = max(1.0, math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1]))
        self.k += self.dir * 2.0 / largo
        if self.k >= 1 or self.k <= 0:
            self.k = max(0.0, min(1.0, self.k))
            self.dir *= -1
        self.ang += 14
        x, y = self.pos()
        cx, cy = j.centro_jugador()
        if math.hypot(cx - x, cy - y) < 17 and j.vulnerable():
            j.golpe("cuchilla")
        for e in list(j.enemigos):
            if not e.es_jefe and e.tipo != TIPO_CAZADOR and math.hypot(e.cx - x, e.cy - y) < 16:
                j.golpear(e, 99, 100, trampa=True)

    def dibujar(self, m, t):
        x, y = self.pos()
        pygame.draw.line(m, (60, 20, 40), self.a, self.b, 2)
        pts = []
        for i in range(16):
            r = 15 if i % 2 == 0 else 9
            a = math.radians(self.ang) + i * math.pi / 8
            pts.append((x + r * math.cos(a), y + r * math.sin(a)))
        pygame.draw.polygon(m, (200, 205, 220), pts)
        pygame.draw.circle(m, (255, 90, 120), (int(x), int(y)), 5)
        pygame.draw.circle(m, (90, 20, 40), (int(x), int(y)), 2)


# ======================================================
# Mascotas
# ======================================================
class Mascota:
    """Acompana al jugador (sigue su rastro) con animacion sencilla."""

    def __init__(self, id_, x, y):
        self.id = id_
        self.x, self.y = x, y
        self.hist = [(x, y)] * 24
        self.izq = False
        self.salto = 0
        self.obj = None

    def actualizar(self, j):
        cx, cy = j.centro_jugador()
        self.hist.append((cx, cy))
        self.hist = self.hist[-26:]
        tx, ty = self.hist[0]
        self.obj = None
        if self.id == "perro" and j.monedas_suelo:  # el perro corre a por las monedas cercanas
            cerca = [mo for mo in j.monedas_suelo if math.hypot(mo.x - cx, mo.y - cy) < 150]
            if cerca:
                self.obj = min(cerca, key=lambda mo: math.hypot(mo.x - self.x, mo.y - self.y))
                tx, ty = self.obj.x, self.obj.y
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        v = 4.2 if self.obj else 3.6
        if d > 1:
            paso = min(d, v if d > 6 else d * 0.5)
            self.x += dx / d * paso
            self.y += dy / d * paso
            if abs(dx) > 1.5:
                self.izq = dx < 0
        if self.obj is not None and math.hypot(self.obj.x - self.x, self.obj.y - self.y) < 14:
            j.recoger_moneda(self.obj)
            AUDIO.sfx("pet")
            self.salto = 14
        if self.salto > 0:
            self.salto -= 1
        if self.id == "dragon" and j.t % 90 == 0 and j.arma.proyectiles:
            chispas(j.particulas, self.x, self.y - 6, (255, 150, 50), 4, 1.8, 18, 3, -0.02)
        if self.id == "zorro" and j.moviendo and j.t % 6 == 0:
            chispas(j.particulas, self.x, self.y + 6, (255, 190, 120), 1, 1.0, 14, 2, 0.0)
        if self.id == "gato" and j.t % 120 == 0:
            chispas(j.particulas, self.x, self.y - 10, (255, 230, 120), 3, 1.2, 20, 2, -0.03)

    def dibujar(self, m, t):
        bob = abs(math.sin(t * 0.18)) * 3 if (math.hypot(self.x - self.hist[-1][0], self.y - self.hist[-1][1]) > 18 or self.obj) else math.sin(t * 0.08)
        s = sprite_mascota(self.id, t // 8, 30, self.izq)
        m.blit(SOMBRA, (int(self.x - 12), int(self.y + 8)))
        m.blit(s, (int(self.x - 15), int(self.y - 20 - bob - (self.salto if self.salto > 7 else 14 - self.salto) * 0.4)))


# ======================================================
# Ambiente visual de cada mundo (particulas decorativas)
# ======================================================
class Ambiente:
    def __init__(self, mundo):
        self.mundo = mundo
        self.p = []
        for _ in range(26):
            self.p.append(self.nueva(True))

    def nueva(self, inicial=False):
        m = self.mundo
        x = random.uniform(0, ANCHO)
        y = random.uniform(0, ALTO_MAPA) if inicial else random.uniform(-10, ALTO_MAPA)
        base = dict(x=x, y=y, f=random.uniform(0, math.tau), r=random.uniform(1.5, 3.2))
        if m == 0:      # polvo de la cripta
            base.update(vx=random.uniform(-0.1, 0.1), vy=-random.uniform(0.1, 0.3), c=(150, 155, 190), a=90)
        elif m == 1:    # luciernagas
            base.update(vx=random.uniform(-0.4, 0.4), vy=random.uniform(-0.3, 0.3), c=(200, 255, 120), a=200, brilla=True)
        elif m == 2:    # arena al viento
            base.update(vx=random.uniform(1.2, 2.6), vy=random.uniform(-0.1, 0.3), c=(235, 200, 140), a=120, r=1.4)
        elif m == 3:    # ascuas
            base.update(vx=random.uniform(-0.3, 0.3), vy=-random.uniform(0.5, 1.4), c=(255, random.randint(100, 190), 50), a=220)
        elif m == 4:    # nieve
            base.update(vx=random.uniform(-0.5, 0.2), vy=random.uniform(0.6, 1.4), c=(240, 250, 255), a=200)
        elif m == 5:    # chispas de neon
            base.update(vx=random.uniform(-0.6, 0.6), vy=random.uniform(-0.6, 0.6), c=random.choice(((255, 90, 210), (90, 230, 255))), a=200, brilla=True)
        elif m == 6:    # burbujas y esporas
            base.update(vx=random.uniform(-0.15, 0.15), vy=-random.uniform(0.2, 0.6), c=(170, 230, 120), a=130)
        elif m == 7:    # gotas y polvo de cristal
            base.update(vx=0.0, vy=random.uniform(0.8, 2.0), c=(150, 130, 230), a=140, r=1.3)
        elif m == 8:    # nubes
            base.update(vx=random.uniform(0.2, 0.6), vy=0.0, c=(255, 255, 255), a=45, r=random.uniform(14, 28), nube=True)
        elif m == 9:    # motas del vacio
            base.update(vx=random.uniform(-0.3, 0.3), vy=-random.uniform(0.1, 0.5), c=(150, 100, 240), a=170, brilla=True)
        else:           # petalos / latidos
            base.update(vx=random.uniform(-0.4, 0.4), vy=-random.uniform(0.3, 0.9), c=(255, 90, 130), a=190, r=random.uniform(2, 4))
        return base

    def actualizar(self):
        for q in self.p:
            q["x"] += q["vx"] + math.sin(q["f"] + q["y"] * 0.02) * 0.2
            q["y"] += q["vy"]
            if q["x"] > ANCHO + 30 or q["x"] < -30 or q["y"] > ALTO_MAPA + 30 or q["y"] < -30:
                nuevo = self.nueva()
                if self.mundo in (3, 6, 9, 10):
                    nuevo["y"] = ALTO_MAPA + 10
                elif self.mundo in (4, 7):
                    nuevo["y"] = -10
                elif self.mundo in (2, 8):
                    nuevo["x"] = -20
                q.update(nuevo)

    def dibujar(self, m, t):
        for q in self.p:
            a = q["a"]
            if q.get("brilla"):
                a = int(a * (0.4 + 0.6 * abs(math.sin(t * 0.05 + q["f"]))))
            if q.get("nube"):
                sup = pygame.Surface((int(q["r"] * 4), int(q["r"] * 1.6)), pygame.SRCALPHA)
                pygame.draw.ellipse(sup, (*q["c"], a), sup.get_rect())
                m.blit(sup, (int(q["x"]), int(q["y"])))
            else:
                r = max(1, int(q["r"]))
                sup = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(sup, (*q["c"], a), (r + 1, r + 1), r)
                m.blit(sup, (int(q["x"]), int(q["y"])))


# ======================================================
# Eventos aleatorios
# ======================================================
EVENTOS_DEF = {
    "oscuridad": dict(nombre="MODO OSCURIDAD", color=(170, 140, 255), dur=900, texto="Apenas ves a tu alrededor..."),
    "lluvia_frutas": dict(nombre="LLUVIA DE FRUTAS", color=(255, 150, 130), dur=720, texto="¡Frutas por todas partes!"),
    "invasion": dict(nombre="INVASIÓN", color=(255, 90, 90), dur=1500, texto="¡Aparecen muchos enemigos!"),
    "contrarreloj": dict(nombre="CONTRARRELOJ", color=(255, 235, 100), dur=0, texto="¡Llega a la bandera antes de que acabe el tiempo!"),
    "tormenta": dict(nombre="TORMENTA", color=(160, 200, 255), dur=960, texto="Rayos y viento sacuden el laberinto"),
    "lluvia_monedas": dict(nombre="LLUVIA DE MONEDAS", color=(255, 220, 80), dur=620, texto="¡Recoge todas las monedas!"),
}


class GestorEventos:
    """Un evento aleatorio cada cierto tiempo. Cada partida es distinta."""

    def __init__(self, j):
        self.j = j
        self.activo = None
        self.aviso = 0
        self.elegido = None
        self.cuenta = int(j.dif["eventos"] * random.uniform(0.45, 0.8)) + 420
        self.recibio_dano = False
        self.bandera = None
        self.ultimo = None

    def permitidos(self):
        j = self.j
        ops = ["lluvia_monedas", "tormenta", "lluvia_frutas", "invasion", "contrarreloj", "oscuridad"]
        if j.mundo == 7:
            ops.remove("oscuridad")   # la cueva ya es oscura
        if j.es_jefe:
            ops = [o for o in ops if o in ("lluvia_monedas", "tormenta", "oscuridad")]
        if j.nivel < 3:
            ops = [o for o in ops if o in ("lluvia_monedas", "lluvia_frutas")]
        elif j.nivel < 6:
            ops = [o for o in ops if o != "invasion"]
        if self.ultimo in ops and len(ops) > 1:
            ops.remove(self.ultimo)
        return ops

    def actualizar(self):
        j = self.j
        if self.aviso > 0:
            self.aviso -= 1
            if self.aviso == 0:
                self.iniciar(self.elegido)
            return
        if self.activo:
            self.tick()
            return
        if j.estado_nivel != "jugando" or (j.jefe and j.jefe.fase_t < 150):
            return
        self.cuenta -= 1
        if self.cuenta <= 0:
            self.elegido = random.choice(self.permitidos())
            self.aviso = 100
            AUDIO.sfx("evento")
            j.flash((255, 220, 120), 70)

    # ---------- inicio ----------
    def iniciar(self, tipo):
        j = self.j
        d = EVENTOS_DEF[tipo]
        self.ultimo = tipo
        self.recibio_dano = False
        self.activo = dict(tipo=tipo, t=d["dur"], dur=d["dur"], nombre=d["nombre"], color=d["color"])
        j.banner(d["nombre"], d["color"], d["texto"])
        if tipo == "invasion":
            n = min(10, 5 + j.nivel // 8)
            celdas = [c for c, dd in j.dist_jugador.items() if dd >= 8]
            random.shuffle(celdas)
            for c in celdas[:n]:
                e = j.nuevo_enemigo(c, j.tipo_enemigo(random.randrange(12)))
                e.invasor = d["dur"]
                j.enemigos.append(e)
                chispas(j.particulas, e.cx, e.cy, (255, 90, 90), 12, 3, 30, 3)
            j.temblor = max(j.temblor, 16)
        elif tipo == "contrarreloj":
            celdas = sorted(j.dist_jugador.items(), key=lambda kv: -kv[1])
            top = [c for c, dd in celdas[:max(3, len(celdas) // 8)] if dd >= 12] or [celdas[0][0]]
            meta = random.choice(top)
            dist = j.dist_jugador.get(meta, 20)
            limite = int(dist * (TAM / (VEL_JUGADOR * 1.05)) * 1.35) + 150
            self.bandera = meta
            self.activo.update(t=limite, dur=limite)
        elif tipo == "oscuridad":
            AUDIO.sfx("trueno")

    # ---------- cada frame ----------
    def tick(self):
        j = self.j
        a = self.activo
        a["t"] -= 1
        tipo = a["tipo"]
        if tipo == "lluvia_frutas" and a["t"] % 14 == 0 and len(j.frutas_extra) < 26:
            cs = [c for c, dd in j.dist_jugador.items() if dd >= 2 and c not in j.celdas_ocupadas()]
            if cs:
                c = random.choice(cs)
                j.frutas_extra.append(Fruta(c, random.randrange(N_FRUTAS_NORMALES), ttl=720))
        elif tipo == "lluvia_monedas" and a["t"] % 9 == 0 and len(j.monedas_suelo) < 50:
            cs = [c for c, dd in j.dist_jugador.items() if dd >= 1]
            if cs:
                c = random.choice(cs)
                j.monedas_suelo.append(Moneda(c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2, 1, 800))
        elif tipo == "tormenta":
            if a["t"] % 38 == 0:
                cx, cy = j.centro_jugador()
                if random.random() < 0.6:
                    x, y = cx + random.uniform(-110, 110), cy + random.uniform(-110, 110)
                else:
                    c = random.choice(list(j.dist_jugador))
                    x, y = c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2
                if not es_pared(x, y):
                    j.impactos.append(Impacto(x, y, 52, 30, (190, 220, 255), dej_lava=200, dano_enemigos=99, sonido="trueno"))
        elif tipo == "contrarreloj":
            px, py = self.bandera[0] * TAM + TAM / 2, self.bandera[1] * TAM + TAM / 2
            cx, cy = j.centro_jugador()
            if math.hypot(cx - px, cy - py) < 20:
                j.sumar_puntos(500, px, py)
                j.dar_monedas(12 + j.nivel // 3, px, py)
                j.ganar_furia(20)
                self.terminar(True, "¡A TIEMPO!")
                return
        if a["t"] <= 0:
            if tipo == "contrarreloj":
                self.terminar(False, "¡TIEMPO AGOTADO!")
            else:
                self.terminar(True, "¡EVENTO SUPERADO!")

    def terminar(self, ok, msg):
        j = self.j
        a = self.activo
        tipo = a["tipo"]
        self.activo = None
        self.bandera = None
        self.cuenta = int(j.dif["eventos"] * random.uniform(0.75, 1.3))
        if tipo == "invasion":
            for e in list(j.enemigos):
                if e.invasor:
                    chispas(j.particulas, e.cx, e.cy, (255, 255, 255), 8, 2, 20, 2)
                    j.enemigos.remove(e)
        if ok:
            j.texto_flotante(*j.centro_jugador(), msg, (140, 255, 160), F_MED, 80)
            if tipo != "contrarreloj":
                j.dar_monedas(4 + j.nivel // 8, *j.centro_jugador())
            j.stat("eventos", 1)
            AUDIO.sfx("nivel")
        else:
            j.texto_flotante(*j.centro_jugador(), msg, (255, 120, 120), F_MED, 90)
            AUDIO.sfx("error")
            j.combo = 0
            for _ in range(2):
                cs = [c for c, dd in j.dist_jugador.items() if 6 <= dd <= 14]
                if cs:
                    e = j.nuevo_enemigo(random.choice(cs), j.tipo_enemigo(random.randrange(6)))
                    j.enemigos.append(e)

    def niebla(self):
        if self.activo and self.activo["tipo"] == "oscuridad":
            return dict(tipo="oscuro", radio=100, color=(4, 2, 14), alfa=240)
        if self.activo and self.activo["tipo"] == "tormenta":
            return dict(tipo="tormenta", radio=None, color=(20, 28, 50), alfa=70)
        return None

    def dibujar(self, m, t):
        if self.bandera:
            px, py = self.bandera[0] * TAM + TAM / 2, self.bandera[1] * TAM + TAM / 2
            g = crear_brillo_cache(40, (255, 230, 90))
            g.set_alpha(int(150 + 90 * math.sin(t * 0.15)))
            m.blit(g, (int(px - 40), int(py - 40)))
            pygame.draw.line(m, (230, 230, 240), (int(px - 6), int(py + 14)), (int(px - 6), int(py - 16)), 3)
            pygame.draw.polygon(m, (255, 220, 60), [(px - 4, py - 16), (px + 12 + math.sin(t * 0.2) * 3, py - 10), (px - 4, py - 4)])
            pygame.draw.circle(m, (255, 230, 90), (int(px), int(py)), 24 + int(3 * math.sin(t * 0.2)), 2)


# ======================================================
# Mecanicas unicas de cada mundo
# ======================================================
class Mec:
    """Base: cada mundo hereda y cambia las reglas del juego."""
    inercia = False
    nombre = "Laberinto clasico"

    def __init__(self, j):
        self.j = j
        self.pend = []        # cambios de pared programados
        self._cf = self._df = -1
        self.cambios_t = 0
        self.pinchos = None
        self.iniciar()

    # --- hooks ---
    def iniciar(self):
        pass

    def actualizar(self):
        pass

    def mult_vel(self, celda):
        return 1.0

    def friccion_en(self, celda):
        return None

    def niebla(self):
        return None

    def ocupadas(self):
        return set()

    def dibujar_suelo(self, m, t):
        pass

    def dibujar_encima(self, m, t):
        pass

    def al_golpear_jefe_fase(self, fase):
        pass

    # --- utilidades comunes ---
    def crear_pinchos(self, n):
        j = self.j
        if n <= 0:
            return
        ocup = j.celdas_bloqueadas_spawn() | self.ocupadas()
        cand = [c for c, d in DIST_INICIO.items() if d >= 6 and c not in ocup]
        random.shuffle(cand)
        self.pinchos = Pinchos(cand[:n])

    def programar_cambios(self, n, tiempo=70):
        j = self.j
        ya = {p["celda"] for p in self.pend}
        abrir = [c for c in paredes_abribles() if c not in ya]
        random.shuffle(abrir)
        cerrar = [c for c in pasillos_cerrables(j.celdas_ocupadas(1) | ya, 10)]
        for _ in range(n):
            if cerrar and (not abrir or random.random() < 0.5):
                self.pend.append(dict(celda=cerrar.pop(), accion="cerrar", t=tiempo))
            elif abrir:
                self.pend.append(dict(celda=abrir.pop(), accion="abrir", t=tiempo))
        if self.pend:
            AUDIO.sfx("alerta")

    def actualizar_cambios(self):
        j = self.j
        if self._cf == j.t:
            return
        self._cf = j.t
        hecho = False
        for p in self.pend[:]:
            p["t"] -= 1
            if p["t"] > 0:
                continue
            self.pend.remove(p)
            x, y = p["celda"]
            px, py = x * TAM + TAM / 2, y * TAM + TAM / 2
            if p["accion"] == "abrir":
                if MAPA[y][x] == "#" and (x, y) not in SECRETAS and (x, y) not in PROTEGIDAS:
                    poner_celda(x, y, ".")
                    hecho = True
                    chispas(j.particulas, px, py, (160, 255, 220), 14, 3, 30, 3)
            elif MAPA[y][x] != "#" and p["celda"] not in j.celdas_ocupadas(1):
                base = len(distancias(CELDA_INICIAL))
                poner_celda(x, y, "#")
                if len(distancias(CELDA_INICIAL)) == base - 1:
                    hecho = True
                    chispas(j.particulas, px, py, (255, 120, 100), 14, 3, 30, 3)
                else:
                    poner_celda(x, y, ".")
        if hecho:
            recalcular_mapa()
            j.cache_dist.clear()
            j.rehacer_fondo()
            for e in j.enemigos:
                e.destino = None
            j.temblor = max(j.temblor, 6)
            AUDIO.sfx("lava")

    def dibujar_cambios(self, m, t):
        if self._df == t:
            return
        self._df = t
        for p in self.pend:
            x, y = p["celda"]
            col = (255, 90, 90) if p["accion"] == "cerrar" else (120, 255, 200)
            a = 80 + int(90 * abs(math.sin(t * 0.25)))
            sup = pygame.Surface((TAM, TAM), pygame.SRCALPHA)
            sup.fill((*col, a // 2))
            pygame.draw.rect(sup, (*col, a + 60), sup.get_rect(), 2)
            m.blit(sup, (x * TAM, y * TAM))


class MecCripta(Mec):
    nombre = "Laberinto clásico"

    def iniciar(self):
        self.crear_pinchos(min(self.j.dif["trampas"], 8))

    def actualizar(self):
        if self.pinchos:
            self.pinchos.actualizar(self.j)

    def dibujar_suelo(self, m, t):
        if self.pinchos:
            self.pinchos.dibujar(m, t)


class MecBosque(Mec):
    nombre = "Laberinto cambiante"

    def iniciar(self):
        self.crear_pinchos(self.j.dif["trampas"] // 3)
        self.cambios_t = 300

    def actualizar(self):
        j = self.j
        if self.pinchos:
            self.pinchos.actualizar(j)
        self.cambios_t -= 1
        if self.cambios_t <= 0:
            self.programar_cambios(2 + min(4, j.nivel // 8))
            self.cambios_t = max(150, 340 - 5 * j.nivel)
        self.actualizar_cambios()

    def dibujar_suelo(self, m, t):
        if self.pinchos:
            self.pinchos.dibujar(m, t)
        self.dibujar_cambios(m, t)


class MecDesierto(Mec):
    nombre = "Tormentas de arena"

    def iniciar(self):
        self.crear_pinchos(self.j.dif["trampas"] // 3)
        self.estado = "calma"
        self.timer = random.randint(420, 700)
        self.forzada = False
        self.rayas = [[random.uniform(0, ANCHO), random.uniform(0, ALTO_MAPA), random.uniform(10, 24)] for _ in range(50)]

    def intensidad(self):
        if self.forzada or self.estado == "tormenta":
            return 1.0
        if self.estado == "aviso":
            return 1 - self.timer / 90
        return 0.0

    def actualizar(self):
        j = self.j
        if self.pinchos:
            self.pinchos.actualizar(j)
        self.timer -= 1
        if self.timer <= 0:
            if self.estado == "calma":
                self.estado, self.timer = "aviso", 90
                j.banner("¡TORMENTA DE ARENA!", (235, 190, 110), "Se acerca una tormenta...")
                AUDIO.sfx("alerta")
            elif self.estado == "aviso":
                self.estado, self.timer = "tormenta", 420
                self.programar_cambios(2 + j.nivel // 15, 40)
                AUDIO.sfx("trueno")
            else:
                self.estado, self.timer = "calma", random.randint(600, 950 - 8 * j.nivel)
        self.actualizar_cambios()
        if self.intensidad() > 0:
            for r in self.rayas:
                r[0] += r[2] * (0.4 + self.intensidad())
                if r[0] > ANCHO + 30:
                    r[0] = -30
                    r[1] = random.uniform(0, ALTO_MAPA)

    def mult_vel(self, celda):
        return 1.0 - 0.2 * self.intensidad() if self.estado == "tormenta" or self.forzada else 1.0

    def niebla(self):
        k = self.intensidad()
        if k <= 0:
            return None
        return dict(tipo="arena", radio=int(900 - 700 * k), color=(212, 168, 98), alfa=int(190 * k))

    def dibujar_suelo(self, m, t):
        if self.pinchos:
            self.pinchos.dibujar(m, t)
        self.dibujar_cambios(m, t)

    def dibujar_encima(self, m, t):
        k = self.intensidad()
        if k > 0:
            for x, y, v in self.rayas[:int(50 * k) + 1]:
                pygame.draw.line(m, (240, 210, 150), (int(x), int(y)), (int(x - v * 1.6), int(y + 2)), 1)


class MecVolcan(Mec):
    nombre = "Suelo peligroso"

    def iniciar(self):
        j = self.j
        ocup = j.celdas_bloqueadas_spawn()
        cand = [c for c in pasillos_cerrables(ocup, 40) if DIST_INICIO.get(c, 0) >= 5]
        self.lava = set(cand[:min(4 + j.dif["trampas"] // 2, 11)])
        zs = [c for c, d in DIST_INICIO.items() if d >= 9 and c not in self.lava and c not in ocup]
        random.shuffle(zs)
        self.zonas = zs[:2 + j.nivel // 20]
        self.calor = 0
        self.t_roca = 220
        self.t_erup = 1100
        self.golpes = {}

    def ocupadas(self):
        return set(self.lava)

    def en_zona(self, celda):
        return any(abs(celda[0] - z[0]) <= 1 and abs(celda[1] - z[1]) <= 1 for z in self.zonas)

    def actualizar(self):
        j = self.j
        c = j.celda_jugador()
        if c in self.lava and j.vulnerable():
            j.golpe("lava")
        for e in list(j.enemigos):
            if not e.es_jefe and e.tipo != TIPO_CAZADOR and e.celda() in self.lava and self.golpes.get(id(e), -99) < j.t - 40:
                self.golpes[id(e)] = j.t
                j.golpear(e, 99, 100, trampa=True)
        if self.en_zona(c):
            self.calor += 1
            if self.calor >= 170:
                self.calor = 0
                if j.vulnerable():
                    j.golpe("calor")
        else:
            self.calor = max(0, self.calor - 2)
        self.t_roca -= 1
        if self.t_roca <= 0:
            self.t_roca = max(70, 190 - 3 * j.nivel)
            cx, cy = j.centro_jugador()
            if random.random() < 0.55:
                x, y = cx + random.uniform(-90, 90), cy + random.uniform(-90, 90)
            else:
                cc = random.choice(list(j.dist_jugador))
                x, y = cc[0] * TAM + TAM / 2, cc[1] * TAM + TAM / 2
            if not es_pared(x, y):
                j.impactos.append(Impacto(x, y, 55, 32, (255, 150, 70), dano_enemigos=99))
        self.t_erup -= 1
        if self.t_erup <= 0:
            self.t_erup = random.randint(900, 1300)
            j.banner("¡ERUPCIÓN!", (255, 120, 50), "¡Aléjate de la lava!")
            j.temblor = max(j.temblor, 30)
            AUDIO.sfx("trueno")
            for _ in range(4 + j.nivel // 15):
                cc = random.choice(list(j.dist_jugador))
                j.impactos.append(Impacto(cc[0] * TAM + TAM / 2, cc[1] * TAM + TAM / 2, 75, 44, (255, 100, 40), dej_lava=260, dano_enemigos=99))

    def dibujar_suelo(self, m, t):
        for z in self.zonas:
            sup = pygame.Surface((TAM * 3, TAM * 3), pygame.SRCALPHA)
            a = 55 + int(35 * math.sin(t * 0.1))
            pygame.draw.rect(sup, (255, 70, 30, a), sup.get_rect(), border_radius=12)
            for i in range(4):
                x = (i * 31 + t * 0.6) % (TAM * 3)
                pygame.draw.line(sup, (255, 200, 120, 90), (x, TAM * 3), (x + 6, TAM * 3 - 22 - 8 * math.sin(t * 0.1 + i)), 2)
            m.blit(sup, ((z[0] - 1) * TAM, (z[1] - 1) * TAM))
        for c in self.lava:
            x, y = c[0] * TAM, c[1] * TAM
            pygame.draw.rect(m, (110, 20, 8), (x, y, TAM, TAM))
            pygame.draw.rect(m, (225, 80, 20), (x + 2, y + 2, TAM - 4, TAM - 4), border_radius=5)
            for i in range(3):
                bx = x + 8 + i * 12 + math.sin(t * 0.06 + i * 2 + c[0]) * 4
                by = y + 10 + i * 8 + math.cos(t * 0.05 + i + c[1]) * 4
                pygame.draw.circle(m, (255, 190, 60), (int(bx), int(by)), 5 + int(2 * math.sin(t * 0.1 + i)))
            pygame.draw.rect(m, (255, 210, 120), (x + 2, y + 2, TAM - 4, TAM - 4), 1, border_radius=5)

    def dibujar_encima(self, m, t):
        if self.calor > 0:
            cx, cy = self.j.centro_jugador()
            pygame.draw.rect(m, (30, 10, 10), (int(cx - 14), int(cy - 24), 28, 5))
            pygame.draw.rect(m, (255, 100 + int(100 * (1 - self.calor / 170)), 40), (int(cx - 14), int(cy - 24), int(28 * self.calor / 170), 5))


class MecGlaciar(Mec):
    nombre = "Deslizamiento"
    inercia = True

    def iniciar(self):
        j = self.j
        self.crear_pinchos(0)
        cs = [c for c in DIST_INICIO if c != CELDA_INICIAL]
        random.shuffle(cs)
        self.nieve = set()
        for s in cs[:12]:
            self.nieve.add(s)
            for dc, df in VECINOS:
                if random.random() < 0.5 and (s[0] + dc, s[1] + df) in DIST_INICIO:
                    self.nieve.add((s[0] + dc, s[1] + df))
        self.nieve.add(CELDA_INICIAL)
        self.capa = pygame.Surface((ANCHO, ALTO_MAPA), pygame.SRCALPHA)
        rnd = random.Random(j.semilla)
        for c in DIST_INICIO:
            x, y = c[0] * TAM, c[1] * TAM
            if c in self.nieve:
                pygame.draw.rect(self.capa, (245, 250, 255, 150), (x + 2, y + 2, TAM - 4, TAM - 4), border_radius=9)
                for _ in range(4):
                    pygame.draw.circle(self.capa, (255, 255, 255, 190), (x + rnd.randint(6, 34), y + rnd.randint(6, 34)), rnd.randint(1, 3))
            else:
                pygame.draw.rect(self.capa, (190, 235, 255, 46), (x, y, TAM, TAM))
                for _ in range(2):
                    px, py = x + rnd.randint(4, 30), y + rnd.randint(4, 30)
                    pygame.draw.line(self.capa, (255, 255, 255, 120), (px, py), (px + rnd.randint(4, 9), py - rnd.randint(2, 6)), 1)

    def friccion_en(self, celda):
        return 0.55 if celda in self.nieve else None

    def dibujar_suelo(self, m, t):
        m.blit(self.capa, (0, 0))


class MecNeon(Mec):
    nombre = "Teletransportadores"
    COLS = [(255, 80, 220), (80, 230, 255), (255, 230, 80), (120, 255, 140)]

    def iniciar(self):
        j = self.j
        self.portales = []
        self.crear_pinchos(j.dif["trampas"] // 3)
        ocup = j.celdas_bloqueadas_spawn()
        cand = [c for c, d in DIST_INICIO.items() if d >= 5 and c not in ocup]
        random.shuffle(cand)
        usados = set()
        for c in cand:
            if len(self.portales) >= min(4, 2 + j.nivel // 15):
                break
            if c in usados:
                continue
            dd = distancias(c)
            socios = [q for q in cand if dd.get(q, 0) >= 10 and q not in usados]
            if socios:
                q = random.choice(socios)
                usados |= {c, q}
                self.portales.append(dict(a=c, b=q, color=self.COLS[len(self.portales) % 4], secreto=False, sala=None))
        # portal secreto: lleva a una habitacion oculta
        salas = [s for s in SALAS_SECRETAS if not s["abierta"]]
        if salas and j.nivel >= 2 and random.random() < 0.75:
            callejones = [c for c in DIST_INICIO if sum(1 for dc, df in VECINOS if (c[0] + dc, c[1] + df) in DIST_INICIO) == 1
                          and DIST_INICIO[c] >= 8 and c not in usados and c not in ocup]
            if callejones:
                s = random.choice(salas)
                self.portales.append(dict(a=random.choice(callejones), b=s["centro"], color=(190, 120, 255), secreto=True, sala=s["id"]))
        self.cd = 0

    def ocupadas(self):
        out = set()
        for p in self.portales:
            out.add(p["a"])
            out.add(p["b"])
        return out

    def actualizar(self):
        j = self.j
        if self.pinchos:
            self.pinchos.actualizar(j)
        if self.cd > 0:
            self.cd -= 1
            return
        cx, cy = j.centro_jugador()
        for p in self.portales:
            for u, v in ((p["a"], p["b"]), (p["b"], p["a"])):
                if math.hypot(cx - (u[0] * TAM + TAM / 2), cy - (u[1] * TAM + TAM / 2)) < 13:
                    chispas(j.particulas, cx, cy, p["color"], 16, 3, 30, 3)
                    j.colocar_jugador(v)
                    chispas(j.particulas, *j.centro_jugador(), p["color"], 16, 3, 30, 3)
                    self.cd = 70
                    AUDIO.sfx("portal")
                    j.stat("portales", 1)
                    j.flash(p["color"], 70)
                    if p["secreto"] and p["sala"] is not None:
                        j.sala_descubierta(SALAS_SECRETAS[p["sala"]], por_portal=True)
                        p["secreto"] = False
                    return

    def dibujar_suelo(self, m, t):
        if self.pinchos:
            self.pinchos.dibujar(m, t)
        cx, cy = self.j.centro_jugador()
        for p in self.portales:
            for c in (p["a"], p["b"]):
                x, y = c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2
                k = 1.0
                if p["secreto"]:
                    k = max(0.0, 1 - (math.hypot(cx - x, cy - y) - 40) / 120) if c == p["a"] else 0.0
                    k = max(0.0, min(1.0, k)) * 0.8
                if k <= 0.02:
                    continue
                g = crear_brillo_cache(34, p["color"])
                g.set_alpha(int(255 * k))
                m.blit(g, (int(x - 34), int(y - 34)))
                for i in range(3):
                    r = 14 - i * 4
                    ang = t * (0.08 + 0.04 * i) * (1 if i % 2 == 0 else -1)
                    col = mezcla(p["color"], 1.0 - 0.2 * i)
                    col = tuple(int(v * k) for v in col)
                    pygame.draw.circle(m, col, (int(x), int(y)), r, 2)
                    px, py = x + r * math.cos(ang), y + r * math.sin(ang)
                    pygame.draw.circle(m, (255, 255, 255), (int(px), int(py)), 2)


class MecPantano(Mec):
    nombre = "Zonas de lento movimiento"

    def iniciar(self):
        j = self.j
        self.crear_pinchos(j.dif["trampas"] // 3)
        cs = [c for c in DIST_INICIO if c != CELDA_INICIAL and DIST_INICIO[c] >= 3]
        random.shuffle(cs)
        self.lodo = set()
        for s in cs[:9 + j.nivel // 10]:
            self.lodo.add(s)
            for dc, df in VECINOS:
                if random.random() < 0.55 and (s[0] + dc, s[1] + df) in DIST_INICIO and (s[0] + dc, s[1] + df) != CELDA_INICIAL:
                    self.lodo.add((s[0] + dc, s[1] + df))
        lodos = list(self.lodo)
        random.shuffle(lodos)
        self.burbujas = {c: random.randint(2, 6) for c in lodos[:4]}

    def mult_vel(self, celda):
        return 0.55 if celda in self.lodo else 1.0

    def actualizar(self):
        j = self.j
        if self.pinchos:
            self.pinchos.actualizar(j)
        cx, cy = j.centro_jugador()
        for e in j.enemigos:
            e.oculto = (not e.es_jefe and e.tipo != TIPO_CAZADOR and e.celda() in self.lodo
                        and math.hypot(e.cx - cx, e.cy - cy) > 130)
        c = j.celda_jugador()
        if c in self.burbujas:
            v = self.burbujas.pop(c)
            j.texto_flotante(cx, cy - 16, "¡Algo escondido!", (255, 235, 130), F_PEQ, 60)
            j.dar_monedas(v, cx, cy)
            j.stat("secretos", 1)
            AUDIO.sfx("secreto")
            chispas(j.particulas, cx, cy, (150, 220, 110), 18, 3, 30, 3)

    def dibujar_suelo(self, m, t):
        for c in self.lodo:
            x, y = c[0] * TAM, c[1] * TAM
            sup = pygame.Surface((TAM, TAM), pygame.SRCALPHA)
            pygame.draw.rect(sup, (70, 80, 40, 175), sup.get_rect(), border_radius=10)
            r = (t // 14 + c[0] * 3 + c[1]) % 6
            pygame.draw.ellipse(sup, (140, 170, 80, 120), (20 - r * 3, 20 - r * 2, r * 6, r * 4), 1)
            m.blit(sup, (x, y))
        for c in self.burbujas:
            x, y = c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2
            for i in range(3):
                by = y + 8 - ((t // 5 + i * 4) % 14) * 1.3
                pygame.draw.circle(m, (190, 230, 150), (int(x - 6 + i * 6), int(by)), 2, 1)
        if self.pinchos:
            self.pinchos.dibujar(m, t)


class MecCueva(Mec):
    nombre = "Visibilidad limitada"

    def iniciar(self):
        j = self.j
        self.crear_pinchos(j.dif["trampas"] // 3)
        ocup = j.celdas_bloqueadas_spawn()
        cs = [c for c, d in DIST_INICIO.items() if d >= 4 and c not in ocup]
        random.shuffle(cs)
        self.antorchas = cs[:6 + j.nivel // 10]

    def niebla(self):
        luces = [(c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2, 85) for c in self.antorchas]
        return dict(tipo="cueva", radio=98, color=(2, 2, 10), alfa=246, luces=luces, linterna=True)

    def actualizar(self):
        if self.pinchos:
            self.pinchos.actualizar(self.j)

    def dibujar_suelo(self, m, t):
        if self.pinchos:
            self.pinchos.dibujar(m, t)
        for c in self.antorchas:
            x, y = c[0] * TAM + TAM / 2, c[1] * TAM + TAM / 2
            pygame.draw.rect(m, (90, 60, 30), (int(x - 2), int(y - 2), 4, 14))
            f = 5 + 2 * math.sin(t * 0.3 + c[0])
            pygame.draw.circle(m, (255, 150, 40), (int(x), int(y - 4)), int(f + 2))
            pygame.draw.circle(m, (255, 230, 120), (int(x), int(y - 4)), int(f - 1))


class MecCielo(Mec):
    nombre = "Plataformas desapareciendo"
    CICLO = 420

    def iniciar(self):
        self.crear_pinchos(0)
        self.plat = {}
        self.elegir()
        self.recambio = 1300

    def elegir(self):
        j = self.j
        ocup = j.celdas_bloqueadas_spawn()
        cand = [c for c, d in DIST_INICIO.items() if d >= 4 and c not in ocup]
        random.shuffle(cand)
        objetivo = int(len(DIST_INICIO) * min(0.18, 0.08 + 0.002 * j.nivel))
        elegidas = []
        base = len(DIST_INICIO)
        for c in cand:
            if len(elegidas) >= objetivo:
                break
            for x, y in elegidas + [c]:
                poner_celda(x, y, "#")
            ok = len(distancias(CELDA_INICIAL)) == base - len(elegidas) - 1
            for x, y in elegidas + [c]:
                poner_celda(x, y, ".")
            if ok:
                elegidas.append(c)
        self.plat = {c: random.randrange(self.CICLO) for c in elegidas}

    def ocupadas(self):
        return set(self.plat)

    def estado(self, c):
        f = (self.j.t + self.plat[c]) % self.CICLO
        return 0 if f < 270 else (1 if f < 335 else 2)   # 0 firme, 1 parpadea, 2 vacio

    def actualizar(self):
        j = self.j
        self.recambio -= 1
        if self.recambio <= 0:
            self.recambio = 1300
            self.elegir()
            AUDIO.sfx("alerta")
        c = j.celda_jugador()
        if c in self.plat and self.estado(c) == 2 and j.vulnerable():
            j.golpe("caida")

    def dibujar_suelo(self, m, t):
        for c in self.plat:
            x, y = c[0] * TAM, c[1] * TAM
            est = self.estado(c)
            if est == 2:
                pygame.draw.rect(m, (14, 20, 46), (x, y, TAM, TAM))
                for i in range(3):
                    pygame.draw.circle(m, (90, 110, 190), (x + 8 + i * 12, y + 12 + (i * 7) % 20), 1)
                pygame.draw.rect(m, (60, 80, 150), (x, y, TAM, TAM), 1)
            else:
                if est == 1 and (t // 5) % 2 == 0:
                    pygame.draw.rect(m, (255, 140, 140), (x + 1, y + 1, TAM - 2, TAM - 2), 2, border_radius=4)
                else:
                    pygame.draw.rect(m, (240, 248, 255), (x + 2, y + 2, TAM - 4, TAM - 4), 2, border_radius=6)
                    pygame.draw.rect(m, (200, 225, 255), (x + 5, y + 5, TAM - 10, TAM - 10), 1, border_radius=4)


class MecAbismo(Mec):
    nombre = "Laberinto vivo"

    def iniciar(self):
        self.crear_pinchos(self.j.dif["trampas"] // 3)
        self.cambios_t = 260
        self.evento_t = 520

    def actualizar(self):
        j = self.j
        if self.pinchos:
            self.pinchos.actualizar(j)
        self.cambios_t -= 1
        if self.cambios_t <= 0:
            self.programar_cambios(3 + min(4, j.nivel // 12), 55)
            self.cambios_t = max(150, 320 - 3 * j.nivel)
        self.evento_t -= 1
        if self.evento_t <= 0:
            self.evento_t = random.randint(420, 700)
            r = random.random()
            cx, cy = j.centro_jugador()
            if r < 0.4:     # el laberinto mueve a los enemigos
                for e in random.sample(j.enemigos, min(2, len(j.enemigos))):
                    if not e.es_jefe and e.tipo != TIPO_CAZADOR:
                        cs = [c for c, d in j.dist_jugador.items() if d >= 7]
                        if cs:
                            chispas(j.particulas, e.cx, e.cy, (150, 100, 240), 14, 3, 30, 3)
                            e.teletransportar(random.choice(cs))
                            chispas(j.particulas, e.cx, e.cy, (150, 100, 240), 14, 3, 30, 3)
                j.texto_flotante(cx, cy - 30, "¡El laberinto los mueve!", (190, 150, 255), F_PEQ, 70)
            else:           # activa trampas alrededor
                for _ in range(3 + j.nivel // 20):
                    ang = random.uniform(0, math.tau)
                    d = random.uniform(40, 120)
                    x, y = cx + d * math.cos(ang), cy + d * math.sin(ang)
                    if not es_pared(x, y):
                        j.impactos.append(Impacto(x, y, 60, 26, (180, 110, 255), dano_enemigos=99))
                j.texto_flotante(cx, cy - 30, "¡Trampas activadas!", (190, 150, 255), F_PEQ, 70)
        self.actualizar_cambios()

    def dibujar_suelo(self, m, t):
        if self.pinchos:
            self.pinchos.dibujar(m, t)
        self.dibujar_cambios(m, t)


class MecCorazon(Mec):
    nombre = "El laberinto late"

    def iniciar(self):
        j = self.j
        self.crear_pinchos(j.dif["trampas"] // 2)
        self.cambios_t = 520
        self.latido_t = 240
        self.pulso = 0
        self.cuchillas = []
        runs = []
        for f in range(1, FILAS - 1):
            c = 1
            while c < COLS - 1:
                if MAPA[f][c] != "#":
                    ini = c
                    while c < COLS - 1 and MAPA[f][c] != "#":
                        c += 1
                    if c - ini >= 5 and (ini, f) in DIST_INICIO and DIST_INICIO[(ini, f)] >= 4:
                        runs.append(([(x, f) for x in range(ini, c)], "h"))
                else:
                    c += 1
        for c in range(1, COLS - 1):
            f = 1
            while f < FILAS - 1:
                if MAPA[f][c] != "#":
                    ini = f
                    while f < FILAS - 1 and MAPA[f][c] != "#":
                        f += 1
                    if f - ini >= 5 and (c, ini) in DIST_INICIO and DIST_INICIO[(c, ini)] >= 4:
                        runs.append(([(c, y) for y in range(ini, f)], "v"))
                else:
                    f += 1
        random.shuffle(runs)
        for seg, eje in runs[:min(2 + j.nivel // 3 - 17, 5) if j.nivel >= 51 else 2]:
            self.cuchillas.append(Cuchilla(seg, eje))

    def actualizar(self):
        j = self.j
        if self.pinchos:
            self.pinchos.actualizar(j)
        for c in self.cuchillas:
            c.actualizar(j)
        self.latido_t -= 1
        if self.pulso > 0:
            self.pulso -= 1
        if self.latido_t <= 0:
            self.latido_t = max(190, 300 - 10 * (j.nivel - MAX_NIVELES))
            self.pulso = 40
            AUDIO.sfx("corazon")
            j.temblor = max(j.temblor, 8)
            cx, cy = j.centro_jugador()
            for _ in range(7):
                ang = random.uniform(0, math.tau)
                d = random.uniform(10, 110)
                x, y = cx + d * math.cos(ang), cy + d * math.sin(ang)
                if not es_pared(x, y):
                    j.impactos.append(Impacto(x, y, 78, 24, (255, 70, 120), dano_enemigos=99, sonido="golpe" if False else "bomba"))
        self.cambios_t -= 1
        if self.cambios_t <= 0:
            self.programar_cambios(2, 60)
            self.cambios_t = 600
        self.actualizar_cambios()

    def dibujar_suelo(self, m, t):
        if self.pinchos:
            self.pinchos.dibujar(m, t)
        self.dibujar_cambios(m, t)

    def dibujar_encima(self, m, t):
        for c in self.cuchillas:
            c.dibujar(m, t)
        if self.pulso > 0:
            r = int((40 - self.pulso) * 14)
            pygame.draw.circle(m, (255, 90, 130), (ANCHO // 2, ALTO_MAPA // 2), r, 3)


MECANICAS = {0: MecCripta, 1: MecBosque, 2: MecDesierto, 3: MecVolcan, 4: MecGlaciar, 5: MecNeon,
             6: MecPantano, 7: MecCueva, 8: MecCielo, 9: MecAbismo, 10: MecCorazon}


# ======================================================
# Juego
# ======================================================
KIND_PROY = {
    "veneno": ((60, 140, 30), (170, 240, 90)), "hueso": ((200, 195, 170), (250, 248, 235)),
    "fuego": ((200, 60, 20), (255, 190, 60)), "nieve": ((150, 200, 240), (250, 255, 255)),
    "bala": ((160, 30, 30), (255, 110, 110)), "rayo": ((200, 180, 40), (255, 250, 160)),
    "sonar": ((110, 70, 170), (210, 170, 255)), "corazon": ((190, 30, 80), (255, 150, 190)),
}

JEFE_ATAQUES = {
    # mundo: [(fase_minima, cada_n_frames, accion, parametros)]. Gana el de mayor fase que ya este activo por accion.
    0: [(1, 480, "invocar", dict(n=1)), (2, 300, "invocar", dict(n=1)), (2, 230, "anillo", dict(n=6, vel=3.2, kind="hueso")),
        (3, 190, "invocar", dict(n=2)), (3, 150, "anillo", dict(n=10, vel=3.6, kind="hueso", giro=True))],
    1: [(1, 330, "embestida", dict(mult=2.3)), (2, 240, "embestida", dict(mult=2.6)), (2, 700, "invocar", dict(n=2, tipo=2)),
        (3, 200, "embestida", dict(mult=3.0, doble=True)), (3, 280, "lluvia", dict(n=3, radio=30, color=(215, 215, 240)))],
    2: [(1, 150, "abanico", dict(n=1, kind="veneno")), (2, 100, "abanico", dict(n=3, kind="veneno")),
        (3, 90, "abanico", dict(n=5, kind="veneno")), (3, 140, "lluvia", dict(n=3, radio=28, color=(130, 230, 70), lava=220))],
    3: [(1, 34, "charcos", dict()), (2, 26, "charcos", dict()), (2, 170, "lluvia", dict(n=2, radio=32, color=(255, 140, 50))),
        (3, 20, "charcos", dict()), (3, 90, "lluvia", dict(n=3, radio=40, color=(255, 110, 40))),
        (3, 210, "anillo", dict(n=8, vel=3.4, kind="fuego"))],
    4: [(1, 400, "pisoton", dict(aviso=60)), (2, 300, "pisoton", dict(aviso=55)), (2, 140, "abanico", dict(n=2, kind="nieve")),
        (3, 210, "pisoton", dict(aviso=40)), (3, 170, "anillo", dict(n=10, vel=3.2, kind="nieve"))],
    5: [(1, 300, "laser", dict()), (2, 210, "laser", dict()), (2, 600, "invocar", dict(n=1, tipo=1)),
        (3, 170, "laser", dict(cruz=True)), (3, 150, "anillo", dict(n=8, vel=3.6, kind="rayo"))],
    6: [(1, 260, "embestida", dict(mult=0.0, salto=True)), (2, 190, "embestida", dict(mult=0.0, salto=True)),
        (2, 120, "abanico", dict(n=3, kind="veneno")), (3, 130, "embestida", dict(mult=0.0, salto=True)),
        (3, 100, "lluvia", dict(n=2, radio=28, color=(130, 230, 70), lava=240)), (3, 200, "anillo", dict(n=8, vel=3.2, kind="veneno"))],
    7: [(1, 300, "anillo", dict(n=6, vel=2.2, kind="sonar")), (1, 560, "invocar", dict(n=1, tipo=2)),
        (2, 420, "invocar", dict(n=2, tipo=2)), (2, 260, "embestida", dict(mult=2.8)),
        (3, 180, "embestida", dict(mult=3.2, doble=True)), (3, 120, "anillo", dict(n=10, vel=2.8, kind="sonar"))],
    8: [(1, 280, "embestida", dict(mult=2.8)), (2, 200, "embestida", dict(mult=3.0)), (2, 110, "lluvia", dict(n=2, radio=26, color=(255, 245, 140))),
        (3, 150, "embestida", dict(mult=3.3)), (3, 70, "lluvia", dict(n=3, radio=26, color=(255, 245, 140))), (3, 210, "anillo", dict(n=8, vel=3.4, kind="rayo"))],
    9: [(1, 240, "anillo", dict(n=8, vel=2.6, kind="sonar", giro=True)), (2, 220, "embestida", dict(mult=0.0, salto=True)),
        (2, 200, "anillo", dict(n=10, vel=3.0, kind="sonar", giro=True)), (2, 500, "invocar", dict(n=1, tipo=1)),
        (3, 200, "escenario", dict(n=4)), (3, 130, "anillo", dict(n=12, vel=3.2, kind="sonar", giro=True)),
        (3, 170, "lluvia", dict(n=3, radio=30, color=(180, 110, 255)))],
    10: [(1, 200, "anillo", dict(n=8, vel=3.0, kind="corazon", giro=True)), (1, 600, "invocar", dict(n=1)),
         (1, 220, "lluvia", dict(n=3, radio=30, color=(255, 80, 130))),
         (2, 260, "laser", dict()), (2, 240, "embestida", dict(mult=0.0, salto=True)), (2, 150, "anillo", dict(n=10, vel=3.4, kind="corazon", giro=True)),
         (2, 500, "invocar", dict(n=2)), (3, 170, "laser", dict(cruz=True)), (3, 260, "pisoton", dict(aviso=45)),
         (3, 100, "lluvia", dict(n=4, radio=32, color=(255, 80, 130))), (3, 110, "anillo", dict(n=12, vel=3.6, kind="corazon", giro=True)),
         (3, 300, "escenario", dict(n=3))],
}

# misiones secundarias de nivel: (tipo, texto)
MISIONES_NIVEL = ["enemigos", "monedas", "combo", "rapido", "sin_dano", "poderes", "frutas_rapido"]
ATAQUES = {  # nombre: (coste de energia, reutilizacion en frames)
    "cargado": (20, 40), "especial": (40, 300), "rayo": (30, 240), "hielo": (25, 180), "rafaga": (35, 260),
}
_LUCES = {}


def luz_grad(r):
    """Disco con borde suave (alfa) para recortar la oscuridad."""
    r = int(r)
    if r not in _LUCES:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for k in range(r, 0, -2):
            a = int(255 * min(1.0, (1 - k / r) * 2.2))
            pygame.draw.circle(s, (0, 0, 0, a), (r, r), k)
        _LUCES[r] = s
    return _LUCES[r]


def crear_vineta_color(color, fuerza=1.0):
    peq = pygame.Surface((32, 24), pygame.SRCALPHA)
    for y in range(24):
        for x in range(32):
            d = math.hypot((x - 15.5) / 16, (y - 11.5) / 12)
            a = max(0.0, min(1.0, (d - 0.55) / 0.6)) ** 1.6
            peq.set_at((x, y), (*color, int(190 * a * fuerza)))
    return pygame.transform.smoothscale(peq, (ANCHO, ALTO_MAPA))


VINETA_ROJA = crear_vineta_color((200, 0, 20))
VINETA_FURIA = crear_vineta_color((255, 90, 0))
VINETA_DIM = crear_vineta_color((60, 0, 30), 0.8)


def mult_combo(c):
    """Combo: 1,2,3,4,5 -> x1..x5 ; 10 -> x10 ; 20 -> x20."""
    if c >= 20:
        return 20
    if c >= 10:
        return 10
    return max(1, min(c, 5))


class Juego:
    def __init__(self, nivel_inicial=1):
        self.mejor = PROG.mejor_puntos
        self.t = 0
        self.toasts = []
        self.cola_modales = []
        self.habito = {d: 1 for d in DIRS}
        self.nueva_partida(nivel_inicial)

    # ---------- partidas ----------
    def nueva_partida(self, nivel=1, datos=None):
        self.vidas_max = PROG.vidas_max()
        self.puntos = 0
        self.vidas = self.vidas_max
        self.nivel = nivel
        self.bombas = 1
        self.semilla = random.randrange(1, 10 ** 6)
        self.cp_nivel, self.cp_puntos = nivel, 0
        self.record_previo = PROG.mejor_puntos
        self.run_frutas = self.run_enemigos = 0
        self.combo_max = 0
        self.furia = 0.0
        self.habito = {d: 1 for d in DIRS}
        if datos:
            self.nivel = max(1, min(MAX_NIVEL_TOTAL, int(datos.get("nivel", 1))))
            self.puntos = int(datos.get("puntos", 0))
            self.vidas = max(1, min(self.vidas_max, int(datos.get("vidas", self.vidas_max))))
            self.bombas = max(0, min(3, int(datos.get("bombas", 1))))
            self.semilla = int(datos.get("semilla", self.semilla))
            self.cp_nivel = int(datos.get("cp_nivel", self.nivel))
            self.cp_puntos = int(datos.get("cp_puntos", 0))
            self.run_frutas = int(datos.get("run_frutas", 0))
            self.run_enemigos = int(datos.get("run_enemigos", 0))
            self.combo_max = int(datos.get("combo_max", 0))
            for d in DIRS:
                self.habito[d] = int(datos.get("habito", {}).get(d, 1))
        self.iniciar_nivel()

    def continuar(self):
        """Tras un Game Over: vuelve al ultimo checkpoint (inicio de cada mundo)."""
        self.puntos = self.cp_puntos
        self.vidas_max = PROG.vidas_max()
        self.vidas = self.vidas_max
        self.nivel = self.cp_nivel
        self.bombas = 1
        self.furia = 0.0
        self.iniciar_nivel()

    def guardar_partida(self):
        """Guarda la partida en curso (nivel, mundo, puntos...) para poder continuar."""
        if self.estado in ("game_over", "muriendo", "victoria", "victoria_final"):
            PROG.partida = None
        else:
            PROG.partida = dict(nivel=self.nivel, mundo=self.mundo, puntos=self.puntos, vidas=self.vidas,
                                bombas=self.bombas, semilla=self.semilla, cp_nivel=self.cp_nivel,
                                cp_puntos=self.cp_puntos, run_frutas=self.run_frutas,
                                run_enemigos=self.run_enemigos, combo_max=self.combo_max, habito=dict(self.habito))
        PROG.guardar()

    def iniciar_nivel(self):
        self.estado = "jugando"  # jugando | muriendo | nivel_completo | game_over | victoria | victoria_final
        self.estado_nivel = "jugando"
        self.timer = 0
        self.t_nivel = 0
        self.dif = dificultad(self.nivel)
        self.mundo = mundo_de(self.nivel)
        self.info = MUNDOS[self.mundo]
        self.es_jefe = es_nivel_jefe(self.nivel)
        primer_nivel_mundo = (self.nivel - 1) % NIVELES_POR_MUNDO == 0
        if primer_nivel_mundo:
            self.cp_nivel, self.cp_puntos = self.nivel, self.puntos
        self.tema = TEMAS[self.mundo]
        self.cache_dist = {}
        self.vida_extra = False
        self.vidas_max = PROG.vidas_max()
        self.vidas = min(self.vidas, self.vidas_max)
        cargar_mapa(construir_mapa(self.nivel, self.semilla))  # laberinto nuevo por nivel
        self.estilo = ESTILO_ACTUAL
        self.fondo = crear_fondo(self.tema, self.nivel + self.semilla)
        self.x = TAM * CELDA_INICIAL[0] + MARGEN
        self.y = TAM * CELDA_INICIAL[1] + MARGEN
        self.vx = self.vy = 0.0
        self.direccion = "abajo"
        self.moviendo = False
        self.invulnerable = 90
        self.arma = Arma()
        self.particulas, self.textos, self.ondas = [], [], []
        self.trampas, self.proy_enemigos, self.lavas = [], [], []
        self.impactos, self.rayos = [], []
        self.efecto_jefe = {}
        self.temblor = 0
        self.combo = self.combo_t = 0
        self.recolectadas = 0
        self.respawns = []
        self.dist_jugador = self.dist_desde(CELDA_INICIAL)
        self.b_prev = False
        self.prev = {}
        self.recibio_dano = False
        self.estrellas_nivel = 0
        self.monedas_nivel = 0
        self.bonus = 0
        self.bonus_monedas = 0
        self.vidas_inicio = self.vidas
        self.t_estrella = self.t_hielo = self.t_rafaga = self.t_rapido = 0
        self.t_cereza = self.t_uva = self.t_cristal = self.t_furia = 0
        self.cadena = 0
        self.vida_frac = 0
        self.carga = 0
        self.energia = float(PROG.energia_max())
        self.cd = {k: 0 for k in ATAQUES}
        self.sin_dano_t = 0
        self.empuje = {}
        self.banners = []
        self.flash_a = 0
        self.flash_col = (255, 255, 255)
        self.fade = 255
        self.boss_oscuro = self.boss_ventisca = False
        self.boss_tinte = None
        self.monedas_suelo, self.cofres, self.fragmentos = [], [], []
        self.frutas_extra, self.especiales = [], []
        self.guardian = None
        self.hechas_salas = 0
        f = self.dif["factor_poder"]
        self.dur = dict(estrella=int(480 * f), hielo=420 if self.mundo == 4 else 300,
                        rafaga=int(600 * f), rapido=int(480 * f))
        cantidad = 8 if self.es_jefe else self.dif["frutas"]
        candidatas = [c for c, d in DIST_INICIO.items() if d >= 3]
        random.shuffle(candidatas)
        self.frutas = [Fruta(c, random.randrange(N_FRUTAS_NORMALES)) for c in candidatas[:cantidad]]
        self.total_frutas = len(self.frutas)

        self.enemigos, self.poderes, self.jefe = [], [], None
        self.mec = MECANICAS[self.mundo](self)
        self.ambiente = Ambiente(self.mundo)
        self.eventos = GestorEventos(self)
        self.mascota = Mascota(PROG.mascota, self.x + 10, self.y + 10) if PROG.mascota else None

        self.poderes = []
        for _ in range(4 if self.es_jefe else self.dif["poderes_ini"]):
            self.poner_poder()
        self.sig_poder = 500 if self.es_jefe else self.dif["sig_poder"]
        if self.es_jefe:
            self.bombas = min(3, self.bombas + 1)
        self.t_esp = random.randint(500, 900)

        cant_e = self.dif["enemigos"]
        if self.es_jefe:
            cant_e = max(2, cant_e // 2)
        tipos = [self.tipo_enemigo(i) for i in range(cant_e)]
        for tipo, cuota in ((3, self.dif["tanques"]), (4, self.dif["tiradores"]), (5, self.dif["fantasmas"])):
            for i in range(len(tipos)):
                if tipos.count(tipo) >= cuota:
                    break
                if tipos[i] in (0, 1):
                    tipos[i] = tipo
        self.enemigos = []
        for i, tp in enumerate(tipos):
            self.enemigos.append(self.nuevo_enemigo(celda_lejana(CELDA_INICIAL, 8), tp, i))
        self.jefe = None
        if self.es_jefe:
            self.jefe = Jefe(celda_lejana(CELDA_INICIAL, 12), self.mundo)
            self.enemigos.append(self.jefe)

        # El Cazador: aprende de tus caminos desde el primer segundo
        self.cazador = None
        self.cazador_en_juego = False
        self.cazador_espera = 0
        self.cazador_vidas = 2
        ia = self.dif["cazador"]
        if ia > 0 and (not self.es_jefe or self.nivel >= 25):
            self.cazador = Cazador(CELDA_INICIAL, ia, self.mundo, self.dif["vel"], self.habito)
            self.cazador_espera = random.randint(480, 840) - 40 * ia

        self.crear_secretos()
        self.crear_mision()
        # fragmento de historia del mundo
        if self.mundo <= 9 and PROG.desbloquear_fragmento(f"mundo_{self.mundo}"):
            self.toasts.append(["Historia: nuevo fragmento", HISTORIA_POR_ID[f"mundo_{self.mundo}"][1], 320, None])
        if self.mundo == MUNDO_DIM:
            if not PROG.dim_desbloqueada:
                PROG.dim_desbloqueada = True
            PROG.maximo("dimension", 1)
        self.actualizar_musica()

        info = self.info
        extra = {6: "¡Algunos enemigos ahora te emboscan!", 8: "¡Aparecen los Tanques! Aguantan varios golpes",
                 12: "¡Cuidado: hay enemigos más rápidos!", 15: "¡Aparecen Tiradores: disparan desde lejos!",
                 22: "¡Aparecen Fantasmas: atraviesan paredes!", 2: "¡Ojo! EL CAZADOR te observa..."}.get(self.nivel, "")
        lim = f"NIVEL {self.nivel} / {MAX_NIVELES}" if self.nivel <= MAX_NIVELES else f"DIMENSIÓN {self.nivel - MAX_NIVELES} / 5"
        regla = f"Regla del mundo: {self.mec.nombre}"
        if self.es_jefe:
            self.aviso = (f"{lim}  ·  ¡JEFE!", info["jefe"], f"Este jefe {info['habilidad']}. ¡Tiene 3 fases!")
            self.aviso_t = 260
        elif primer_nivel_mundo:
            self.aviso = (lim, f"Mundo {info['nombre']}: aparecen los {info['plural']}",
                          f"{regla}   ·   Bomba: {info['bomba']}")
            self.aviso_t = 280
        else:
            self.aviso = (lim, f"Mundo {info['nombre']}  -  recoge todas las frutas", extra or regla)
            self.aviso_t = 180
        self.guardar_partida()

    # ---------- creacion ----------
    def celdas_ocupadas(self, margen=0):
        """Casillas con objetos, enemigos o el jugador (para no aparecer encima)."""
        oc = set()
        for lst in (self.frutas, self.frutas_extra, self.especiales, self.poderes):
            for o in lst:
                oc.add((int(o.cx // TAM), int(o.cy // TAM)))
        for lst in (self.cofres, self.fragmentos):
            for o in lst:
                oc.add((int(o.x // TAM), int(o.y // TAM)))
        cj = self.celda_jugador()
        oc.add(cj)
        if margen:
            for e in self.enemigos:
                oc.add(e.celda())
            base = set(oc)
            for c in base:
                for dc in range(-margen, margen + 1):
                    for df in range(-margen, margen + 1):
                        oc.add((c[0] + dc, c[1] + df))
        return oc

    def celdas_bloqueadas_spawn(self):
        """Casillas donde NO deben ponerse trampas ni objetos nuevos."""
        oc = {(int(f.cx // TAM), int(f.cy // TAM)) for f in self.frutas}
        oc |= {CELDA_INICIAL, (1, 2), (2, 1)}
        oc |= {(int(e.cx // TAM), int(e.cy // TAM)) for e in self.enemigos}
        return oc

    def poner_poder(self):
        ocupadas = self.celdas_ocupadas() | self.mec.ocupadas()
        libres = [c for c, d in DIST_INICIO.items() if d >= 4 and c not in ocupadas]
        if not libres:
            return
        pesos = [2, 2, 3, 2, 2, 3 if self.mundo == MUNDO_DIM else 0]
        tipo = random.choices(range(len(PODERES)), weights=pesos)[0]
        self.poderes.append(Poder(random.choice(libres), tipo, self.mundo))

    def tipo_enemigo(self, i):
        n = self.nivel
        if n >= 22 and i % 9 == 8:
            return 5
        if n >= 15 and i % 7 == 6:
            return 4
        if n >= 8 and i % 5 == 4:
            return 3
        if n >= 12 and i % 4 == 3:
            return 2
        if n >= 6 and i % 2 == 1:
            return 1
        return 0

    def nuevo_enemigo(self, celda, tipo, i=0, vel=None):
        color = {0: 0 if i % 2 == 0 else 2, 1: 1, 2: 3, 3: 2, 4: 1, 5: 3}.get(tipo, 0)
        info = ENEMIGO_INFO[tipo]
        if vel is None:
            vel = self.dif["vel"] * random.uniform(0.95, 1.05) * info["vel"]
        alt = tipo in (1, 4) and self.mundo in DIBUJOS_ALT
        cls = {4: Tirador, 5: Fantasma}.get(tipo, Enemigo)
        return cls(celda, vel, color, tipo, self.mundo, alt)

    def dist_desde(self, celda):
        d = self.cache_dist.get(celda)
        if d is None:
            if len(self.cache_dist) > 40:
                self.cache_dist.clear()
            d = self.cache_dist[celda] = distancias(celda)
        return d

    def celda_emboscada(self, cj):
        """Casilla unas 4 por delante del jugador (hacia donde mira)."""
        dx, dy = DIRS[self.direccion]
        mejor = cj
        for k in range(1, 5):
            n = (cj[0] + dx * k, cj[1] + dy * k)
            if n not in self.dist_jugador:
                break
            mejor = n
        return mejor

    def segmento(self, celda, eje):
        """Casillas libres en linea recta (fila o columna) que pasan por 'celda'."""
        dc, df = (1, 0) if eje == "h" else (0, 1)
        seg = {celda}
        for sg in (1, -1):
            c = celda
            while True:
                c = (c[0] + dc * sg, c[1] + df * sg)
                if es_pared(c[0] * TAM + 2, c[1] * TAM + 2):
                    break
                seg.add(c)
        return seg

    def rehacer_fondo(self):
        self.fondo = crear_fondo(self.tema, self.nivel + self.semilla)

    def colocar_jugador(self, celda):
        self.x = TAM * celda[0] + MARGEN
        self.y = TAM * celda[1] + MARGEN
        self.vx = self.vy = 0.0
        self.dist_jugador = self.dist_desde(celda) if celda in DIST_INICIO else self.dist_jugador

    def disparar_enemigo(self, x, y, dx, dy, kind="veneno", vel=5.0):
        n = math.hypot(dx, dy) or 1
        self.proy_enemigos.append([x, y, dx / n, dy / n, kind, vel])

    # ---------- utilidades ----------
    def centro_jugador(self):
        return self.x + ANCHO_PJ / 2, self.y + ALTO_PJ / 2

    def celda_jugador(self):
        cx, cy = self.centro_jugador()
        return int(cx // TAM), int(cy // TAM)

    def vulnerable(self):
        return self.t_estrella <= 0 and self.invulnerable <= 0 and self.estado == "jugando"

    def stat(self, clave, n=1, maximo=False):
        self.notificar(PROG.maximo(clave, n) if maximo else PROG.sumar(clave, n))

    def notificar(self, tareas):
        """Avisa de misiones y logros completados."""
        for t in tareas:
            self.toasts.append(["¡Misión completada!", t["texto"], 300, t["premio"]])
            AUDIO.sfx("vida")
            sig = PROG.siguiente(t)
            if sig:
                self.toasts.append(["Nueva misión", sig["texto"], 300, None])
        for lg in PROG.pop_logros():
            self.toasts.append(["¡LOGRO DESBLOQUEADO!", lg["nombre"], 340, None])
            AUDIO.sfx("logro")
        if tareas:
            PROG.guardar()

    def texto_flotante(self, x, y, txt, color, fnt=F_MED, vida=60):
        self.textos.append(TextoFlotante(x, y, txt, color, fnt, vida))

    def banner(self, titulo, color=(255, 255, 255), sub=""):
        self.banners.append([titulo, sub, color, 150])

    def flash(self, color, alfa=120):
        if CONFIG["efectos"]:
            self.flash_col, self.flash_a = color, max(self.flash_a, alfa)

    def actualizar_musica(self):
        if self.estado in ("game_over", "muriendo"):
            return
        if self.t_furia > 0:
            AUDIO.musica("furia")
        elif self.es_jefe:
            AUDIO.musica("jefe3" if (self.jefe and self.jefe.fase >= 3) else "jefe")
        else:
            AUDIO.musica_mundo(self.mundo)

    # ---------- economia ----------
    def dar_monedas(self, n, x=None, y=None):
        if n <= 0:
            return
        self.monedas_nivel += n
        self.progreso_mision("monedas", n)
        self.notificar(PROG.ganar_monedas(n))
        AUDIO.sfx("moneda")
        if x is not None:
            self.texto_flotante(x, y - 12, f"+{n} $", (255, 220, 90), F_PEQ, 50)

    def recoger_moneda(self, mo):
        if mo in self.monedas_suelo:
            self.monedas_suelo.remove(mo)
            self.dar_monedas(mo.valor, mo.x, mo.y)
            chispas(self.particulas, mo.x, mo.y, (255, 220, 80), 6, 2.0, 18, 2, 0.0)

    def soltar_monedas(self, x, y, total, por=1):
        n = max(1, total // por)
        for _ in range(min(n, 8)):
            ang = random.uniform(0, math.tau)
            v = random.uniform(1.5, 3.5)
            self.monedas_suelo.append(Moneda(x, y, por if total >= por else total, 1100, math.cos(ang) * v, math.sin(ang) * v))

    def multiplicador(self):
        m = mult_combo(self.combo) if self.combo_t > 0 else 1
        if self.t_uva > 0:
            m *= 2
        if self.t_cristal > 0:
            m *= 3
        if self.t_furia > 0:
            m *= 2
        return m

    def sumar_puntos(self, base, x=None, y=None, usar_mult=True, color=(255, 240, 130)):
        m = self.multiplicador() if usar_mult else 1
        pts = int(base * m)
        self.puntos += pts
        if x is not None:
            txt = f"+{pts}" + (f"  x{m}" if m > 1 else "")
            self.texto_flotante(x, y - 14, txt, color, F_MED if m >= 5 else F_PEQ, 55)
        return pts

    def avanzar_combo(self):
        self.combo = self.combo + 1 if self.combo_t > 0 else 1
        self.combo_t = COMBO_FRAMES
        if self.combo > self.combo_max:
            self.combo_max = self.combo
        if self.combo in (5, 10, 20):
            self.ganar_furia({5: 8, 10: 14, 20: 25}[self.combo])
            self.texto_flotante(*self.centro_jugador(), f"¡COMBO x{mult_combo(self.combo)}!", (255, 225, 90), F_GRANDE, 70)
            AUDIO.sfx("poder")
            self.flash((255, 220, 90), 50)
        self.stat("combo_max", self.combo, True)
        self.progreso_mision("combo", self.combo, absoluto=True)

    # ---------- furia ----------
    def ganar_furia(self, n):
        if self.t_furia > 0 or self.estado != "jugando":
            return
        self.furia = min(100.0, self.furia + n)
        if self.furia >= 100:
            self.activar_furia()

    def activar_furia(self):
        self.t_furia = 600
        self.furia = 100.0
        self.banner("¡MODO FURIA!", (255, 110, 50), "Más velocidad, más daño y puntos x2")
        self.flash((255, 90, 30), 150)
        self.temblor = max(self.temblor, 24)
        AUDIO.sfx("furia_on")
        cx, cy = self.centro_jugador()
        self.ondas.append([cx, cy, 36, 36, (255, 110, 40), 260])
        chispas(self.particulas, cx, cy, (255, 150, 50), 40, 6, 50, 5)
        self.stat("furias")
        self.actualizar_musica()

    def terminar_furia(self):
        self.t_furia = 0
        self.furia = 0.0
        AUDIO.sfx("furia_off")
        self.actualizar_musica()

    # ---------- misiones de nivel ----------
    def crear_mision(self):
        n = self.nivel
        if self.es_jefe:
            tipo = random.choice(("jefe_perfecto", "enemigos"))
        else:
            ops = ["enemigos", "monedas", "combo", "rapido", "sin_dano", "poderes", "frutas_rapido"]
            if SALAS_SECRETAS or SECRETAS:
                ops += ["secreto", "secreto"]
            tipo = random.choice(ops)
        premio = 6 + n // 3
        m = dict(tipo=tipo, prog=0, hecha=False, premio=premio)
        if tipo == "enemigos":
            m.update(meta=3 + n // 10, texto="Derrota {} enemigos")
        elif tipo == "monedas":
            m.update(meta=6 + n // 4, texto="Consigue {} Frutacoins")
        elif tipo == "combo":
            m.update(meta=5 if n < 20 else 10, texto="Logra un combo de {}")
        elif tipo == "rapido":
            m.update(meta=self.dif["tiempo_par"], texto="Termina en menos de {} s")
        elif tipo == "sin_dano":
            m.update(meta=1, texto="Termina sin recibir daño")
        elif tipo == "poderes":
            m.update(meta=2, texto="Recoge {} poderes")
        elif tipo == "frutas_rapido":
            m.update(meta=min(6, max(3, self.total_frutas // 3)), texto="Recoge {} frutas en 20 s")
        elif tipo == "secreto":
            m.update(meta=1, texto="Encuentra un secreto")
        elif tipo == "jefe_perfecto":
            m.update(meta=1, texto="Derrota al jefe sin perder vidas")
            m["premio"] = 20
        m["texto"] = m["texto"].format(m["meta"])
        self.mision = m

    def progreso_mision(self, tipo, n=1, absoluto=False):
        m = self.mision
        if m["hecha"] or m["tipo"] != tipo:
            return
        if tipo == "frutas_rapido" and self.t_nivel > 1200:
            return
        m["prog"] = n if absoluto else m["prog"] + n
        if m["prog"] >= m["meta"]:
            self.mision_cumplida()

    def mision_cumplida(self):
        m = self.mision
        if m["hecha"]:
            return
        m["hecha"] = True
        self.toasts.append(["¡Misión de nivel!", m["texto"], 280, None])
        self.texto_flotante(*self.centro_jugador(), f"¡MISIÓN! +{m['premio']} $", (140, 255, 160), F_MED, 80)
        AUDIO.sfx("vida")
        self.notificar(PROG.ganar_monedas(m["premio"]))
        self.monedas_nivel += m["premio"]
        self.stat("minimisiones")

    # ---------- secretos ----------
    def crear_secretos(self):
        """Prepara el contenido de las habitaciones ocultas (se revela al abrirlas)."""
        self.salas = SALAS_SECRETAS
        for sl in self.salas:
            r = random.random()
            cont = dict(cofre=True, monedas=random.randint(10, 22) + self.nivel // 3)
            if r < 0.14 or (self.mundo == MUNDO_DIM and r < 0.3):
                cont["legendaria"] = True
            elif r < 0.45 and [f for f in FRAGMENTOS_SECRETOS if f not in PROG.fragmentos]:
                cont["fragmento"] = random.choice([f for f in FRAGMENTOS_SECRETOS if f not in PROG.fragmentos])
            elif r < 0.6:
                cont["poder"] = True
            elif r < 0.7 and self.nivel >= 5:
                cont["guardian"] = True
            if random.random() < 0.4:
                cont["pila"] = True
            sl["contenido"] = cont

    def revelar_secreto(self, celda, por="empuje"):
        sec = SECRETAS.get(celda)
        if sec is None:
            return
        del SECRETAS[celda]
        poner_celda(celda[0], celda[1], ".")
        recalcular_mapa()
        self.cache_dist.clear()
        self.dist_jugador = self.dist_desde(self.celda_jugador())
        self.rehacer_fondo()
        px, py = celda[0] * TAM + TAM / 2, celda[1] * TAM + TAM / 2
        AUDIO.sfx("secreto")
        chispas(self.particulas, px, py, (255, 235, 140), 30, 4, 40, 4)
        self.ondas.append([px, py, 26, 26, (255, 235, 140), 90])
        self.temblor = max(self.temblor, 10)
        self.flash((255, 235, 150), 60)
        self.stat("secretos")
        self.progreso_mision("secreto")
        if sec["sala"] is not None:
            self.sala_descubierta(self.salas[sec["sala"]])
        else:
            self.texto_flotante(px, py - 20, "¡PASADIZO SECRETO!", (255, 235, 140), F_MED, 90)
            self.dar_monedas(5 + self.nivel // 5, px, py)

    def sala_descubierta(self, sl, por_portal=False):
        if sl["abierta"]:
            return
        sl["abierta"] = True
        c = sl["contenido"]
        cx, cy = sl["centro"]
        px, py = cx * TAM + TAM / 2, cy * TAM + TAM / 2
        self.hechas_salas += 1
        self.stat("habitaciones")
        if por_portal:
            self.stat("secretos")
            self.progreso_mision("secreto")
        self.texto_flotante(px, py - 30, "¡HABITACIÓN SECRETA!", (255, 235, 140), F_MED, 100)
        self.banner("¡HABITACIÓN SECRETA!", (255, 235, 140), "Hay un tesoro dentro...")
        cof = Cofre(px, py, c["monedas"], 500 + 25 * self.nivel)
        self.cofres.append(cof)
        if c.get("legendaria"):
            self.especiales.append(Fruta((cx - 1, cy), IDX_LEGENDARIA, ttl=2400))
        if c.get("fragmento"):
            self.fragmentos.append(Fragmento(px + TAM, py, c["fragmento"]))
        if c.get("poder"):
            self.poderes.append(Poder((cx + 1, cy - 1), random.choice((0, 1, 3, 4)), self.mundo))
        if c.get("pila"):
            for _ in range(8):
                self.monedas_suelo.append(Moneda(px + random.uniform(-40, 40), py + random.uniform(-40, 40), 1, 1800))
        if c.get("guardian") and self.guardian is None:
            g = self.nuevo_enemigo((cx, cy - 1), 3, 0)
            g.hp = g.hp_max = 8.0 + self.nivel * 0.2
            g.info = dict(g.info, pts=1500, monedas=0)
            g.invasor = 0
            g.guardian = True
            g.vel *= 0.9
            self.guardian = g
            self.enemigos.append(g)
            self.texto_flotante(px, py - 56, "¡GUARDIÁN SECRETO!", (255, 120, 120), F_MED, 100)
            AUDIO.sfx("alerta")
        # ahora los enemigos pueden entrar y la sala cuenta como parte del mapa
        self.cache_dist.clear()
        self.dist_jugador = self.dist_desde(self.celda_jugador())

    def revelar_por_explosion(self, x, y, radio_px):
        for celda, sec in list(SECRETAS.items()):
            px, py = celda[0] * TAM + TAM / 2, celda[1] * TAM + TAM / 2
            if math.hypot(px - x, py - y) <= radio_px + TAM / 2:
                self.revelar_secreto(celda, "bomba")

    # ---------- logica ----------
    def actualizar(self, teclas):
        self.t += 1
        if self.temblor > 0:
            self.temblor -= 1
        if self.aviso_t > 0:
            self.aviso_t -= 1
        for p in self.particulas:
            p.actualizar()
        self.particulas = [p for p in self.particulas if p.vida > 0]
        if len(self.particulas) > 700:
            self.particulas = self.particulas[-700:]
        for tx in self.textos:
            tx.actualizar()
        self.textos = [tx for tx in self.textos if tx.vida > 0]
        for o in self.ondas:
            o[2] -= 1
        self.ondas = [o for o in self.ondas if o[2] > 0]
        for tt in self.toasts:
            tt[2] -= 1
        self.toasts = [tt for tt in self.toasts if tt[2] > 0]
        for lv in self.lavas:
            lv[2] -= 1
        self.lavas = [lv for lv in self.lavas if lv[2] > 0]
        for b in self.banners:
            b[3] -= 1
        self.banners = [b for b in self.banners if b[3] > 0]
        for r in self.rayos:
            r[1] -= 1
        self.rayos = [r for r in self.rayos if r[1] > 0]
        if self.flash_a > 0:
            self.flash_a = max(0, self.flash_a - 6)
        if self.fade > 0 and self.estado != "nivel_completo":
            self.fade = max(0, self.fade - 8)
        if CONFIG["efectos"]:
            self.ambiente.actualizar()

        if self.estado == "muriendo":
            self.timer -= 1
            if self.timer <= 0:
                self.estado = "game_over"
                self.registrar_records()
                self.guardar_partida()
            return
        if self.estado == "nivel_completo":
            self.timer -= 1
            if self.timer < 30:
                self.fade = int(255 * (1 - self.timer / 30))
            if self.t % 4 == 0:  # confeti
                chispas(self.particulas, random.uniform(0, ANCHO), -5,
                        random.choice([f[3] for f in FRUTAS[:N_FRUTAS_NORMALES]]), 1, 0.5, 90, 4, 0.08)
            if self.timer <= 0:
                if self.nivel == MAX_NIVELES:
                    self.estado = "victoria"
                    return
                if self.nivel >= MAX_NIVEL_TOTAL:
                    self.estado = "victoria_final"
                    return
                self.nivel += 1
                self.iniciar_nivel()
            return
        if self.estado != "jugando":
            return

        # --- temporizadores ---
        self.t_nivel += 1
        if self.invulnerable > 0:
            self.invulnerable -= 1
        if self.combo_t > 0:
            self.combo_t -= 1
            if self.combo_t == 0:
                self.combo = 0
        if self.t_estrella > 0:
            self.t_estrella -= 1
            if self.t_estrella == 0:
                self.cadena = 0
        for nombre in ("t_hielo", "t_rafaga", "t_rapido", "t_cereza", "t_uva", "t_cristal"):
            if getattr(self, nombre) > 0:
                setattr(self, nombre, getattr(self, nombre) - 1)
        if self.t_furia > 0:
            self.t_furia -= 1
            self.furia = 100.0 * self.t_furia / 600
            if self.t_furia % 80 == 0:
                self.nova_furia()
            if self.t_furia == 0:
                self.terminar_furia()
        self.sin_dano_t += 1
        if self.sin_dano_t % 240 == 0:
            self.ganar_furia(4)
        emax = PROG.energia_max()
        self.energia = min(emax, self.energia + (0.7 if self.t_furia > 0 else 0.22))
        for k in self.cd:
            if self.cd[k] > 0:
                self.cd[k] -= 1
        self.sig_poder -= 1
        if self.sig_poder <= 0:
            self.sig_poder = 500 if self.es_jefe else self.dif["sig_poder"]
            if len(self.poderes) < 2:
                self.poner_poder()
        self.t_esp -= 1
        if self.t_esp <= 0:
            self.t_esp = random.randint(700, 1100)
            if random.random() < min(0.8, 0.14 * PROG.rareza()):
                self.aparece_especial()
        for lst in (self.frutas_extra, self.especiales):
            for fr in lst:
                if fr.ttl is not None:
                    fr.ttl -= 1
            lst[:] = [fr for fr in lst if fr.ttl is None or fr.ttl > 0]

        # --- movimiento ---
        ix, iy, ox, oy = self.mover_jugador(teclas)
        cx, cy = self.centro_jugador()
        self.revisar_empuje(ix, iy, ox, oy)
        if self.t_rapido > 0 and self.moviendo and self.t % 3 == 0:
            chispas(self.particulas, cx, cy + 6, (255, 200, 80), 2, 1.0, 16, 3, 0.0)
        if self.t_cereza > 0 and self.moviendo and self.t % 4 == 0:
            chispas(self.particulas, cx, cy + 6, (255, 70, 90), 1, 1.2, 14, 3, 0.0)
        if self.t_estrella > 0 and self.t % 2 == 0:
            chispas(self.particulas, cx, cy, random.choice(((255, 230, 90), (255, 255, 255))), 1, 2.0, 22, 3, 0.0)
        if self.t_furia > 0 and self.t % 2 == 0:
            chispas(self.particulas, cx + random.uniform(-8, 8), cy + 4, random.choice(((255, 120, 40), (255, 210, 80))), 1, 1.6, 24, 4, -0.05)
        self.efecto_cosmetico(cx, cy)

        cj = self.celda_jugador()
        self.dist_jugador = self.dist_desde(cj)
        if self.moviendo and self.t % 6 == 0:
            self.habito[self.direccion] = self.habito.get(self.direccion, 0) + 1

        # --- ataques ---
        self.entrada_ataques(teclas, cx, cy)
        self.arma.actualizar(self.particulas)
        for celda in self.arma.golpes_pared:
            if celda in SECRETAS and SECRETAS[celda]["tipo"] in ("disparo", "empuje"):
                self.revelar_secreto(celda, "disparo")
        for e, p in self.arma.revisar_impactos(self.enemigos):
            self.aplicar_impacto(e, p)

        # --- trampas y mecanica del mundo ---
        self.trampas = [tr for tr in self.trampas if tr.actualizar(self)]
        self.mec.actualizar()
        self.mec.actualizar_cambios()
        self.eventos.actualizar()
        self.impactos = [im for im in self.impactos if im.actualizar(self)]
        if self.mascota:
            self.mascota.actualizar(self)
        if self.estado != "jugando":
            return

        # --- El Cazador ---
        if self.cazador is not None:
            if self.t % 6 == 0:
                self.cazador.observar(cj, self.direccion, self.moviendo)
            if not self.cazador_en_juego and self.cazador_vidas > 0 and self.t_nivel > 120:
                self.cazador_espera -= 1
                if self.cazador_espera <= 0:
                    self.aparece_cazador()

        # reaparicion de enemigos eliminados
        for r in self.respawns:
            r[0] -= 1
            if r[0] <= 0 and len(self.enemigos) < 24:
                self.enemigos.append(self.nuevo_enemigo(celda_lejana(cj, 10), r[3], 0, vel=r[1]))
        self.respawns = [r for r in self.respawns if r[0] > 0]

        if self.jefe is not None:
            self.actualizar_jefe(cx, cy, cj)

        # --- enemigos ---
        rect_j = pygame.Rect(int(self.x), int(self.y), ANCHO_PJ, ALTO_PJ)
        hielo = self.t_hielo > 0
        for e in list(self.enemigos):
            if e not in self.enemigos:
                continue
            if e.es_jefe:
                inmovil = hielo and self.mundo != 4 and self.t_hielo > 0.6 * self.dur["hielo"]
                if inmovil:
                    continue
                lento = 0.5 if (hielo and self.mundo == 4) else 1.0
                if getattr(e, "lento", 0) > 0:
                    e.lento -= 1
                    lento *= 0.4
                fm = (1.0, 1.2, 1.4)[e.fase - 1]
                e.ia(self, cj, (cx, cy), False, e.mult * fm * lento)
            else:
                if hielo and self.mundo != 4:  # inmovilizado: no se mueve ni hace dano
                    if self.t % 10 == 0:
                        chispas(self.particulas, e.cx, e.cy, self.tema["acento"], 1, 1.0, 20, 2, 0.0)
                    e.inmovil()
                    continue
                lento = 0.3 if hielo else 1.0
                e.ia(self, cj, (cx, cy), self.t_estrella > 0, lento)
            if e.rect().colliderect(rect_j):
                if self.t_estrella > 0:  # con la estrella, los enemigos se comen
                    if e.es_jefe:
                        self.golpear(e, 2, 0, inv=25)
                    elif e.tipo == TIPO_CAZADOR:
                        self.golpear(e, 2, 0, inv=25)
                    else:
                        self.cadena += 1
                        self.stat("cadena_max", self.cadena, True)
                        self.matar_enemigo(e, 100 * 2 ** min(self.cadena, 4))
                elif self.invulnerable <= 0:
                    self.golpe("enemigo")
                    break

        # --- proyectiles enemigos y charcos ---
        vivos = []
        for p in self.proy_enemigos:
            v = p[5] if len(p) > 5 else 5.0
            p[0] += p[2] * v
            p[1] += p[3] * v
            kind = p[4] if len(p) > 4 else "veneno"
            if es_pared(p[0] + p[2] * 7, p[1] + p[3] * 7) or not (0 < p[0] < ANCHO and 0 < p[1] < ALTO_MAPA):
                chispas(self.particulas, p[0], p[1], KIND_PROY.get(kind, KIND_PROY["veneno"])[1], 6, 2.5, 18, 3, 0.0)
                continue
            if math.hypot(cx - p[0], cy - p[1]) < 14:
                if self.vulnerable():
                    self.golpe("proyectil")
                continue
            vivos.append(p)
        self.proy_enemigos = vivos
        if self.estado == "jugando" and self.vulnerable():
            for lv in self.lavas:
                if math.hypot(cx - lv[0], cy - lv[1]) < 18:
                    self.golpe("lava")
                    break

        # --- recoger cosas ---
        for fr in list(self.frutas):
            if math.hypot(fr.cx - cx, fr.cy - cy) < 20:
                self.frutas.remove(fr)
                self.recoger(fr)
        for fr in list(self.frutas_extra) + list(self.especiales):
            if math.hypot(fr.cx - cx, fr.cy - cy) < 21:
                (self.frutas_extra if fr in self.frutas_extra else self.especiales).remove(fr)
                self.recoger(fr, extra=True)
        for p in list(self.poderes):
            if math.hypot(p.cx - cx, p.cy - cy) < 20:
                self.poderes.remove(p)
                self.activar_poder(p)
        for mo in list(self.monedas_suelo):
            if not mo.actualizar(self):
                self.monedas_suelo.remove(mo)
            elif math.hypot(mo.x - cx, mo.y - cy) < 18:
                self.recoger_moneda(mo)
        for cof in self.cofres:
            if not cof.abierto and math.hypot(cof.x - cx, cof.y - cy) < 22:
                self.abrir_cofre(cof)
        for fg in list(self.fragmentos):
            if math.hypot(fg.x - cx, fg.y - cy) < 20:
                self.fragmentos.remove(fg)
                self.recoger_fragmento(fg)

        # --- fin de nivel: en niveles de jefe hay que derrotarlo ---
        if self.estado == "jugando":
            if self.es_jefe:
                if self.jefe is None:
                    self.completar_nivel()
            elif not self.frutas:
                self.completar_nivel()

    # ---------- movimiento ----------
    def mover_jugador(self, teclas):
        base = VEL_JUGADOR * PROG.vel_mult()
        if self.t_rapido > 0:
            base = max(base, 6 * PROG.vel_mult())
        if self.t_cereza > 0:
            base *= 1.3
        if self.t_furia > 0:
            base *= 1.2
        cj = self.celda_jugador()
        base *= self.mec.mult_vel(cj)
        ix = iy = 0
        if tecla(teclas, "izquierda"):
            ix = -1
            self.direccion = "izquierda"
        if tecla(teclas, "derecha"):
            ix = 1
            self.direccion = "derecha"
        if tecla(teclas, "arriba"):
            iy = -1
            self.direccion = "arriba"
        if tecla(teclas, "abajo"):
            iy = 1
            self.direccion = "abajo"
        self.moviendo = ix != 0 or iy != 0
        ox, oy = self.x, self.y
        if self.mec.inercia:  # glaciar: el personaje resbala
            fr = self.mec.friccion_en(cj)
            acel = 0.055 if fr is None else 0.33
            self.vx += (ix * base - self.vx) * acel
            self.vy += (iy * base - self.vy) * acel
            if abs(self.vx) < 0.04:
                self.vx = 0.0
            if abs(self.vy) < 0.04:
                self.vy = 0.0
            nx = self.x + self.vx
            if hay_colision(nx, self.y, ANCHO_PJ, ALTO_PJ):
                if abs(self.vx) > 3:
                    chispas(self.particulas, *self.centro_jugador(), (230, 245, 255), 5, 2, 14, 2, 0.0)
                self.vx = -self.vx * 0.3
            else:
                self.x = nx
            ny = self.y + self.vy
            if hay_colision(self.x, ny, ANCHO_PJ, ALTO_PJ):
                if abs(self.vy) > 3:
                    chispas(self.particulas, *self.centro_jugador(), (230, 245, 255), 5, 2, 14, 2, 0.0)
                self.vy = -self.vy * 0.3
            else:
                self.y = ny
            self.moviendo = self.moviendo or math.hypot(self.vx, self.vy) > 0.5
        else:
            self.x, self.y = mover(self.x, self.y, ix * base, iy * base)
        return ix, iy, ox, oy

    def revisar_empuje(self, ix, iy, ox, oy):
        """Empujar una pared falsa durante medio segundo la revela."""
        empujadas = set()
        cx, cy = self.centro_jugador()
        for inp, eje in ((ix, "x"), (iy, "y")):
            if not inp:
                continue
            if abs((self.x - ox) if eje == "x" else (self.y - oy)) > 0.05:
                continue
            fx = cx + inp * (ANCHO_PJ / 2 + 4) if eje == "x" else cx
            fy = cy + inp * (ALTO_PJ / 2 + 4) if eje == "y" else cy
            cel = (int(fx // TAM), int(fy // TAM))
            if cel in SECRETAS and SECRETAS[cel]["tipo"] == "empuje":
                empujadas.add(cel)
                self.empuje[cel] = self.empuje.get(cel, 0) + 1
                if self.empuje[cel] % 8 == 0:
                    chispas(self.particulas, fx, fy, (200, 190, 170), 4, 1.5, 16, 2, 0.05)
                if self.empuje[cel] >= 30:
                    self.empuje.pop(cel)
                    self.revelar_secreto(cel)
        for k in list(self.empuje):
            if k not in empujadas:
                self.empuje[k] -= 2
                if self.empuje[k] <= 0:
                    del self.empuje[k]

    def efecto_cosmetico(self, cx, cy):
        ef = EFECTO_POR_ID.get(PROG.efecto) if PROG.efecto else None
        if not ef or not CONFIG["efectos"]:
            return
        t, col = ef["tipo"], ef["color"]
        if t == "estela" and self.moviendo and self.t % 2 == 0:
            chispas(self.particulas, cx, cy + 6, col, 2, 0.8, 22, 4, -0.02)
        elif t == "arcoiris" and self.moviendo and self.t % 2 == 0:
            r, g, b = colorsys.hsv_to_rgb((self.t * 0.02) % 1, 0.8, 1.0)
            chispas(self.particulas, cx, cy + 6, (int(r * 255), int(g * 255), int(b * 255)), 2, 0.6, 26, 4, 0.0)
        elif t == "estrellas" and self.t % 5 == 0:
            chispas(self.particulas, cx + random.uniform(-14, 14), cy - 12, col, 1, 0.6, 30, 3, 0.04)
        elif t == "corazones" and self.t % 9 == 0:
            self.texto_flotante(cx + random.uniform(-10, 10), cy - 12, "♥", col, F_PEQ, 30)
        elif t == "chispas" and self.t % 4 == 0:
            a = random.uniform(0, math.tau)
            chispas(self.particulas, cx + math.cos(a) * 14, cy + math.sin(a) * 14, col, 1, 1.5, 12, 2, 0.0)

    # ---------- ataques ----------
    def usar_ataque(self, nombre):
        coste, cd = ATAQUES[nombre]
        if self.cd[nombre] > 0:
            return False
        if self.t_furia > 0:
            coste, cd = 0, cd // 2
        if self.energia < coste:
            if self.t % 20 == 0:
                AUDIO.sfx("error")
                self.texto_flotante(*self.centro_jugador(), "Sin energía", (180, 200, 255), F_PEQ, 40)
            return False
        self.energia -= coste
        self.cd[nombre] = cd
        return True

    def entrada_ataques(self, teclas, cx, cy):
        furia = self.t_furia > 0

        def pulso(accion):
            ahora = bool(tecla(teclas, accion))
            antes = self.prev.get(accion, False)
            self.prev[accion] = ahora
            return ahora and not antes

        if pulso("bomba") and self.bombas > 0:
            self.detonar()
        ddx, ddy = DIRS[self.direccion]
        dano = PROG.dano() * (2.0 if furia else 1.0)
        if tecla(teclas, "disparo"):
            if furia:
                if self.arma.espera <= 0:
                    self.arma.espera = 8
                    for ang in (-0.22, 0.0, 0.22):
                        a = math.atan2(ddy, ddx) + ang
                        self.arma.lanzar(cx, cy, math.cos(a), math.sin(a), dano * 1.3, radio=8, vel=11, perfora=True, tipo="furia")
                    AUDIO.sfx("rafaga")
                    chispas(self.particulas, cx + ddx * 12, cy + ddy * 12, (255, 130, 50), 6, 2.5, 14, 3, 0.0)
            elif self.arma.disparar(cx, cy, self.direccion, multi=self.t_rafaga > 0, dano=dano):
                AUDIO.sfx("disparo")
                chispas(self.particulas, cx + ddx * 12, cy + ddy * 12, (140, 225, 255), 5, 2.0, 14, 2, 0.0)
                if PROG.mascota == "dragon":
                    chispas(self.particulas, cx + ddx * 16, cy + ddy * 16, (255, 150, 50), 3, 2.0, 14, 3, 0.0)
        # ataque cargado: mantener la tecla y soltar
        if tecla(teclas, "cargado"):
            if self.carga == 0 and self.cd["cargado"] <= 0:
                self.carga = 1
            elif self.carga > 0:
                self.carga = min(90, self.carga + 1)
                if self.carga == 40:
                    AUDIO.sfx("carga")
                    chispas(self.particulas, cx, cy, (255, 230, 120), 14, 3, 20, 3, 0.0)
                if self.carga >= 40 and self.t % 3 == 0:
                    a = random.uniform(0, math.tau)
                    chispas(self.particulas, cx + math.cos(a) * 22, cy + math.sin(a) * 22, (255, 230, 120), 1, 0.2, 10, 2, 0.0)
        elif self.carga > 0:
            if self.carga >= 40 and self.usar_ataque("cargado"):
                k = min(1.5, self.carga / 60)
                self.arma.lanzar(cx, cy, ddx, ddy, dano * 3 * k, radio=int(11 * min(1.3, k)), vel=11.5, perfora=True, tipo="carga")
                AUDIO.sfx("disparo_carga")
                self.temblor = max(self.temblor, 8)
                self.ondas.append([cx, cy, 14, 14, COLORES_ATAQUE["carga"], 50])
                chispas(self.particulas, cx + ddx * 14, cy + ddy * 14, (255, 230, 120), 16, 4, 24, 4, 0.0)
            self.carga = 0
        if pulso("especial") and self.usar_ataque("especial"):
            self.ataque_especial(cx, cy, dano)
        if pulso("rayo") and self.usar_ataque("rayo"):
            self.ataque_rayo(cx, cy, dano)
        if pulso("hielo") and self.usar_ataque("hielo"):
            self.arma.lanzar(cx, cy, ddx, ddy, dano * 0.5, radio=8, vel=7.5, tipo="hielo", congela=170)
            AUDIO.sfx("hielo")
            chispas(self.particulas, cx + ddx * 12, cy + ddy * 12, (170, 235, 255), 10, 2.5, 20, 3, 0.0)
        if pulso("rafaga") and self.usar_ataque("rafaga"):
            for k in range(8):
                a = k * math.pi / 4
                self.arma.lanzar(cx, cy, math.cos(a), math.sin(a), dano, radio=5, vel=9, tipo="rafaga")
            AUDIO.sfx("rafaga")
            self.ondas.append([cx, cy, 12, 12, COLORES_ATAQUE["rafaga"], 40])

    def ataque_especial(self, cx, cy, dano):
        """Estallido: onda de choque alrededor del jugador."""
        radio = 4.5 * TAM
        AUDIO.sfx("especial")
        self.ondas.append([cx, cy, 30, 30, (255, 200, 90), radio])
        self.ondas.append([cx, cy, 22, 22, (255, 255, 255), radio * 0.7])
        self.temblor = max(self.temblor, 18)
        self.flash((255, 220, 140), 60)
        chispas(self.particulas, cx, cy, (255, 200, 90), 36, 6, 40, 5)
        for e in list(self.enemigos):
            if math.hypot(e.cx - cx, e.cy - cy) < radio:
                self.golpear(e, 4 * dano, None, inv=15)
        self.revelar_por_explosion(cx, cy, radio)

    def ataque_rayo(self, cx, cy, dano):
        """Rayo encadenado: salta entre hasta 4 enemigos cercanos."""
        AUDIO.sfx("rayo")
        objetivos, origen = [], (cx, cy)
        for _ in range(4):
            cand = [e for e in self.enemigos if e not in objetivos and math.hypot(e.cx - origen[0], e.cy - origen[1]) < (330 if not objetivos else 170)]
            if not cand:
                break
            e = min(cand, key=lambda q: math.hypot(q.cx - origen[0], q.cy - origen[1]))
            pts = [origen]
            for k in range(1, 5):
                f = k / 5
                pts.append((origen[0] + (e.cx - origen[0]) * f + random.uniform(-9, 9),
                            origen[1] + (e.cy - origen[1]) * f + random.uniform(-9, 9)))
            pts.append((e.cx, e.cy))
            self.rayos.append([pts, 14])
            objetivos.append(e)
            origen = (e.cx, e.cy)
        if not objetivos:  # sin objetivo: un rayo al frente
            dx, dy = DIRS[self.direccion]
            self.rayos.append([[(cx, cy), (cx + dx * 130 + random.uniform(-8, 8), cy + dy * 130 + random.uniform(-8, 8))], 10])
        for e in objetivos:
            chispas(self.particulas, e.cx, e.cy, (255, 250, 150), 14, 4, 24, 3)
            self.golpear(e, 2 * dano, None, inv=12)

    def nova_furia(self):
        cx, cy = self.centro_jugador()
        self.ondas.append([cx, cy, 24, 24, (255, 120, 40), 3.2 * TAM])
        AUDIO.sfx("especial")
        for e in list(self.enemigos):
            if math.hypot(e.cx - cx, e.cy - cy) < 3.2 * TAM:
                self.golpear(e, 2 * PROG.dano(), None, inv=12)

    def aplicar_impacto(self, e, p):
        self.golpear(e, p["dano"], None, inv=8)
        if p["tipo"] == "carga":
            self.temblor = max(self.temblor, 6)
            chispas(self.particulas, e.cx, e.cy, (255, 230, 120), 14, 4, 24, 4)
        if p["congela"] and e in self.enemigos:
            if e.es_jefe:
                e.lento = 200
            else:
                e.congelado = p["congela"]
            chispas(self.particulas, e.cx, e.cy, (170, 235, 255), 16, 3, 28, 3)
            self.texto_flotante(e.cx, e.cy - 24, "¡CONGELADO!", (170, 235, 255), F_PEQ, 50)
        if e in self.enemigos and e.tipo == TIPO_CAZADOR:
            e.paralizado = max(e.paralizado, 40)

    # ---------- El Cazador y especiales ----------
    def aparece_cazador(self):
        cz = self.cazador
        cj = self.celda_jugador()
        cand = [c for c, d in self.dist_jugador.items() if 7 <= d <= 13]
        if not cand:
            cand = [c for c, d in self.dist_jugador.items() if d >= 5] or [celda_lejana(cj, 6)]
        dx, dy = DIRS[self.direccion]
        cand.sort(key=lambda c: -((c[0] - cj[0]) * dx + (c[1] - cj[1]) * dy) + random.uniform(0, 9))
        c = cand[0]
        cz.hp = cz.hp_max
        cz.teletransportar(c)
        cz.aparicion, cz.modo_t, cz.meta, cz.paralizado, cz.congelado = 50, 0, None, 0, 0
        self.enemigos.append(cz)
        self.cazador_en_juego = True
        self.cazador_vidas -= 1
        AUDIO.sfx("cazador")
        self.banner("EL CAZADOR", (190, 120, 255), "Aprende de tus caminos... ¡sorpréndelo!")
        self.flash((150, 80, 255), 90)
        chispas(self.particulas, cz.cx, cz.cy, (170, 90, 255), 30, 4, 40, 4)
        self.ondas.append([cz.cx, cz.cy, 30, 30, (170, 90, 255), 120])

    def cazador_derrotado(self, e):
        self.cazador_en_juego = False
        self.cazador_espera = 1500
        self.stat("cazador_derrotado")
        self.ganar_furia(25)
        self.soltar_monedas(e.cx, e.cy, 12, 3)
        self.banner("¡EL CAZADOR HA CAÍDO!", (190, 120, 255), "Pero volverá..." if self.cazador_vidas > 0 else "")
        if PROG.desbloquear_fragmento("cazador"):
            self.toasts.append(["Historia: nuevo fragmento", HISTORIA_POR_ID["cazador"][1], 320, None])
            self.cola_modales.append(("fragmento", "cazador"))

    def aparece_especial(self):
        pesos = {IDX_DORADA: 50, IDX_CRISTAL: 35, IDX_LEGENDARIA: 12}
        if self.mundo == MUNDO_DIM:
            pesos[IDX_CORAZON] = 40
        tipo = random.choices(list(pesos), weights=list(pesos.values()))[0]
        cs = [c for c, d in DIST_INICIO.items() if d >= 5 and c not in self.celdas_ocupadas() and c not in self.mec.ocupadas()]
        if not cs:
            return
        c = random.choice(cs)
        self.especiales.append(Fruta(c, tipo, ttl=1100 if tipo != IDX_LEGENDARIA else 800))
        AUDIO.sfx("alerta")
        self.texto_flotante(c[0] * TAM + TAM / 2, c[1] * TAM, "¡Fruta rara!", FRUTAS[tipo][3], F_PEQ, 90)

    def abrir_cofre(self, cof):
        cof.abierto = True
        AUDIO.sfx("cofre")
        chispas(self.particulas, cof.x, cof.y, (255, 215, 80), 30, 4, 40, 4)
        self.ondas.append([cof.x, cof.y, 24, 24, (255, 215, 80), 80])
        self.sumar_puntos(cof.puntos, cof.x, cof.y, usar_mult=False)
        self.soltar_monedas(cof.x, cof.y, cof.monedas, 2)
        self.texto_flotante(cof.x, cof.y - 30, "¡COFRE!", (255, 230, 110), F_MED, 80)
        self.stat("cofres")

    def recoger_fragmento(self, fg):
        AUDIO.sfx("secreto")
        chispas(self.particulas, fg.x, fg.y, (255, 235, 150), 20, 3, 30, 3)
        if PROG.desbloquear_fragmento(fg.id):
            self.cola_modales.append(("fragmento", fg.id))
            self.notificar([])
        self.sumar_puntos(300, fg.x, fg.y, usar_mult=False)

    def registrar_records(self):
        PROG.record("mejor_combo", self.combo_max)
        PROG.record("max_frutas", self.run_frutas)
        PROG.record("max_enemigos", self.run_enemigos)
        PROG.record("nivel_max", self.nivel)
        self.mejor = max(self.mejor, self.puntos)
        PROG.mejor_puntos = max(PROG.mejor_puntos, self.puntos)
        PROG.maximo("puntos_max", self.puntos)
        PROG.guardar()

    # ---------- dano y muerte ----------
    def matar_enemigo(self, e, pts=None):
        if e not in self.enemigos or e.es_jefe:
            return
        self.enemigos.remove(e)
        info = e.info
        if pts is None:
            pts = info["pts"]
        AUDIO.sfx("matar")
        col = (190, 120, 255) if e.tipo == TIPO_CAZADOR else mezcla(PALETAS_ENEMIGO[e.mundo][e.color % len(PALETAS_ENEMIGO[e.mundo])][0], 1.1)
        chispas(self.particulas, e.cx, e.cy, col, 26, 4.5, 40, 4)
        self.ondas.append([e.cx, e.cy, 12, 12, col, 44])
        self.avanzar_combo()
        self.sumar_puntos(pts, e.cx, e.cy, color=(255, 255, 255))
        self.energia = min(PROG.energia_max(), self.energia + 5)
        self.temblor = max(self.temblor, 6)
        self.stat("enemigos")
        self.run_enemigos += 1
        self.progreso_mision("enemigos")
        if getattr(e, "guardian", False):
            self.guardian = None
            self.soltar_monedas(e.cx, e.cy, 36, 4)
            self.texto_flotante(e.cx, e.cy - 40, "¡GUARDIÁN DERROTADO!", (255, 230, 110), F_MED, 100)
            self.stat("guardianes")
            self.ganar_furia(20)
            return
        self.ganar_furia(25 if e.tipo == TIPO_CAZADOR else 6)
        if e.tipo == TIPO_CAZADOR:
            self.cazador_derrotado(e)
            return
        self.soltar_monedas(e.cx, e.cy, info["monedas"])
        if not e.invasor:
            self.respawns.append([self.dif["respawn"], e.vel, e.color, e.tipo])

    def golpear(self, e, dano=99, pts=100, inv=10, trampa=False):
        """Dano a un enemigo: los normales mueren, los resistentes y el jefe pierden vida."""
        if e.es_jefe:
            if e.inv > 0:
                return
            dmg = min(dano, 8)
            e.hp -= dmg
            e.inv = inv
            chispas(self.particulas, e.cx, e.cy, (255, 230, 150), 10, 4, 24, 3)
            AUDIO.sfx("matar")
            self.puntos += int(10 * dmg)
            self.texto_flotante(e.cx, e.cy - 42, f"-{dmg:g}" if dmg == int(dmg) else f"-{dmg:.1f}", (255, 120, 120), F_MED, 60)
            self.ganar_furia(1.2)
            if trampa:
                self.stat("trampas")
            if e.hp <= 0:
                self.derrotar_jefe(e)
        else:
            if trampa:
                self.stat("trampas")
            if e.hp_max > 1 and dano < 50:
                e.hp -= dano
                e.flash = 12
                chispas(self.particulas, e.cx, e.cy, (255, 220, 160), 8, 3, 18, 3)
                AUDIO.sfx("disparo")
                if e.tipo == TIPO_CAZADOR:
                    e.paralizado = max(e.paralizado, 30)
                if e.hp > 0:
                    self.texto_flotante(e.cx, e.cy - 24, f"-{dano:.1f}".rstrip("0").rstrip("."), (255, 200, 150), F_PEQ, 40)
                    return
            self.matar_enemigo(e, pts)

    def derrotar_jefe(self, b):
        if self.jefe is None:
            return
        self.jefe = None
        for e in list(self.enemigos):
            chispas(self.particulas, e.cx, e.cy, (255, 255, 255), 10, 4, 30, 3)
        self.enemigos = []
        self.respawns = []
        self.proy_enemigos = []
        self.lavas = []
        self.impactos = []
        self.efecto_jefe = {}
        self.cazador_en_juego = False
        self.guardian = None
        self.boss_oscuro = self.boss_ventisca = False
        self.boss_tinte = None
        colores = [(255, 230, 140), (255, 120, 90), (140, 220, 255), (200, 140, 255)]
        for _ in range(8):
            chispas(self.particulas, b.cx + random.uniform(-26, 26), b.cy + random.uniform(-26, 26),
                    random.choice(colores), 22, 5.5, 55, 5)
        self.ondas.append([b.cx, b.cy, 40, 40, (255, 230, 140), 280])
        self.temblor = 40
        self.flash((255, 255, 255), 200)
        pts = 1000 + 300 * min(self.mundo, 10)
        self.puntos += pts
        self.texto_flotante(b.cx, b.cy - 40, f"¡JEFE DERROTADO!  +{pts}", (255, 240, 130), F_MED, 130)
        self.stat("jefes")
        perfecto = self.vidas >= self.vidas_inicio
        if perfecto:
            self.stat("jefes_perfectos")
            self.progreso_mision("jefe_perfecto")
        monedas = 40 + 10 * self.mundo
        self.soltar_monedas(b.cx, b.cy, monedas, 5)
        skin, tareas = PROG.desbloquear_jefe(self.mundo)
        if skin:
            self.toasts.append(["¡Skin desbloqueada!", skin["nombre"], 320, None])
        self.notificar(tareas)
        if self.mundo == MUNDO_DIM:
            self.stat("dimension_completa", 1, True)
        self.registrar_records()

    # ---------- jefes: 3 fases ----------
    FASES_TXT = {
        0: ("Invoca más rápido y lanza huesos", "¡DANZA MACABRA! Lluvia de huesos y refuerzos"),
        1: ("Embiste más seguido y aúlla", "¡Se enfurece! Garras y embestidas dobles en la oscuridad"),
        2: ("Veneno triple", "¡Lluvia de veneno y tormenta de arena!"),
        3: ("Charcos más rápido y erupciones", "¡Meteoritos y fuego por todas partes!"),
        4: ("Pisotones y bolas de nieve", "¡VENTISCA! Pisotones en cadena"),
        5: ("Láser más rápido y drones", "¡SOBRECARGA! Láser cruzado"),
        6: ("Saltos más rápidos y lengua venenosa", "¡Charcos tóxicos por todo el pantano!"),
        7: ("Enjambre de murciélagos", "¡Oscuridad total y picadas!"),
        8: ("Rayos desde las nubes", "¡TORMENTA ELÉCTRICA! Picadas feroces"),
        9: ("Saltos dimensionales", "¡El laberinto cobra vida!"),
        10: ("Láser y sombras", "¡EL CORAZÓN LATE FURIOSO! Todo el laberinto se mueve"),
    }
    KIND_FINAL = {0: "hueso", 1: "bala", 2: "veneno", 3: "fuego", 4: "nieve", 5: "rayo", 6: "veneno", 7: "sonar", 8: "rayo", 9: "sonar", 10: "corazon"}

    def cambio_fase(self, b, nueva):
        b.fase = nueva
        b.fase_t = 0
        b.inv = 70
        self.efecto_jefe = {}
        self.proy_enemigos = []
        AUDIO.sfx("fase")
        col = (255, 150, 50) if nueva == 2 else (255, 60, 60)
        self.flash((255, 255, 255), 190)
        self.temblor = max(self.temblor, 40)
        self.banner(f"¡FASE {nueva}!", col, self.FASES_TXT.get(self.mundo, ("", ""))[nueva - 2])
        self.ondas.append([b.cx, b.cy, 40, 40, col, 330])
        chispas(self.particulas, b.cx, b.cy, col, 50, 6, 50, 5)
        for _ in range(2):
            if len(self.enemigos) < 10:
                self.enemigos.append(self.nuevo_enemigo(b.celda(), self.tipo_enemigo(random.randrange(6)), 0))
        if nueva == 3:
            m = self.mundo
            self.boss_tinte = (255, 30, 30)
            if m in (1, 7):
                self.boss_oscuro = True
            if m == 4:
                self.boss_ventisca = True
            if m == 2 and hasattr(self.mec, "forzada"):
                self.mec.forzada = True
            if m in (5, 9, 10, 3):
                self.mec.programar_cambios(4, 50)
        self.actualizar_musica()

    def actualizar_jefe(self, cx, cy, cj):
        """Ataques del jefe: cada mundo tiene los suyos y cambian con cada fase."""
        b = self.jefe
        b.t += 1
        b.fase_t += 1
        if b.inv > 0:
            b.inv -= 1
        b.mult = 1.0
        b.aviso = False
        nueva = b.fase_actual()
        if nueva > b.fase:
            self.cambio_fase(b, nueva)
        if self.t_hielo > 0.6 * self.dur["hielo"] and self.mundo != 4:
            return  # congelado: no ataca
        if b.fase == 3 and not b.final_hecho and b.hp <= b.hp_max * 0.08:
            b.final_hecho = True
            self.efecto_jefe = {"final": dict(t=200)}
            self.banner("¡ATAQUE FINAL!", (255, 60, 60), "¡Aguanta!")
            self.flash((255, 60, 60), 160)
            AUDIO.sfx("fase")
            b.inv = 60
        fin = self.efecto_jefe.get("final")
        if fin is not None:
            fin["t"] -= 1
            b.mult = 0.0
            b.aviso = True
            kind = self.KIND_FINAL.get(self.mundo, "veneno")
            if fin["t"] % 7 == 0:
                for k in range(3):
                    a = fin["t"] * 0.21 + k * math.tau / 3
                    self.disparar_enemigo(b.cx, b.cy, math.cos(a), math.sin(a), kind, 3.4)
            if fin["t"] <= 0:
                self.efecto_jefe.pop("final", None)
                for k in range(20):
                    a = k * math.tau / 20
                    self.disparar_enemigo(b.cx, b.cy, math.cos(a), math.sin(a), kind, 3.0)
                self.temblor = max(self.temblor, 30)
                self.ondas.append([b.cx, b.cy, 30, 30, (255, 90, 90), 300])
            return
        acciones = {}
        for fmin, cada, acc, par in JEFE_ATAQUES[self.mundo]:
            if fmin <= b.fase and (acc not in acciones or fmin >= acciones[acc][0]):
                acciones[acc] = (fmin, cada, par)
        for acc, (fmin, cada, par) in acciones.items():
            self.accion_jefe(b, acc, cada, par, cx, cy, cj)

    def accion_jefe(self, b, acc, cada, par, cx, cy, cj):
        t = b.t
        if acc == "invocar":
            if t % cada == 0 and len(self.enemigos) < 10:
                for _ in range(par.get("n", 1)):
                    self.enemigos.append(self.nuevo_enemigo(b.celda(), par.get("tipo", 0), t // cada))
                chispas(self.particulas, b.cx, b.cy, (190, 140, 255), 22, 4, 40, 4)
                self.texto_flotante(b.cx, b.cy - 44, "¡Invoca!", (220, 180, 255), F_MED, 60)
        elif acc == "anillo":
            if t % cada == 0:
                n = par.get("n", 8)
                a0 = t * 0.07 if par.get("giro") else 0.0
                for k in range(n):
                    a = a0 + k * math.tau / n
                    self.disparar_enemigo(b.cx, b.cy, math.cos(a), math.sin(a), par.get("kind", "veneno"), par.get("vel", 3.2))
                AUDIO.sfx("rafaga")
        elif acc == "abanico":
            if t % cada == 0:
                n = par.get("n", 1)
                dxp, dyp = cx - b.cx, cy - b.cy
                if n == 1:
                    if abs(dxp) > abs(dyp):
                        d = (1 if dxp > 0 else -1, 0)
                    else:
                        d = (0, 1 if dyp > 0 else -1)
                    self.disparar_enemigo(b.cx, b.cy, d[0], d[1], par.get("kind", "veneno"), 5.0)
                else:
                    base = math.atan2(dyp, dxp)
                    for i in range(n):
                        a = base + (i - (n - 1) / 2) * 0.3
                        self.disparar_enemigo(b.cx, b.cy, math.cos(a), math.sin(a), par.get("kind", "veneno"), 4.6)
                AUDIO.sfx("disparo")
        elif acc == "lluvia":
            if t % cada == 0:
                for _ in range(par.get("n", 2)):
                    x, y = cx + random.uniform(-120, 120), cy + random.uniform(-120, 120)
                    if not es_pared(x, y):
                        self.impactos.append(Impacto(x, y, 62, par.get("radio", 30), par.get("color", (255, 120, 60)),
                                                     dej_lava=par.get("lava", 0)))
        elif acc == "charcos":
            if t % cada == 0 and len(self.lavas) < 16:
                self.lavas.append([b.cx, b.cy, 330])
        elif acc == "escenario":
            if t % cada == 0:
                self.mec.programar_cambios(par.get("n", 3), 50)
        elif acc == "embestida":
            st = self.efecto_jefe.get("emb")
            if st is None and t % cada == 0:
                st = self.efecto_jefe["emb"] = dict(f=0, rep=2 if par.get("doble") else 1)
            if st is not None:
                st["f"] += 1
                f = st["f"]
                if par.get("salto"):
                    if f < 40:
                        b.mult = 0.0
                        b.aviso = True
                    else:
                        cs = [c for c, d in self.dist_jugador.items() if 3 <= d <= 5]
                        if cs:
                            chispas(self.particulas, b.cx, b.cy, (255, 255, 255), 20, 4, 30, 3)
                            b.teletransportar(random.choice(cs))
                        self.ondas.append([b.cx, b.cy, 26, 26, (255, 210, 120), 90])
                        self.temblor = max(self.temblor, 16)
                        AUDIO.sfx("bomba")
                        if math.hypot(cx - b.cx, cy - b.cy) < 70 and self.vulnerable():
                            self.golpe("salto")
                        del self.efecto_jefe["emb"]
                else:
                    if f <= 45:
                        b.mult = 0.0
                        b.aviso = True
                    elif f <= 90:
                        b.mult = par.get("mult", 2.3)
                    elif st["rep"] > 1:
                        st["rep"] -= 1
                        st["f"] = 0
                    else:
                        del self.efecto_jefe["emb"]
        elif acc == "pisoton":
            p = self.efecto_jefe.get("pisoton")
            av = par.get("aviso", 60)
            if p is None and t % cada == 0:
                p = self.efecto_jefe["pisoton"] = [b.cx, b.cy, av, av]
            if p is not None:
                b.mult = 0.0
                b.aviso = True
                p[2] -= 1
                if p[2] <= 0:
                    del self.efecto_jefe["pisoton"]
                    self.ondas.append([p[0], p[1], 26, 26, (170, 225, 255), 125])
                    self.temblor = 22
                    chispas(self.particulas, p[0], p[1], (200, 235, 255), 30, 6, 40, 4)
                    AUDIO.sfx("bomba")
                    if math.hypot(cx - p[0], cy - p[1]) < 125 and self.vulnerable():
                        self.golpe("pisoton")
        elif acc == "laser":
            laser = self.efecto_jefe.get("laser")
            if laser is None and t % cada == max(0, cada - 70):
                if par.get("cruz"):
                    segs = [("h", self.segmento(cj, "h")), ("v", self.segmento(cj, "v"))]
                else:
                    eje = random.choice("hv")
                    segs = [(eje, self.segmento(cj, eje))]
                laser = self.efecto_jefe["laser"] = dict(segs=segs, t=70)
            if laser is not None:
                laser["t"] -= 1
                b.mult = 0.4
                if 0 < laser["t"] <= 25 and self.vulnerable() and any(cj in seg for _, seg in laser["segs"]):
                    self.golpe("laser")
                if laser["t"] <= 0:
                    self.efecto_jefe.pop("laser", None)

    # ---------- fin de nivel ----------
    def completar_nivel(self):
        bonus = 100 * self.nivel + 50 * self.vidas + (500 if self.es_jefe else 0)
        estrellas = 2 + (15 if self.es_jefe else 0)
        monedas = 5 + self.nivel // 2 + ((30 + 5 * self.mundo) if self.es_jefe else 0)
        self.estado = "nivel_completo"
        self.timer = 180
        extra_txt = []
        seg = self.t_nivel / FPS
        if not self.es_jefe and self.t_nivel < self.dif["tiempo_par"] * FPS:
            monedas += 5 + self.nivel // 5
            extra_txt.append("¡Rápido!")
            self.stat("rapidos")
        if not self.recibio_dano:
            monedas += 5
            extra_txt.append("¡Sin daño!")
        m = self.mision
        if not m["hecha"]:
            if m["tipo"] == "sin_dano" and not self.recibio_dano:
                self.mision_cumplida()
            elif m["tipo"] == "rapido" and seg < m["meta"]:
                self.mision_cumplida()
        self.extra_txt = "  ".join(extra_txt)
        if self.nivel == MAX_NIVELES:
            bonus += 500 * self.vidas
            estrellas += 50
            monedas += 100
            self.timer = 260
            AUDIO.sfx("victoria")
            PROG.dim_desbloqueada = True
            PROG.desbloquear_fragmento("fin_50")
            self.stat("dimension", 1, True)
            self.cola_modales.append(("cinematica", "fin_50"))
        elif self.nivel >= MAX_NIVEL_TOTAL:
            bonus += 1000 * self.vidas
            estrellas += 100
            monedas += 200
            self.timer = 260
            AUDIO.sfx("victoria")
            PROG.desbloquear_fragmento("fin_dim")
            PROG.dim_completa = True
            self.cola_modales.append(("cinematica", "fin_dim"))
        else:
            AUDIO.sfx("nivel")
            if self.nivel % NIVELES_POR_MUNDO == 0 and self.vidas < self.vidas_max:
                self.vidas += 1  # vida extra al terminar cada mundo
                self.vida_extra = True
        self.puntos += bonus
        self.bonus = bonus
        self.bonus_monedas = monedas
        self.estrellas_nivel = estrellas
        self.mejor = max(self.mejor, self.puntos)
        PROG.ganar_estrellas(estrellas)
        PROG.mejor_puntos = max(PROG.mejor_puntos, self.puntos)
        self.notificar(PROG.ganar_monedas(monedas))
        self.stat("niveles")
        self.stat("nivel_max", self.nivel, True)
        self.stat("puntos_max", self.puntos, True)
        if not self.recibio_dano:
            self.stat("sin_dano")
        if self.nivel >= MAX_NIVELES:
            self.stat("victorias")
        if self.nivel >= MAX_NIVEL_TOTAL:
            self.stat("dimension_completa", 1, True)
        if not self.es_jefe:
            PROG.record("tiempo_rapido", int(seg), menor=True)
        self.registrar_records()
        self.guardar_partida()

    # ---------- poderes y bomba ----------
    def activar_poder(self, p):
        nombre, txt, color = PODERES[p.tipo]
        txt = TEXTOS_MUNDO[self.mundo].get(p.tipo, txt)
        AUDIO.sfx("poder")
        self.ejecutar_poder(nombre)
        chispas(self.particulas, p.cx, p.cy, color, 24, 4.0, 40, 4)
        chispas(self.particulas, p.cx, p.cy, (255, 255, 255), 8, 3.0, 24, 2)
        self.texto_flotante(p.cx, p.cy - 16, txt, color, F_MED, 80)
        self.puntos += 25
        self.stat("poderes")
        self.stat("poder_" + nombre)
        self.progreso_mision("poderes")

    def ejecutar_poder(self, nombre):
        if nombre == "estrella":
            self.t_estrella = self.dur["estrella"]
            self.cadena = 0
        elif nombre == "hielo":
            self.t_hielo = self.dur["hielo"]
        elif nombre == "bomba":
            self.bombas = min(3, self.bombas + 1)
        elif nombre == "rafaga":
            self.t_rafaga = self.dur["rafaga"]
        elif nombre == "rayo":
            self.t_rapido = self.dur["rapido"]
        elif nombre == "eclipse":
            cx, cy = self.centro_jugador()
            self.flash((255, 210, 100), 170)
            self.ondas.append([cx, cy, 34, 34, (255, 210, 100), 8 * TAM])
            self.temblor = max(self.temblor, 24)
            AUDIO.sfx("especial")
            for e in list(self.enemigos):
                if math.hypot(e.cx - cx, e.cy - cy) < 8 * TAM:
                    self.golpear(e, 3, None, inv=15)
            if self.vidas < self.vidas_max:
                self.vidas += 1
            self.ganar_furia(25)

    def detonar(self):
        """La 'bomba' cambia con el mundo: onda, planta, cactus, meteoritos, avalancha o mina."""
        cx, cy = self.centro_jugador()
        celda = self.celda_jugador()
        px, py = celda[0] * TAM + TAM / 2, celda[1] * TAM + TAM / 2
        m = self.mundo
        if m == 4:  # la avalancha necesita espacio delante
            ddx, ddy = DIRS[self.direccion]
            if es_pared(cx + ddx * 26, cy + ddy * 26):
                self.texto_flotante(cx, cy - 24, "¡Hay una pared!", (255, 200, 200), F_MED, 50)
                return
        self.bombas -= 1
        self.stat("bombas")
        self.revelar_por_explosion(cx, cy, 3 * TAM)
        if m == 0:  # onda expansiva
            AUDIO.sfx("bomba")
            self.ondas.append([cx, cy, 28, 28, None, RADIO_BOMBA * TAM])
            self.temblor = 16
            chispas(self.particulas, cx, cy, (255, 170, 70), 30, 6.0, 40, 5)
            for e in list(self.enemigos):
                if self.dist_jugador.get(e.celda(), 99) <= RADIO_BOMBA:
                    self.golpear(e, 6, None, trampa=True)
        elif m == 1:
            AUDIO.sfx("poder")
            self.trampas.append(PlantaCarnivora(px, py))
            chispas(self.particulas, px, py, (90, 200, 90), 16, 3, 30, 4)
        elif m == 2:
            AUDIO.sfx("poder")
            self.trampas.append(CactusTorreta(px, py))
            chispas(self.particulas, px, py, (120, 220, 130), 16, 3, 30, 4)
        elif m == 3:
            AUDIO.sfx("bomba")
            self.trampas.append(Meteoros())
        elif m == 4:
            AUDIO.sfx("poder")
            ddx, ddy = DIRS[self.direccion]
            self.trampas.append(Avalancha(cx, cy, ddx, ddy))
        else:  # Neon y mundos siguientes
            AUDIO.sfx("poder")
            self.trampas.append(MinaLaser(px, py))
            chispas(self.particulas, px, py, (90, 235, 255), 16, 3, 30, 4)

    # ---------- frutas con habilidades ----------
    def recoger(self, fr, extra=False):
        nombre, _, base, color = FRUTAS[fr.tipo]
        especial = fr.tipo >= N_FRUTAS_NORMALES
        self.avanzar_combo()
        mult = min(mult_combo(self.combo), 5)
        AUDIO.sfx(f"fruta{mult}")
        if nombre == "dorada":
            pts = self.sumar_puntos(base, fr.cx, fr.cy, color=(255, 230, 90))
        else:
            pts = self.sumar_puntos(base, fr.cx, fr.cy)
        if not especial and not extra:
            self.recolectadas += 1
        self.run_frutas += 1
        chispas(self.particulas, fr.cx, fr.cy, color, 18, 3.5, 36, 4)
        chispas(self.particulas, fr.cx, fr.cy, (255, 255, 255), 6, 2.5, 22, 2)
        self.stat("frutas")
        self.stat("fruta_" + nombre)
        if nombre == "manzana":
            self.stat("manzanas")
        if PROG.descubrir_fruta(nombre):
            self.toasts.append(["Fruta descubierta", nombre.capitalize(), 200, None])
        self.progreso_mision("frutas_rapido")
        self.dar_monedas(1 if not especial else 5, fr.cx, fr.cy)
        self.ganar_furia(3 if not especial else 8)
        self.habilidad_fruta(nombre, fr)

    def habilidad_fruta(self, nombre, fr):
        cx, cy = fr.cx, fr.cy
        if nombre == "cereza":
            self.t_cereza = 300
            self.texto_flotante(cx, cy - 30, "¡VELOCIDAD!", (255, 90, 110), F_PEQ, 60)
        elif nombre == "manzana":
            self.vida_frac += 1
            self.texto_flotante(cx, cy - 30, "+1/3 ♥", (255, 120, 140), F_PEQ, 60)
            AUDIO.sfx("curar")
            if self.vida_frac >= 3:
                self.vida_frac = 0
                if self.vidas < self.vidas_max:
                    self.vidas += 1
                    self.texto_flotante(cx, cy - 46, "¡+1 VIDA!", (255, 120, 140), F_MED, 70)
                else:
                    self.sumar_puntos(150, cx, cy - 20)
        elif nombre == "naranja":
            AUDIO.sfx("bomba")
            self.ondas.append([cx, cy, 24, 24, (255, 170, 50), 3.2 * TAM])
            chispas(self.particulas, cx, cy, (255, 170, 50), 28, 5, 34, 4)
            self.temblor = max(self.temblor, 10)
            for e in list(self.enemigos):
                if math.hypot(e.cx - cx, e.cy - cy) < 3.2 * TAM:
                    self.golpear(e, 3, None, inv=15)
            self.revelar_por_explosion(cx, cy, 3 * TAM)
        elif nombre == "limon":
            AUDIO.sfx("paralisis")
            self.texto_flotante(cx, cy - 30, "¡PARALIZADOS!", (255, 240, 90), F_MED, 70)
            self.ondas.append([cx, cy, 24, 24, (255, 240, 90), 8 * TAM])
            for e in self.enemigos:
                if math.hypot(e.cx - cx, e.cy - cy) < 8 * TAM:
                    if e.es_jefe:
                        e.lento = 150
                    else:
                        e.paralizado = 180
        elif nombre == "uva":
            self.t_uva = 600
            self.texto_flotante(cx, cy - 30, "¡PUNTOS x2!", (190, 120, 240), F_PEQ, 60)
        elif nombre == "legendaria":
            AUDIO.sfx("legendaria")
            self.flash((255, 160, 255), 130)
            self.stat("legendarias")
            op = random.choice(("estrella", "hielo", "rafaga", "rayo", "bomba", "vida", "furia", "estallido"))
            self.texto_flotante(cx, cy - 40, "¡FRUTA LEGENDARIA!", (255, 160, 255), F_MED, 100)
            if op == "vida":
                if self.vidas < self.vidas_max:
                    self.vidas += 1
                self.texto_flotante(cx, cy - 66, "¡Vida!", (255, 140, 160), F_MED, 80)
            elif op == "furia":
                self.ganar_furia(60)
                self.texto_flotante(cx, cy - 66, "¡Furia!", (255, 140, 60), F_MED, 80)
            elif op == "estallido":
                self.ataque_especial(cx, cy, PROG.dano())
            else:
                self.ejecutar_poder(op)
                self.texto_flotante(cx, cy - 66, "¡" + op.upper() + "!", (255, 255, 160), F_MED, 80)
            for a in range(0, 360, 30):
                r, g, b = colorsys.hsv_to_rgb(a / 360, 0.7, 1.0)
                chispas(self.particulas, cx, cy, (int(r * 255), int(g * 255), int(b * 255)), 3, 4, 40, 3)
        elif nombre == "cristal":
            AUDIO.sfx("cristal")
            self.t_cristal = 600
            self.flash((140, 230, 255), 90)
            self.texto_flotante(cx, cy - 40, "¡PUNTOS x3!", (140, 230, 255), F_MED, 90)
        elif nombre == "dorada":
            AUDIO.sfx("dorada")
            self.flash((255, 215, 80), 120)
            self.puntos += 1000
            self.texto_flotante(cx, cy - 40, "¡FRUTA DORADA! +1000", (255, 230, 90), F_MED, 100)
            self.dar_monedas(25, cx, cy)
            for _ in range(3):
                chispas(self.particulas, cx, cy, (255, 215, 60), 20, 5, 44, 4)
        elif nombre == "corazon":
            AUDIO.sfx("corazon")
            self.flash((255, 80, 130), 120)
            if self.vidas < self.vidas_max:
                self.vidas += 1
            self.ganar_furia(30)
            self.texto_flotante(cx, cy - 40, "¡CORAZÓN! +VIDA", (255, 110, 150), F_MED, 90)

    def golpe(self, causa=""):
        if self.estado != "jugando":
            return
        cx, cy = self.centro_jugador()
        self.vidas -= 1
        self.recibio_dano = True
        self.sin_dano_t = 0
        AUDIO.sfx("golpe")
        self.combo = 0
        self.combo_t = 0
        self.temblor = 20
        self.flash((255, 40, 40), 110)
        if self.t_furia <= 0:
            self.furia = max(0.0, self.furia - 15)
        chispas(self.particulas, cx, cy, (80, 230, 120), 34, 5, 45, 4)
        chispas(self.particulas, cx, cy, (255, 90, 90), 16, 4, 35, 3)
        if self.vidas <= 0:
            self.registrar_records()
            self.stat("puntos_max", self.puntos, True)
            self.estado = "muriendo"
            self.timer = 70
            AUDIO.parar_musica()
            AUDIO.sfx("gameover")
            return
        self.colocar_jugador(CELDA_INICIAL)
        self.direccion = "abajo"
        self.invulnerable = self.dif["invulnerable"]
        self.arma.proyectiles = []
        self.proy_enemigos = []
        self.carga = 0
        for e in self.enemigos:  # alejar a los que estan cerca del inicio
            if not e.es_jefe and DIST_INICIO.get(e.celda(), 99) < 6:
                e.teletransportar(celda_lejana(CELDA_INICIAL, 9))

    # ---------- dibujo ----------
    def dibujar_jugador(self, m):
        cx, cy = self.centro_jugador()
        ef = EFECTO_POR_ID.get(PROG.efecto) if PROG.efecto else None
        if self.t_furia > 0:
            g = crear_brillo_cache(34, (255, 100, 30))
            g.set_alpha(int(170 + 80 * math.sin(self.t * 0.3)))
            m.blit(g, (int(cx - 34), int(cy - 34)))
        if ef and ef["tipo"] == "aura" and CONFIG["efectos"]:
            g = crear_brillo_cache(30, ef["color"])
            g.set_alpha(int(150 + 60 * math.sin(self.t * 0.1)))
            m.blit(g, (int(cx - 30), int(cy - 30)))
        if self.t_estrella > 0:
            m.blit(BRILLOS_ESTRELLA[(self.t // 5) % len(BRILLOS_ESTRELLA)], (int(cx - 30), int(cy - 30)))
        elif self.t_rafaga > 0:
            m.blit(BRILLOS_PODER[3], (int(cx - 28), int(cy - 28)))
        if self.t_cristal > 0:
            pygame.draw.circle(m, (140, 230, 255), (int(cx), int(cy)), 19, 1)
        s = math.sin(self.t * 0.5) if self.moviendo else math.sin(self.t * 0.1) * 0.4
        sw = int(28 + 3 * s)
        sh = int(28 - 3 * s)
        spr = pygame.transform.smoothscale(sprite_jugador(self.direccion, self.t), (sw, sh))
        m.blit(SOMBRA, (int(cx - 12), int(cy + 8)))
        m.blit(spr, (int(cx - sw / 2), int(cy + 13 - sh)))
        if self.carga > 0:  # anillo de carga
            k = min(1.0, self.carga / 40)
            col = (255, 230, 120) if self.carga >= 40 else (200, 200, 230)
            pygame.draw.circle(m, col, (int(cx), int(cy)), 14 + int(6 * k), 2)
            if self.carga >= 40:
                pygame.draw.circle(m, (255, 255, 255), (int(cx), int(cy)), 22 + int(2 * math.sin(self.t * 0.5)), 1)

    def estado_enemigos(self):
        if self.t_hielo > 0:
            return ESTADOS_HIELO[self.mundo]
        if self.t_estrella > 0:
            return "parpadeo" if self.t_estrella < 100 else "asustado"
        return None

    def dibujar_efectos_jefe(self, m):
        for lv in self.lavas:  # charcos
            k = min(1.0, lv[2] / 40)
            col = lv[3] if len(lv) > 3 else (255, 90, 30)
            r = int(15 + 2 * math.sin(self.t * 0.2 + lv[0]))
            pygame.draw.ellipse(m, mezcla(col, 0.6 + 0.4 * k), (int(lv[0] - r), int(lv[1] - r * 0.7), r * 2, int(r * 1.4)))
            pygame.draw.ellipse(m, mezcla(col, 1.5), (int(lv[0] - r * 0.5), int(lv[1] - r * 0.3), r, int(r * 0.6)))
        for p in self.proy_enemigos:
            kind = p[4] if len(p) > 4 else "veneno"
            c1, c2 = KIND_PROY.get(kind, KIND_PROY["veneno"])
            g = crear_brillo_cache(14, c2)
            m.blit(g, (int(p[0] - 14), int(p[1] - 14)))
            pygame.draw.circle(m, c1, (int(p[0]), int(p[1])), 8)
            pygame.draw.circle(m, c2, (int(p[0]), int(p[1])), 5)
            pygame.draw.circle(m, (255, 255, 255), (int(p[0] - 1), int(p[1] - 2)), 2)
        p = self.efecto_jefe.get("pisoton")
        if p is not None:  # zona del pisoton
            pulso = 3 if (self.t // 5) % 2 == 0 else 1
            pygame.draw.circle(m, (255, 90, 90), (int(p[0]), int(p[1])), 125, pulso)
            pygame.draw.circle(m, (255, 200, 200), (int(p[0]), int(p[1])), int(125 * (1 - p[2] / max(1, p[3]))), 1)
        lz = self.efecto_jefe.get("laser")
        if lz is not None:  # rayo laser: aviso y disparo
            for eje, seg in lz["segs"]:
                for c in seg:
                    x, y = c[0] * TAM, c[1] * TAM
                    if lz["t"] > 25:
                        if (self.t // 4) % 2 == 0:
                            if eje == "h":
                                pygame.draw.rect(m, (255, 90, 210), (x, y + TAM // 2 - 1, TAM, 3))
                            else:
                                pygame.draw.rect(m, (255, 90, 210), (x + TAM // 2 - 1, y, 3, TAM))
                    else:
                        if eje == "h":
                            pygame.draw.rect(m, (255, 90, 210), (x, y + 6, TAM, TAM - 12))
                            pygame.draw.rect(m, (255, 240, 255), (x, y + 14, TAM, TAM - 28))
                        else:
                            pygame.draw.rect(m, (255, 90, 210), (x + 6, y, TAM - 12, TAM))
                            pygame.draw.rect(m, (255, 240, 255), (x + 14, y, TAM - 28, TAM))
        if "final" in self.efecto_jefe and self.jefe is not None:
            b = self.jefe
            r = 40 + int(14 * math.sin(self.t * 0.4))
            pygame.draw.circle(m, (255, 60, 60), (int(b.cx), int(b.cy)), r, 3)
            pygame.draw.circle(m, (255, 255, 255), (int(b.cx), int(b.cy)), r + 10, 1)

    def dibujar_barra_jefe(self):
        b = self.jefe
        if b is None:
            return
        w = 420
        x = (ANCHO - w) // 2
        y = ALTO_HUD + 10
        panel = pygame.Surface((w + 16, 46), pygame.SRCALPHA)
        pygame.draw.rect(panel, (12, 10, 26, 215), panel.get_rect(), border_radius=10)
        pantalla.blit(panel, (x - 8, y - 4))
        texto(pantalla, self.info["jefe"], F_PEQ, (255, 220, 160), (x, y - 2), desp=1)
        fcol = ((120, 230, 130), (255, 170, 50), (255, 70, 70))[b.fase - 1]
        texto(pantalla, f"FASE {b.fase}/3", fuente(14), fcol, (x + w - 70, y), desp=1)
        pygame.draw.rect(pantalla, (50, 20, 30), (x, y + 20, w, 14), border_radius=7)
        k = max(0.0, b.hp / b.hp_max)
        if k > 0:
            pygame.draw.rect(pantalla, fcol, (x, y + 20, max(6, int(w * k)), 14), border_radius=7)
        for u in (FASE2_HP, FASE3_HP):  # marcas de cambio de fase
            pygame.draw.line(pantalla, (255, 255, 255), (x + int(w * u), y + 18), (x + int(w * u), y + 36), 2)
        pygame.draw.rect(pantalla, (255, 255, 255), (x, y + 20, w, 14), 1, border_radius=7)

    def dibujar_toasts(self):
        for i, (titulo, txt, tiempo, premio) in enumerate(self.toasts[:3]):
            a = min(255, tiempo * 6)
            x = ANCHO - 346
            y = ALTO_HUD + (66 if self.jefe is not None else 12) + i * 62
            panel = pygame.Surface((336, 54), pygame.SRCALPHA)
            pygame.draw.rect(panel, (16, 14, 34, 225), panel.get_rect(), border_radius=12)
            pygame.draw.rect(panel, (255, 208, 60, 255), panel.get_rect(), 2, border_radius=12)
            panel.set_alpha(a)
            pantalla.blit(panel, (x, y))
            ic = (ICONO_TROFEO if premio is not None else ICONO_ESTRELLA).copy()
            ic.set_alpha(a)
            pantalla.blit(ic, (x + 10, y + 14))
            texto(pantalla, titulo, fuente(14), (255, 220, 100), (x + 44, y + 7), desp=1, alfa=a)
            texto(pantalla, txt[:34], fuente(16), (255, 255, 255), (x + 44, y + 26), desp=1, alfa=a)
            if premio is not None:
                r = texto(pantalla, f"+{premio}", fuente(18), (255, 230, 120), (x + 296, y + 16), desp=1, alfa=a)
                pantalla.blit(ICONO_ESTRELLA, (r.right + 2, y + 15))

    def dibujar_banners(self):
        y0 = ALTO_HUD + (130 if self.jefe is not None else 96)
        for i, (titulo, sub, color, t) in enumerate(self.banners[-2:]):
            a = min(255, t * 8)
            franja = pygame.Surface((ANCHO, 62), pygame.SRCALPHA)
            franja.fill((0, 0, 0, int(150 * a / 255)))
            y = y0 + i * 70
            pantalla.blit(franja, (0, y))
            texto_borde(pantalla, titulo, F_GRANDE, color, mezcla(color, 0.3), (ANCHO // 2, y + 24), 2)
            if sub:
                texto(pantalla, sub, F_PEQ, (255, 255, 255), (ANCHO // 2, y + 52), centro=True, alfa=a)

    def dibujar_evento(self):
        ev = self.eventos
        y = ALTO_HUD + (62 if self.jefe is not None else 8)
        if ev.aviso > 0 and (ev.aviso // 8) % 2 == 0:
            d = EVENTOS_DEF[ev.elegido]
            texto_borde(pantalla, f"¡ALERTA! {d['nombre']}", F_MED, d["color"], (30, 20, 10), (ANCHO // 2, y + 16), 2)
        elif ev.activo:
            a = ev.activo
            w = 300
            x = (ANCHO - w) // 2
            panel = pygame.Surface((w + 12, 40), pygame.SRCALPHA)
            pygame.draw.rect(panel, (10, 10, 24, 210), panel.get_rect(), border_radius=10)
            pantalla.blit(panel, (x - 6, y))
            extra = f"  {max(0, a['t']) // FPS + 1}s" if a["tipo"] == "contrarreloj" else ""
            texto(pantalla, a["nombre"] + extra, F_PEQ, a["color"], (ANCHO // 2, y + 8), centro=True, desp=1)
            pygame.draw.rect(pantalla, (40, 40, 60), (x, y + 24, w, 8), border_radius=4)
            k = max(0.0, a["t"] / max(1, a["dur"]))
            pygame.draw.rect(pantalla, a["color"], (x, y + 24, int(w * k), 8), border_radius=4)

    def dibujar_estados(self):
        """Poderes y efectos activos, abajo a la izquierda (sobre la pared inferior)."""
        iconos = iconos_poderes(self.mundo)
        items = []
        if self.t_estrella > 0:
            items.append((iconos[0], self.t_estrella / self.dur["estrella"], None, PODERES[0][2]))
        if self.t_hielo > 0:
            items.append((iconos[1], self.t_hielo / self.dur["hielo"], None, PODERES[1][2]))
        if self.t_rafaga > 0:
            items.append((iconos[3], self.t_rafaga / self.dur["rafaga"], None, PODERES[3][2]))
        if self.t_rapido > 0:
            items.append((iconos[4], self.t_rapido / self.dur["rapido"], None, PODERES[4][2]))
        if self.t_cereza > 0:
            items.append((SPR_FRUTAS_HUD[0], self.t_cereza / 300, None, (255, 80, 100)))
        if self.t_uva > 0:
            items.append((SPR_FRUTAS_HUD[4], self.t_uva / 600, "x2", (190, 120, 240)))
        if self.t_cristal > 0:
            items.append((SPR_FRUTAS_HUD[IDX_CRISTAL], self.t_cristal / 600, "x3", (140, 230, 255)))
        if self.bombas > 0:
            items.append((iconos[2], None, f"x{self.bombas}  [{self.tecla_nombre('bomba')}]", None))
        dibujar_indicador_musica((ANCHO - 150, ALTO - 30))
        x = 14
        y = ALTO - 36
        for ic, k, etiqueta, col in items:
            pantalla.blit(ic, (x, y))
            if k is not None:
                pygame.draw.rect(pantalla, (20, 20, 34), (x + 32, y + 10, 44, 8), border_radius=4)
                pygame.draw.rect(pantalla, col, (x + 32, y + 10, max(2, int(44 * k)), 8), border_radius=4)
                if etiqueta:
                    texto(pantalla, etiqueta, fuente(13), (255, 255, 255), (x + 80, y + 6), desp=1)
                x += 88 if not etiqueta else 112
            else:
                texto(pantalla, etiqueta, F_PEQ, (255, 255, 255), (x + 32, y + 5), desp=1)
                x += 118

    @staticmethod
    def tecla_nombre(accion):
        return pygame.key.name(CONTROLES[accion][0]).upper()[:5]

    def dibujar_hud(self):
        pantalla.blit(HUD_BG, (0, 0))
        pygame.draw.rect(pantalla, self.tema["acento"], (0, ALTO_HUD - 3, ANCHO, 3))
        gris = (150, 155, 185)
        texto(pantalla, "PUNTOS", F_PEQ, gris, (16, 4), desp=1)
        texto(pantalla, f"{self.puntos:06d}", F_HUD, (255, 255, 255), (16, 22))
        # vidas (con corazon parcial por las manzanas)
        texto(pantalla, "VIDAS", F_PEQ, gris, (150, 4), desp=1)
        n = self.vidas_max
        sp = min(26, 178 // max(1, n))
        for i in range(n):
            px = 150 + i * sp
            if i < self.vidas:
                pantalla.blit(SPR_CORAZON_S, (px, 26))
            else:
                pantalla.blit(SPR_CORAZON_VACIO_S, (px, 26))
                if i == self.vidas and self.vida_frac > 0:
                    h = int(24 * self.vida_frac / 3)
                    pantalla.blit(SPR_CORAZON_S, (px, 26 + 24 - h), pygame.Rect(0, 24 - h, 24, h))
        texto(pantalla, "FRUTAS", F_PEQ, gris, (340, 4), desp=1)
        pantalla.blit(SPR_FRUTAS_HUD[1], (340, 24))
        texto(pantalla, f"{self.total_frutas - len(self.frutas)}/{self.total_frutas}", F_HUD, (255, 255, 255), (374, 22))
        texto(pantalla, "COMBO", F_PEQ, gris, (448, 4), desp=1)
        if self.combo_t > 0 and self.combo >= 1:
            mult = mult_combo(self.combo)
            col = (255, 225, 90) if mult < 10 else ((255, 150, 60) if mult < 20 else (255, 70, 70))
            texto(pantalla, f"x{mult}", F_HUD, col, (448, 22))
            k = self.combo_t / COMBO_FRAMES
            pygame.draw.rect(pantalla, (50, 50, 70), (506, 36, 52, 8), border_radius=4)
            pygame.draw.rect(pantalla, col, (506, 36, int(52 * k), 8), border_radius=4)
            texto(pantalla, f"{self.combo} seguidos", fuente(12), gris, (506, 46), desp=1)
        else:
            texto(pantalla, "x1", F_HUD, (95, 98, 125), (448, 22))
        texto(pantalla, "NIVEL", F_PEQ, gris, (572, 4), desp=1)
        if self.nivel > MAX_NIVELES:
            lv = f"DIM {self.nivel - MAX_NIVELES}/5"
        else:
            lv = f"{self.nivel}/{MAX_NIVELES}"
        texto(pantalla, f"{lv} · {self.tema['nombre']}", fuente(21), (255, 255, 255), (572, 26))
        texto(pantalla, "COINS", F_PEQ, gris, (770, 4), desp=1)
        pantalla.blit(SPR_MONEDA, (770, 24))
        texto(pantalla, f"{PROG.monedas}", F_HUD, (255, 220, 90), (798, 22))
        texto(pantalla, "RECORD", F_PEQ, gris, (885, 4), desp=1)
        texto(pantalla, f"{max(self.mejor, self.puntos):06d}", F_HUD, (255, 215, 90), (885, 22))
        # ---- fila 2 ----
        emax = PROG.energia_max()
        texto(pantalla, "ENERGÍA", fuente(13), gris, (16, 62), desp=1)
        pygame.draw.rect(pantalla, (20, 24, 44), (80, 64, 110, 11), border_radius=5)
        pygame.draw.rect(pantalla, (90, 190, 255), (80, 64, max(2, int(110 * self.energia / emax)), 11), border_radius=5)
        pygame.draw.rect(pantalla, (170, 190, 230), (80, 64, 110, 11), 1, border_radius=5)
        furia_on = self.t_furia > 0
        texto(pantalla, "¡FURIA!" if furia_on else f"FURIA {int(self.furia)}%", fuente(13),
              (255, 140, 60) if furia_on or self.furia > 80 else gris, (204, 62), desp=1)
        pygame.draw.rect(pantalla, (40, 18, 18), (284, 64, 130, 11), border_radius=5)
        if self.furia > 0:
            col = (255, 90 + int(60 * math.sin(self.t * 0.3)), 30) if furia_on else (255, 140, 50)
            pygame.draw.rect(pantalla, col, (284, 64, max(2, int(130 * self.furia / 100)), 11), border_radius=5)
        pygame.draw.rect(pantalla, (255, 170, 120), (284, 64, 130, 11), 1, border_radius=5)
        # ataques
        defs = (("cargado", (255, 230, 120)), ("especial", (255, 200, 90)), ("rayo", (255, 250, 150)),
                ("hielo", (170, 235, 255)), ("rafaga", (255, 170, 255)))
        for i, (nom, col) in enumerate(defs):
            x = 432 + i * 38
            coste, cdm = ATAQUES[nom]
            ok = self.cd[nom] <= 0 and (self.energia >= coste or furia_on)
            r = pygame.Rect(x, 60, 34, 26)
            pygame.draw.rect(pantalla, (22, 22, 40), r, border_radius=6)
            pygame.draw.rect(pantalla, col if ok else (70, 70, 96), r, 2, border_radius=6)
            if self.cd[nom] > 0:
                h = int(26 * self.cd[nom] / max(1, cdm // (2 if furia_on else 1)))
                s = pygame.Surface((34, h), pygame.SRCALPHA)
                s.fill((0, 0, 0, 150))
                pantalla.blit(s, (x, 60 + 26 - h))
            texto(pantalla, self.tecla_nombre(nom)[:2], fuente(15), col if ok else (110, 110, 135), r.center, centro=True, desp=1)
        # mision de nivel
        m = self.mision
        col = (140, 255, 160) if m["hecha"] else (255, 235, 150)
        prog = "¡HECHA!" if m["hecha"] else f"{min(m['prog'], m['meta'])}/{m['meta']}" if m["tipo"] not in ("sin_dano", "rapido", "jefe_perfecto", "secreto") else ""
        texto(pantalla, f"Misión: {m['texto']} {prog}", fuente(14), col, (630, 60), desp=1)
        # El Cazador
        cz = self.cazador
        if cz is not None and self.cazador_en_juego:
            texto(pantalla, f"CAZADOR IA{cz.nivel_ia} · aprende {int(cz.aprendizaje * 100)}%", fuente(13), (200, 150, 255), (630, 76), desp=1)

    def aplicar_niebla(self, m, n):
        cx, cy = self.centro_jugador()
        capa = self.capa_niebla
        capa.fill((*n["color"], n["alfa"]))
        if n["tipo"] != "tormenta":
            r = n["radio"] or 140
            if r <= 330:
                r = max(40, int(round(r / 20) * 20))
                capa.blit(luz_grad(r), (cx - r, cy - r), special_flags=pygame.BLEND_RGBA_SUB)
                if n.get("linterna"):
                    dx, dy = DIRS[self.direccion]
                    r2 = int(r * 0.85)
                    capa.blit(luz_grad(r2), (cx + dx * r * 0.75 - r2, cy + dy * r * 0.75 - r2), special_flags=pygame.BLEND_RGBA_SUB)
            for lx, ly, lr in n.get("luces", []):
                lr = int(lr)
                capa.blit(luz_grad(lr), (lx - lr, ly - lr), special_flags=pygame.BLEND_RGBA_SUB)
            if n["tipo"] == "cueva":  # frutas luminosas
                for o in self.frutas + self.frutas_extra + self.especiales + self.poderes:
                    capa.blit(luz_grad(36), (o.cx - 36, o.cy - 36), special_flags=pygame.BLEND_RGBA_SUB)
                for o in self.cofres + self.fragmentos:
                    capa.blit(luz_grad(40), (o.x - 40, o.y - 40), special_flags=pygame.BLEND_RGBA_SUB)
        m.blit(capa, (0, 0))
        if n["tipo"] == "cueva":  # los enemigos ocultos solo muestran los ojos
            luces = n.get("luces", [])
            for e in self.enemigos:
                if e.es_jefe:
                    continue
                d = math.hypot(e.cx - cx, e.cy - cy)
                if d < n["radio"] * 0.95 or d > 300 or any(math.hypot(e.cx - lx, e.cy - ly) < lr for lx, ly, lr in luces):
                    continue
                if (self.t // 18 + id(e)) % 7 != 0:
                    for ox in (-4, 4):
                        pygame.draw.ellipse(m, (255, 60, 60), (int(e.cx + ox - 2), int(e.cy - 5), 4, 6))

    def calcular_niebla(self):
        cand = []
        for n in (self.mec.niebla(), self.eventos.niebla()):
            if n:
                cand.append(n)
        if self.boss_oscuro:
            cand.append(dict(tipo="oscuro", radio=130, color=(10, 0, 20), alfa=225))
        if self.boss_ventisca:
            cand.append(dict(tipo="arena", radio=190, color=(225, 238, 250), alfa=175))
        return max(cand, key=lambda q: q["alfa"]) if cand else None

    def dibujar(self):
        m = lienzo
        t = self.t
        m.blit(self.fondo, (0, 0))
        self.mec.dibujar_suelo(m, t)
        self.mec.dibujar_cambios(m, t)
        for im in self.impactos:
            im.dibujar(m, t)
        for tr in self.trampas:
            tr.dibujar(m, t)
        self.dibujar_efectos_jefe(m)
        self.eventos.dibujar(m, t)
        for fr in self.frutas + self.frutas_extra + self.especiales:
            fr.dibujar(m, t)
        for p in self.poderes:
            p.dibujar(m, t)
        for mo in self.monedas_suelo:
            mo.dibujar(m, t)
        for c in self.cofres:
            c.dibujar(m, t)
        for f in self.fragmentos:
            f.dibujar(m, t)
        est = self.estado_enemigos()
        for e in self.enemigos:
            e.dibujar(m, t, est)
        if self.mascota:
            self.mascota.dibujar(m, t)
        self.arma.dibujar(m)
        visible = self.estado in ("jugando", "nivel_completo")
        if visible and not (self.invulnerable > 0 and (self.invulnerable // 4) % 2 == 0):
            self.dibujar_jugador(m)
        for p in self.particulas:
            p.dibujar(m)
        for pts, v in self.rayos:
            ps = [(int(a), int(b)) for a, b in pts]
            if len(ps) >= 2:
                pygame.draw.lines(m, (120, 160, 255), False, ps, 7)
                pygame.draw.lines(m, (255, 255, 255), False, ps, 3)
        for o in self.ondas:
            k = 1 - o[2] / o[3]
            r = max(3, int(o[5] * k))
            c1 = o[4] or (255, 170, 80)
            pygame.draw.circle(m, c1, (int(o[0]), int(o[1])), r, max(1, int(9 * (1 - k))))
            pygame.draw.circle(m, mezcla(c1, 1.4), (int(o[0]), int(o[1])), max(2, int(r * 0.85)), max(1, int(4 * (1 - k))))
        self.mec.dibujar_encima(m, t)
        if CONFIG["efectos"]:
            self.ambiente.dibujar(m, t)
        for tx in self.textos:
            tx.dibujar(m)
        n = self.calcular_niebla()
        if n:
            if not hasattr(self, "capa_niebla"):
                self.capa_niebla = pygame.Surface((ANCHO, ALTO_MAPA), pygame.SRCALPHA)
            self.aplicar_niebla(m, n)
        m.blit(VINETA, (0, 0))
        if CONFIG["efectos"]:
            tinte = TINTE_MUNDO[min(self.mundo, 10)]
            if tinte:
                velo = _velos.get(self.mundo)
                if velo is None:
                    velo = _velos[self.mundo] = pygame.Surface((ANCHO, ALTO_MAPA), pygame.SRCALPHA)
                    velo.fill(tinte)
                m.blit(velo, (0, 0))
            if self.t_furia > 0:
                VINETA_FURIA.set_alpha(int(150 + 90 * math.sin(t * 0.25)))
                m.blit(VINETA_FURIA, (0, 0))
            elif self.vidas <= 1 and self.estado == "jugando":
                VINETA_ROJA.set_alpha(int(110 + 100 * abs(math.sin(t * 0.08))))
                m.blit(VINETA_ROJA, (0, 0))
            if self.mundo == MUNDO_DIM:
                VINETA_DIM.set_alpha(120)
                m.blit(VINETA_DIM, (0, 0))
            if self.boss_tinte and self.jefe is not None:
                velo = pygame.Surface((ANCHO, ALTO_MAPA), pygame.SRCALPHA)
                velo.fill((*self.boss_tinte, 14 + int(14 * math.sin(t * 0.1))))
                m.blit(velo, (0, 0))
        if self.t_hielo > 0 and self.mundo in (0, 4):  # tinte helado
            velo = pygame.Surface((ANCHO, ALTO_MAPA), pygame.SRCALPHA)
            velo.fill((90, 180, 255, 28))
            m.blit(velo, (0, 0))

        ox = oy = 0
        if self.temblor > 0 and CONFIG["efectos"]:
            ox = random.randint(-self.temblor // 3, self.temblor // 3)
            oy = random.randint(-self.temblor // 3, self.temblor // 3)
        pantalla.fill(self.tema["fondo"])
        pantalla.blit(m, (ox, ALTO_HUD + oy))
        self.dibujar_hud()
        self.dibujar_barra_jefe()
        self.dibujar_evento()
        if self.estado in ("jugando", "muriendo"):
            self.dibujar_estados()
        self.dibujar_banners()
        self.dibujar_toasts()

        if self.aviso_t > 0 and self.estado == "jugando":
            a = 255 if self.aviso_t > 40 else int(self.aviso_t * 6.3)
            cy = ALTO_HUD + ALTO_MAPA // 2
            franja = pygame.Surface((ANCHO, 150), pygame.SRCALPHA)
            franja.fill((0, 0, 0, int(160 * a / 255)))
            pantalla.blit(franja, (0, cy - 75))
            t1, t2, t3 = self.aviso
            texto(pantalla, t1, F_GRANDE, (255, 255, 255), (ANCHO // 2, cy - 38), centro=True, alfa=a)
            col2 = (255, 120, 120) if self.es_jefe else self.tema["acento"]
            texto(pantalla, t2, F_MED, col2, (ANCHO // 2, cy + 6), centro=True, alfa=a)
            if t3:
                texto(pantalla, t3, F_PEQ, (255, 210, 120), (ANCHO // 2, cy + 44), centro=True, alfa=a)
        if self.estado == "nivel_completo":
            cy = ALTO_HUD + ALTO_MAPA // 2
            franja = pygame.Surface((ANCHO, 190), pygame.SRCALPHA)
            franja.fill((0, 0, 0, 165))
            pantalla.blit(franja, (0, cy - 85))
            if self.nivel == MAX_NIVELES:
                titulo = "¡50 NIVELES COMPLETADOS!"
            elif self.nivel >= MAX_NIVEL_TOTAL:
                titulo = "¡EL CORAZÓN HA SIDO LIBERADO!"
            elif self.es_jefe:
                titulo = "¡JEFE DERROTADO!"
            else:
                titulo = "¡NIVEL COMPLETADO!"
            texto_borde(pantalla, titulo, F_GRANDE, (255, 235, 120), (90, 50, 0), (ANCHO // 2, cy - 50), 3)
            extra = "     ¡VIDA EXTRA!" if self.vida_extra else ""
            texto(pantalla, f"Bonus +{self.bonus}{extra}", F_MED, (255, 255, 255), (ANCHO // 2, cy - 8), centro=True)
            texto(pantalla, f"+{self.estrellas_nivel} estrellas      +{self.bonus_monedas} Frutacoins", F_MED, (255, 226, 90),
                  (ANCHO // 2, cy + 30), centro=True)
            if getattr(self, "extra_txt", ""):
                texto(pantalla, self.extra_txt, F_MED, (140, 255, 170), (ANCHO // 2, cy + 66), centro=True)
        if self.flash_a > 0 and CONFIG["efectos"]:
            f = pygame.Surface((ANCHO, ALTO_MAPA), pygame.SRCALPHA)
            f.fill((*self.flash_col, min(255, self.flash_a)))
            pantalla.blit(f, (0, ALTO_HUD))
        if self.fade > 0:
            f = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
            f.fill((0, 0, 0, min(255, self.fade)))
            pantalla.blit(f, (0, 0))


TINTE_MUNDO = {0: None, 1: (40, 140, 50, 16), 2: (235, 180, 90, 20), 3: (255, 70, 20, 22), 4: (150, 210, 255, 20),
               5: (255, 60, 220, 18), 6: (80, 110, 40, 26), 7: (30, 20, 80, 26), 8: (170, 210, 255, 14),
               9: (110, 40, 210, 24), 10: (255, 40, 90, 20)}
_velos = {}


# ======================================================
# Pantallas
# ======================================================
K_ARRIBA, K_ABAJO = (pygame.K_UP, pygame.K_w), (pygame.K_DOWN, pygame.K_s)
K_IZQ, K_DER = (pygame.K_LEFT, pygame.K_a), (pygame.K_RIGHT, pygame.K_d)
K_OK = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
K_ATRAS = (pygame.K_ESCAPE, pygame.K_BACKSPACE)


# Estado del raton expresado en las coordenadas virtuales del juego.
# Esto permite que los clics funcionen tambien al cambiar el tamano de la ventana.
_RATON_POS = None
_RATON_CLIC = False


def _raton_a_coordenadas_virtuales(pos):
    """Convierte la posicion real del raton a la superficie virtual del juego."""
    if _ventana is None or pos is None:
        return None
    try:
        w, h = pygame.display.get_surface().get_size()
        k = min(w / ANCHO, h / ALTO)
        tw, th = max(1, int(ANCHO * k)), max(1, int(ALTO * k))
        ox, oy = (w - tw) // 2, (h - th) // 2
        mx, my = pos
        if mx < ox or my < oy or mx >= ox + tw or my >= oy + th:
            return None
        return int((mx - ox) / k), int((my - oy) / k)
    except (ZeroDivisionError, pygame.error):
        return None


def leer_teclas():
    """Lee teclado, rueda y raton. Devuelve (lista_de_teclas, salir)."""
    global _RATON_POS, _RATON_CLIC
    keys, salir = [], False
    _RATON_CLIC = False
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            salir = True
        elif ev.type == pygame.KEYDOWN:
            if es_tecla(ev.key, "musica"):
                AUDIO.alternar()
            else:
                keys.append(ev.key)
        elif ev.type == pygame.MOUSEMOTION:
            _RATON_POS = _raton_a_coordenadas_virtuales(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            _RATON_POS = _raton_a_coordenadas_virtuales(ev.pos)
            _RATON_CLIC = True
        elif ev.type == pygame.MOUSEWHEEL:
            keys.append(pygame.K_UP if ev.y > 0 else pygame.K_DOWN)
    if salir:
        pygame.event.post(pygame.event.Event(pygame.QUIT))
    return keys, salir


def texto_ajustado(surf, txt, fnt, color, x, y, ancho, interlinea=4, sombra=(0, 0, 0), centro=False):
    """Escribe 'txt' partiendo las lineas para que quepan en 'ancho'. Devuelve la 'y' final."""
    linea = ""
    for palabra in txt.split():
        prueba = (linea + " " + palabra).strip()
        if fnt.size(prueba)[0] > ancho and linea:
            texto(surf, linea, fnt, color, (x + (ancho // 2 if centro else 0), y), centro=centro, sombra=sombra, desp=1)
            y += fnt.get_height() + interlinea
            linea = palabra
        else:
            linea = prueba
    if linea:
        texto(surf, linea, fnt, color, (x + (ancho // 2 if centro else 0), y), centro=centro, sombra=sombra, desp=1)
        y += fnt.get_height() + interlinea
    return y


def dibujar_saldo(x, y):
    """Estrellas, Frutacoins y misiones completadas."""
    pantalla.blit(ICONO_ESTRELLA, (x, y))
    r = texto(pantalla, str(PROG.estrellas), F_MED, (255, 232, 110), (x + 30, y - 2), desp=2)
    pantalla.blit(SPR_MONEDA, (r.right + 14, y))
    r = texto(pantalla, str(PROG.monedas), F_MED, (255, 200, 80), (r.right + 42, y - 2), desp=2)
    pantalla.blit(ICONO_TROFEO, (r.right + 14, y - 1))
    texto(pantalla, f"{len(PROG.trofeos)}/{len(TAREAS)}", F_MED, (255, 255, 255), (r.right + 44, y - 2), desp=2)


def encabezado(titulo, sub=None):
    w = F_GRANDE.size(titulo)[0]
    texto_borde(pantalla, titulo, F_GRANDE, (255, 226, 90), (120, 50, 10), (44 + w // 2, 48), 3)
    dibujar_saldo(ANCHO - 400, 36)
    if sub:
        texto(pantalla, sub, F_PEQ, (210, 210, 235), (44, 80), desp=1)


def pie(txt):
    texto(pantalla, txt, F_PEQ, (200, 200, 230), (ANCHO // 2, ALTO - 26), centro=True)
    dibujar_indicador_musica((16, ALTO - 34))


def icono_menu(nombre, x, y, t):
    """Pequeno icono de cada opcion del menu (centrado en x, y)."""
    if nombre == "JUGAR":
        pygame.draw.polygon(pantalla, (120, 240, 140), [(x - 9, y - 12), (x - 9, y + 12), (x + 13, y)])
    elif nombre == "MUNDOS":
        pantalla.blit(pygame.transform.smoothscale(sprite_enemigo(3, 0, (t // 8) % 4, "abajo"), (30, 30)), (x - 15, y - 15))
    elif nombre == "TIENDA":
        pantalla.blit(pygame.transform.scale(SPR_MONEDA, (26, 26)), (x - 13, y - 13))
    elif nombre == "MASCOTAS":
        pantalla.blit(sprite_mascota("perro", t // 10, 30), (x - 15, y - 17))
    elif nombre == "SKINS":
        pantalla.blit(sprite_jugador("abajo", t, tam=30), (x - 15, y - 15))
    elif nombre == "MISIONES":
        pantalla.blit(ICONO_ESTRELLA, (x - 14, y - 12))
    elif nombre == "LOGROS":
        pantalla.blit(ICONO_TROFEO, (x - 14, y - 13))
    elif nombre == "RÉCORDS":
        pantalla.blit(SPR_FRUTAS_HUD[IDX_DORADA], (x - 15, y - 15))
    elif nombre == "HISTORIA":
        pantalla.blit(SPR_PERGAMINO, (x - 13, y - 13))
    elif nombre == "CONFIGURACIÓN":
        pygame.draw.circle(pantalla, (190, 195, 225), (x, y), 11)
        for i in range(8):
            a = i * math.pi / 4 + t * 0.01
            pygame.draw.circle(pantalla, (190, 195, 225), (int(x + 13 * math.cos(a)), int(y + 13 * math.sin(a))), 3)
        pygame.draw.circle(pantalla, (40, 36, 80), (x, y), 5)
    else:  # SALIR
        pygame.draw.line(pantalla, (255, 110, 110), (x - 10, y - 10), (x + 10, y + 10), 4)
        pygame.draw.line(pantalla, (255, 110, 110), (x - 10, y + 10), (x + 10, y - 10), 4)


def dialogo_opciones(titulo, opciones, sel=0):
    """Pequeno dialogo modal. Devuelve el indice elegido o None (ESC)."""
    snap = pantalla.copy()
    t = 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return None
        for k in keys:
            if k in K_ARRIBA:
                sel = (sel - 1) % len(opciones)
                AUDIO.sfx("mover")
            elif k in K_ABAJO:
                sel = (sel + 1) % len(opciones)
                AUDIO.sfx("mover")
            elif k in K_OK:
                AUDIO.sfx("ok")
                return sel
            elif k in K_ATRAS:
                return None
        pantalla.blit(snap, (0, 0))
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((0, 0, 10, 170))
        pantalla.blit(velo, (0, 0))
        h = 90 + 56 * len(opciones)
        rect = pygame.Rect(ANCHO // 2 - 240, ALTO // 2 - h // 2, 480, h)
        pygame.draw.rect(pantalla, (22, 18, 52), rect, border_radius=20)
        pygame.draw.rect(pantalla, (255, 226, 90), rect, 3, border_radius=20)
        texto(pantalla, titulo, F_MED, (255, 255, 255), (rect.centerx, rect.y + 36), centro=True)
        for i, op in enumerate(opciones):
            r = pygame.Rect(rect.x + 30, rect.y + 70 + i * 56, 420, 46)
            if i == sel:
                pygame.draw.rect(pantalla, (255, 226, 90, 60), r, border_radius=23)
                pygame.draw.rect(pantalla, (255, 226, 90), r, 2, border_radius=23)
            texto(pantalla, op, F_MED, (255, 240, 150) if i == sel else (215, 215, 240), r.center, centro=True)
        presentar()


def pantalla_inicio(juego, nivel_inicial=1):
    """Menu principal. Devuelve ('nueva', nivel), ('continuar',) o None para salir."""
    fondo = crear_degradado_v(ANCHO, ALTO, (24, 18, 62), (78, 32, 96))
    flotantes = [[random.uniform(0, ANCHO), random.uniform(0, ALTO), random.uniform(-0.6, 0.6), random.uniform(0.4, 1.3),
                  random.randrange(len(FRUTAS)), random.uniform(0, math.tau)] for _ in range(22)]
    bichos = [[random.uniform(0, ANCHO), random.uniform(0, ALTO), random.uniform(-0.5, 0.5), random.uniform(0.3, 1.0),
               random.randrange(4), random.uniform(0, math.tau), random.randrange(10)] for _ in range(8)]
    opciones = ["JUGAR", "MUNDOS", "TIENDA", "MASCOTAS", "SKINS", "MISIONES", "LOGROS", "RÉCORDS", "HISTORIA", "CONFIGURACIÓN", "SALIR"]
    por_col = 6
    sel, t = 0, 0
    AUDIO.musica("menu")
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return None
        # Seleccion con raton: conserva todos los atajos de teclado existentes.
        for i in range(len(opciones)):
            col, row = divmod(i, por_col)
            hitbox = pygame.Rect(100 + col * 400, 334 + row * 70, 380, 58)
            if _RATON_POS is not None and hitbox.collidepoint(_RATON_POS):
                if sel != i:
                    sel = i
                    AUDIO.sfx("mover")
                if _RATON_CLIC:
                    keys.append(pygame.K_RETURN)
                break
        for k in keys:
            if k in K_ARRIBA:
                sel = (sel - 1) % len(opciones)
                AUDIO.sfx("mover")
            elif k in K_ABAJO:
                sel = (sel + 1) % len(opciones)
                AUDIO.sfx("mover")
            elif k in K_IZQ and sel >= por_col:
                sel -= por_col
                AUDIO.sfx("mover")
            elif k in K_DER and sel + por_col < len(opciones):
                sel += por_col
                AUDIO.sfx("mover")
            elif k == pygame.K_ESCAPE:
                return None
            elif k in K_OK:
                AUDIO.sfx("ok")
                nombre = opciones[sel]
                if nombre == "JUGAR":
                    if PROG.partida:
                        r = dialogo_opciones("¿Cómo quieres jugar?", [f"CONTINUAR (nivel {PROG.partida['nivel']})", "NUEVA PARTIDA", "VOLVER"])
                        if r == 0:
                            return ("continuar",)
                        if r == 1:
                            return ("nueva", nivel_inicial)
                    else:
                        return ("nueva", nivel_inicial)
                elif nombre == "MUNDOS":
                    elegido = pantalla_mundos()
                    if elegido is not None:
                        return ("nueva", elegido)
                elif nombre == "TIENDA":
                    pantalla_tienda("tienda")
                elif nombre == "MASCOTAS":
                    pantalla_tienda("mascotas")
                elif nombre == "SKINS":
                    pantalla_tienda("skins")
                elif nombre == "MISIONES":
                    pantalla_tareas()
                elif nombre == "LOGROS":
                    pantalla_logros()
                elif nombre == "RÉCORDS":
                    pantalla_records()
                elif nombre == "HISTORIA":
                    pantalla_historia()
                elif nombre == "CONFIGURACIÓN":
                    pantalla_config()
                else:
                    return None
                AUDIO.musica("menu")
        pantalla.blit(fondo, (0, 0))
        for f in flotantes:
            f[0] += f[2]
            f[1] += f[3]
            if f[1] > ALTO + 40:
                f[1] = -60
                f[0] = random.uniform(0, ANCHO)
            pantalla.blit(SPR_FRUTAS_GRANDES[f[4]], (int(f[0] + math.sin(t * 0.03 + f[5]) * 20), int(f[1])))
        for q in bichos:
            q[0] += q[2]
            q[1] += q[3]
            if q[1] > ALTO + 60:
                q[1] = -70
                q[0] = random.uniform(0, ANCHO)
            spr = pygame.transform.smoothscale(sprite_enemigo(q[6], q[4], (t // 8) % 4, "abajo"), (60, 60))
            spr.set_alpha(150)
            pantalla.blit(spr, (int(q[0] + math.sin(t * 0.03 + q[5]) * 20), int(q[1])))

        panel = pygame.Surface((ANCHO - 120, ALTO - 90), pygame.SRCALPHA)
        pygame.draw.rect(panel, (10, 8, 30, 178), panel.get_rect(), border_radius=28)
        pantalla.blit(panel, (60, 50))
        bob = math.sin(t * 0.05) * 5
        texto_borde(pantalla, "LABERINTO FRUTAL", fuente(74), (255, 226, 90), (120, 50, 10), (ANCHO // 2, 138 + bob), 4)
        hue = (t * 0.004) % 1
        r_, g_, b_ = colorsys.hsv_to_rgb(hue, 0.55, 1.0)
        texto_borde(pantalla, "D I M E N S I O N E S", F_MED, (int(r_ * 255), int(g_ * 255), int(b_ * 255)), (40, 10, 60), (ANCHO // 2, 192 + bob), 3)
        yb = 228 + math.sin(t * 0.09) * 5
        pantalla.blit(sprite_jugador("abajo", t, tam=88), (ANCHO // 2 - 44, int(yb)))
        for i in range(4):
            pantalla.blit(SPR_FRUTAS_GRANDES[(i * 2) % len(FRUTAS)], (ANCHO // 2 - 330 + i * 70, int(244 + math.sin(t * 0.07 + i) * 8)))
        for i in range(4):
            e_spr = pygame.transform.smoothscale(sprite_enemigo(i * 3 % 10, i, (t // 8 + i) % 4, "abajo"), (58, 58))
            pantalla.blit(e_spr, (ANCHO // 2 + 120 + i * 70, int(244 + math.sin(t * 0.07 + i + 1.5) * 8)))
        pantalla.blit(pygame.transform.smoothscale(sprite_cazador(t // 10, 1), (60, 70)), (ANCHO // 2 + 400, int(240 + math.sin(t * 0.05) * 6)))

        for i, nombre in enumerate(opciones):
            col, row = divmod(i, por_col)
            x = 100 + col * 400
            y = 334 + row * 70
            r = pygame.Rect(x, y, 380, 58)
            activo = i == sel
            # Resplandor exterior suave para que la opcion seleccionada destaque.
            if activo:
                glow = pygame.Surface((r.w + 20, r.h + 20), pygame.SRCALPHA)
                pygame.draw.rect(glow, (255, 205, 70, 35), glow.get_rect(), border_radius=24)
                pygame.draw.rect(glow, (255, 226, 90, 55), glow.get_rect().inflate(-8, -8), 3, border_radius=20)
                pantalla.blit(glow, (r.x - 10, r.y - 10))
            card = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(card, (255, 226, 90, 90) if activo else (40, 36, 90, 205), card.get_rect(), border_radius=18)
            pygame.draw.rect(card, (255, 240, 150) if activo else (96, 90, 160), card.get_rect(), 3 if activo else 2, border_radius=18)
            pantalla.blit(card, r)
            desp = int(math.sin(t * 0.2) * 4) if activo else 0
            icono_menu(nombre, r.x + 36 + desp, r.centery, t)
            texto(pantalla, nombre, F_MED if not activo else fuente(30), (255, 240, 150) if activo else (215, 215, 240),
                  (r.x + 70 + desp, r.y + 14 - (2 if activo else 0)))
        # tarjeta de estado a la derecha de la 2a columna (sobra una fila)
        info = pygame.Rect(500, 334 + 5 * 70, 380, 58)
        texto(pantalla, f"Mejor puntuación: {PROG.mejor_puntos}", F_PEQ, (255, 215, 90), (info.x + 10, info.y + 6), desp=1)
        texto(pantalla, f"Nivel más alto: {PROG.records['nivel_max']}   ·   Frutacoins: {PROG.monedas}", F_PEQ, (200, 210, 240), (info.x + 10, info.y + 32), desp=1)
        dibujar_saldo(100, 62)
        tk = lambda a: pygame.key.name(CONTROLES[a][0]).upper()
        texto(pantalla, f"Flechas/WASD: mover   ESPACIO: disparar   {tk('bomba')}: bomba   {tk('especial')}: especial   "
                        f"{tk('rayo')}: rayo   {tk('hielo')}: hielo   {tk('rafaga')}: ráfaga   C: cargado", fuente(14), (220, 220, 245),
              (ANCHO // 2, ALTO - 74), centro=True, desp=1)
        texto(pantalla, "Clic o flechas + ENTER para elegir   ·   ESC: salir   ·   P: pausa en partida", F_PEQ, (180, 180, 215),
              (ANCHO // 2, ALTO - 50), centro=True)
        dibujar_indicador_musica((70, ALTO - 36))
        presentar()


def pantalla_mundos():
    """Selector de mundos. Devuelve el nivel inicial elegido o None."""
    cols = 5
    CW, CH, GAP = 176, 196, 14
    x0 = (ANCHO - (cols * CW + (cols - 1) * GAP)) // 2
    y0 = 116
    fondo = crear_degradado_v(ANCHO, ALTO, (20, 16, 46), (66, 26, 70))
    total = 11 if PROG.dim_desbloqueada else 10
    sel, t = 0, 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return None
        for k in keys:
            if k in K_ATRAS:
                return None
            elif k in K_IZQ:
                sel = max(0, sel - 1)
            elif k in K_DER:
                sel = min(total - 1, sel + 1)
            elif k in K_ARRIBA:
                sel = max(0, sel - cols)
            elif k in K_ABAJO:
                sel = min(total - 1, sel + cols)
            elif k in K_OK:
                AUDIO.sfx("ok")
                return NIVEL_DIM_INI if sel == 10 else sel * NIVELES_POR_MUNDO + 1
        pantalla.blit(fondo, (0, 0))
        encabezado("MUNDOS", "Cada mundo tiene su propia regla de juego")
        for i in range(11):
            r, c = divmod(i, cols)
            if i == 10:
                rect = pygame.Rect((ANCHO - CW) // 2, y0 + 2 * (CH + GAP), CW, CH)
            else:
                rect = pygame.Rect(x0 + c * (CW + GAP), y0 + r * (CH + GAP), CW, CH)
            tema = TEMAS[i]
            bloqueado = i == 10 and not PROG.dim_desbloqueada
            card = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(card, (*mezcla(tema["piso"], 0.6), 235) if not bloqueado else (20, 18, 30, 220), card.get_rect(), border_radius=14)
            pygame.draw.rect(card, tema["acento"] if not bloqueado else (70, 70, 90), card.get_rect(), 2, border_radius=14)
            pantalla.blit(card, rect)
            if bloqueado:
                texto(pantalla, "???", F_GRANDE, (110, 110, 140), (rect.centerx, rect.y + 60), centro=True)
                texto(pantalla, "Dimensión oculta", F_PEQ, (150, 150, 180), (rect.centerx, rect.y + 110), centro=True, desp=1)
                texto(pantalla, "Completa el nivel 50", fuente(13), (130, 130, 160), (rect.centerx, rect.y + 140), centro=True, desp=1)
            else:
                spr = pygame.transform.smoothscale(sprite_enemigo(i, 0, (t // 8) % 4, "abajo"), (68, 68))
                pantalla.blit(spr, (rect.centerx - 34, rect.y + 8 + int(math.sin(t * 0.08 + i) * 2)))
                texto(pantalla, f"Mundo {i + 1}" if i < 10 else "DIMENSIÓN", F_PEQ, (220, 220, 245), (rect.centerx, rect.y + 82), centro=True, desp=1)
                nom = tema["nombre"]
                texto(pantalla, nom, fuente(20), (255, 255, 255), (rect.centerx, rect.y + 102), centro=True)
                texto(pantalla, MECANICAS[i].nombre, fuente(12), (140, 255, 200), (rect.centerx, rect.y + 128), centro=True, desp=1)
                jefe = MUNDOS[i]["jefe"]
                f_j = fuente(13) if F_PEQ.size(jefe)[0] > CW - 10 else F_PEQ
                texto(pantalla, jefe, f_j, (255, 190, 130), (rect.centerx, rect.y + 150), centro=True, desp=1)
                niv_ini = i * NIVELES_POR_MUNDO + 1
                if i < 10:
                    pr = f"Niveles {niv_ini}-{niv_ini + 4}"
                else:
                    pr = "Niveles 51-55"
                texto(pantalla, pr, fuente(13), (180, 200, 255), (rect.centerx, rect.y + 174), centro=True, desp=1)
                if i < 10 and (i in PROG.jefes):
                    pantalla.blit(ICONO_TROFEO, (rect.right - 30, rect.y + 6))
            if i == sel:
                pygame.draw.rect(pantalla, (255, 226, 90), rect.inflate(6, 6), 3, border_radius=17)
        pie("Flechas: elegir   ENTER: jugar este mundo   ESC: volver")
        presentar()


def dibujar_tarjeta(rect, borde, fondo_c, seleccionada=False):
    card = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(card, fondo_c, card.get_rect(), border_radius=14)
    pygame.draw.rect(card, borde, card.get_rect(), 2, border_radius=14)
    pantalla.blit(card, rect)
    if seleccionada:
        pygame.draw.rect(pantalla, (255, 226, 90), rect.inflate(6, 6), 3, border_radius=17)


def precio_texto(x, y, valor, moneda, puedo, centro=True):
    """Dibuja 'valor' con el icono de estrella o de Frutacoin."""
    txt = str(valor)
    w = F_PEQ.size(txt)[0] + 26
    xx = x - w // 2 if centro else x
    pantalla.blit(pygame.transform.scale(SPR_MONEDA, (24, 24)) if moneda else ICONO_ESTRELLA, (xx, y - 3))
    texto(pantalla, txt, F_PEQ, (255, 232, 110) if puedo else (255, 130, 130), (xx + 28, y), desp=1)


def pantalla_tienda(modo="tienda"):
    """Tienda: skins, mejoras, mascotas y efectos. (Se usa tambien para SKINS y MASCOTAS.)"""
    tabs = {"tienda": ["SKINS", "MEJORAS", "MASCOTAS", "EFECTOS"], "skins": ["SKINS", "EFECTOS"], "mascotas": ["MASCOTAS"]}[modo]
    titulo = {"tienda": "TIENDA", "skins": "SKINS Y EFECTOS", "mascotas": "MASCOTAS"}[modo]
    fondo = crear_degradado_v(ANCHO, ALTO, (22, 20, 56), (60, 30, 84))
    sel = {n: 0 for n in tabs}
    tab, scroll = 0, 0
    msg, msg_t, t = "", 0, 0
    cols_skin, CWs, CHs, GAPs, FIL_VIS = 5, 176, 120, 6, 5
    x0s = (ANCHO - (cols_skin * CWs + (cols_skin - 1) * GAPs)) // 2
    y0s = 152

    def aviso(texto_, nuevas=None):
        nonlocal msg, msg_t
        msg, msg_t = texto_, 220
        if nuevas:
            msg += f"   ¡Misión completada! +{sum(x['premio'] for x in nuevas)} estrellas"
            PROG.guardar()

    while True:
        reloj.tick(FPS)
        t += 1
        nombre = tabs[tab]
        n_items = {"SKINS": len(SKINS), "MEJORAS": len(MEJORAS), "MASCOTAS": len(MASCOTAS), "EFECTOS": len(EFECTOS) + 1}[nombre]
        ancho_grid = {"SKINS": cols_skin, "MEJORAS": 1, "MASCOTAS": 4, "EFECTOS": 3}[nombre]
        keys, salir = leer_teclas()
        if salir:
            PROG.guardar()
            return
        for k in keys:
            s = sel[nombre]
            if k in K_ATRAS:
                PROG.guardar()
                return
            elif k == pygame.K_TAB or k == pygame.K_e:
                tab = (tab + 1) % len(tabs)
                AUDIO.sfx("mover")
            elif k == pygame.K_q:
                tab = (tab - 1) % len(tabs)
                AUDIO.sfx("mover")
            elif k in K_IZQ:
                s = max(0, s - 1)
            elif k in K_DER:
                s = min(n_items - 1, s + 1)
            elif k in K_ARRIBA:
                s = max(0, s - ancho_grid)
            elif k in K_ABAJO:
                s = min(n_items - 1, s + ancho_grid)
            elif k == pygame.K_PAGEUP:
                s = max(0, s - ancho_grid * FIL_VIS)
            elif k == pygame.K_PAGEDOWN:
                s = min(n_items - 1, s + ancho_grid * FIL_VIS)
            elif k in K_OK:
                if nombre == "SKINS":
                    sk = SKINS[s]
                    if PROG.tiene(sk["id"]):
                        PROG.equipar(sk["id"])
                        aviso(f"Equipaste: {sk['nombre']}")
                        AUDIO.sfx("ok")
                    elif sk["jefe"] is not None:
                        aviso(f"Derrota al {MUNDOS[sk['jefe']]['jefe']} para conseguir este traje")
                    else:
                        ok, m_, nuevas = PROG.comprar(sk["id"])
                        AUDIO.sfx("vida" if ok else "error")
                        aviso(m_, nuevas)
                elif nombre == "MEJORAS":
                    ok, m_, nuevas = PROG.comprar_mejora(MEJORAS[s]["id"])
                    AUDIO.sfx("vida" if ok else "error")
                    aviso(m_, nuevas)
                elif nombre == "MASCOTAS":
                    mc = MASCOTAS[s]
                    if mc["id"] in PROG.mascotas:
                        PROG.equipar_mascota(None if PROG.mascota == mc["id"] else mc["id"])
                        aviso("Mascota guardada" if PROG.mascota is None else f"{mc['nombre']} te acompañará")
                        AUDIO.sfx("pet")
                    else:
                        ok, m_, nuevas = PROG.comprar_mascota(mc["id"])
                        AUDIO.sfx("vida" if ok else "error")
                        aviso(m_, nuevas)
                else:  # EFECTOS
                    if s == 0:
                        PROG.equipar_efecto(None)
                        aviso("Sin efecto")
                    else:
                        ef = EFECTOS[s - 1]
                        if ef["id"] in PROG.efectos:
                            PROG.equipar_efecto(ef["id"])
                            aviso(f"Equipaste: {ef['nombre']}")
                            AUDIO.sfx("ok")
                        else:
                            ok, m_, nuevas = PROG.comprar_efecto(ef["id"])
                            AUDIO.sfx("vida" if ok else "error")
                            aviso(m_, nuevas)
            sel[nombre] = s
        pantalla.blit(fondo, (0, 0))
        encabezado(titulo)
        # pestanas
        tx = 40
        for i, nm in enumerate(tabs):
            r = pygame.Rect(tx, 100, 170, 36)
            activo = i == tab
            pygame.draw.rect(pantalla, (255, 226, 90, 255) if activo else (36, 34, 80), r, border_radius=18)
            pygame.draw.rect(pantalla, (255, 226, 90) if activo else (96, 90, 160), r, 2, border_radius=18)
            texto(pantalla, nm, F_PEQ, (40, 20, 0) if activo else (215, 215, 240), r.center, centro=True, sombra=None)
            tx += 180
        if len(tabs) > 1:
            texto(pantalla, "TAB / Q / E: cambiar de pestaña", fuente(13), (170, 175, 210), (tx + 10, 110), desp=1)
        s = sel[nombre]
        if nombre == "SKINS":
            total_filas = (len(SKINS) + cols_skin - 1) // cols_skin
            fila_sel = s // cols_skin
            if fila_sel < scroll:
                scroll = fila_sel
            elif fila_sel >= scroll + FIL_VIS:
                scroll = fila_sel - FIL_VIS + 1
            texto(pantalla, f"Colección: {len(PROG.skins)}/{len(SKINS)}   ·   las skins con moneda cuestan Frutacoins", F_PEQ, (220, 220, 245), (40, 142 - 4), desp=1)
            for i, sk in enumerate(SKINS):
                r, c = divmod(i, cols_skin)
                if r < scroll or r >= scroll + FIL_VIS:
                    continue
                rect = pygame.Rect(x0s + c * (CWs + GAPs), y0s + 12 + (r - scroll) * (CHs + GAPs), CWs, CHs)
                tengo, puesta = PROG.tiene(sk["id"]), PROG.equipada == sk["id"]
                fondo_c = (30, 60, 46, 230) if puesta else ((28, 34, 70, 230) if tengo else (22, 20, 40, 220))
                borde = (110, 240, 140) if puesta else ((120, 160, 255) if tengo else (70, 70, 96))
                dibujar_tarjeta(rect, borde, fondo_c, i == s)
                spr = sprite_jugador("abajo", t, sk["id"], 56)
                if not tengo and sk["jefe"] is not None:
                    spr = spr.copy()
                    spr.fill((30, 30, 45), special_flags=pygame.BLEND_RGB_MULT)
                pantalla.blit(spr, (rect.centerx - 28, rect.y + 6 + int(math.sin(t * 0.08 + i) * 2 if i == s else 0)))
                texto(pantalla, sk["nombre"], F_PEQ, (255, 255, 255) if tengo else (200, 200, 225), (rect.centerx, rect.y + 72), centro=True, desp=1)
                if puesta:
                    texto(pantalla, "EQUIPADA", F_PEQ, (130, 245, 160), (rect.centerx, rect.y + 96), centro=True, desp=1)
                elif tengo:
                    texto(pantalla, "Tuya", F_PEQ, (150, 180, 255), (rect.centerx, rect.y + 96), centro=True, desp=1)
                elif sk["jefe"] is not None:
                    txt_j = f"Vence al {MUNDOS[sk['jefe']]['jefe']}"
                    f_j = fuente(13) if F_PEQ.size(txt_j)[0] <= CWs - 10 else fuente(11)
                    texto(pantalla, txt_j, f_j, (255, 170, 130), (rect.centerx, rect.y + 96), centro=True, desp=1)
                elif sk["mon"]:
                    precio_texto(rect.centerx, rect.y + 94, sk["mon"], True, PROG.monedas >= sk["mon"])
                else:
                    precio_texto(rect.centerx, rect.y + 94, sk["precio"], False, PROG.estrellas >= sk["precio"])
            if total_filas > FIL_VIS:
                alto_pista = FIL_VIS * (CHs + GAPs) - GAPs
                bx = x0s + cols_skin * (CWs + GAPs) - GAPs + 14
                pygame.draw.rect(pantalla, (40, 40, 72), (bx, y0s + 12, 8, alto_pista), border_radius=4)
                alto_thumb = max(30, int(alto_pista * FIL_VIS / total_filas))
                ty = y0s + 12 + int((alto_pista - alto_thumb) * scroll / (total_filas - FIL_VIS))
                pygame.draw.rect(pantalla, (255, 226, 90), (bx, ty, 8, alto_thumb), border_radius=4)
        elif nombre == "MEJORAS":
            texto(pantalla, "Mejoras permanentes: se compran con Frutacoins", F_PEQ, (220, 220, 245), (40, 142), desp=1)
            for i, mj in enumerate(MEJORAS):
                rect = pygame.Rect(80, 180 + i * 110, ANCHO - 160, 98)
                lvl, maxl = PROG.nivel_mejora(mj["id"]), len(mj["precios"])
                dibujar_tarjeta(rect, (120, 160, 255) if lvl else (70, 70, 96), (28, 34, 70, 230), i == s)
                texto(pantalla, mj["nombre"], F_MED, (255, 255, 255), (rect.x + 24, rect.y + 12))
                texto(pantalla, mj["texto"], F_PEQ, (200, 210, 240), (rect.x + 24, rect.y + 50), desp=1)
                for k in range(maxl):
                    pr = pygame.Rect(rect.x + 24 + k * 34, rect.y + 74, 28, 12)
                    pygame.draw.rect(pantalla, (255, 208, 60) if k < lvl else (50, 50, 80), pr, border_radius=4)
                precio = PROG.precio_mejora(mj["id"])
                if precio is None:
                    texto(pantalla, "NIVEL MÁXIMO", F_MED, (130, 245, 160), (rect.right - 220, rect.y + 34))
                else:
                    texto(pantalla, f"Nivel {lvl} → {lvl + 1}", F_PEQ, (200, 210, 240), (rect.right - 250, rect.y + 20), desp=1)
                    precio_texto(rect.right - 250, rect.y + 52, precio, True, PROG.monedas >= precio, centro=False)
        elif nombre == "MASCOTAS":
            texto(pantalla, "Las mascotas te acompañan y te dan una ventaja. Solo una a la vez.", F_PEQ, (220, 220, 245), (40, 142), desp=1)
            for i, mc in enumerate(MASCOTAS):
                rect = pygame.Rect(40 + i * 232, 190, 220, 400)
                tengo, puesta = mc["id"] in PROG.mascotas, PROG.mascota == mc["id"]
                dibujar_tarjeta(rect, (110, 240, 140) if puesta else ((120, 160, 255) if tengo else (70, 70, 96)),
                                (30, 60, 46, 230) if puesta else (28, 34, 70, 230), i == s)
                sp = sprite_mascota(mc["id"], t // 8, 110)
                pantalla.blit(sp, (rect.centerx - 55, rect.y + 30 + int(math.sin(t * 0.1 + i) * 5)))
                texto(pantalla, mc["nombre"], F_GRANDE, (255, 255, 255), (rect.centerx, rect.y + 190), centro=True)
                texto_ajustado(pantalla, mc["texto"], F_PEQ, (200, 210, 240), rect.x + 14, rect.y + 226, rect.w - 28, centro=True)
                if puesta:
                    texto(pantalla, "ACOMPAÑÁNDOTE", F_PEQ, (130, 245, 160), (rect.centerx, rect.y + 340), centro=True, desp=1)
                elif tengo:
                    texto(pantalla, "TUYA  (ENTER: equipar)", F_PEQ, (150, 180, 255), (rect.centerx, rect.y + 340), centro=True, desp=1)
                else:
                    precio_texto(rect.centerx, rect.y + 340, mc["precio"], True, PROG.monedas >= mc["precio"])
        else:  # EFECTOS
            texto(pantalla, "Efectos visuales para tu personaje", F_PEQ, (220, 220, 245), (40, 142), desp=1)
            for i in range(len(EFECTOS) + 1):
                r, c = divmod(i, 3)
                rect = pygame.Rect(40 + c * 316, 180 + r * 150, 304, 138)
                if i == 0:
                    puesta = PROG.efecto is None
                    dibujar_tarjeta(rect, (110, 240, 140) if puesta else (120, 160, 255), (28, 34, 70, 230), i == s)
                    texto(pantalla, "SIN EFECTO", F_MED, (255, 255, 255), (rect.centerx, rect.y + 46), centro=True)
                    texto(pantalla, "EQUIPADO" if puesta else "ENTER: quitar efecto", F_PEQ, (130, 245, 160) if puesta else (170, 180, 210), (rect.centerx, rect.y + 90), centro=True, desp=1)
                    continue
                ef = EFECTOS[i - 1]
                tengo, puesta = ef["id"] in PROG.efectos, PROG.efecto == ef["id"]
                dibujar_tarjeta(rect, (110, 240, 140) if puesta else ((120, 160, 255) if tengo else (70, 70, 96)),
                                (30, 60, 46, 230) if puesta else (28, 34, 70, 230), i == s)
                for k in range(6):  # vista previa animada
                    a = t * 0.07 + k * math.pi / 3
                    col = ef["color"]
                    if ef["tipo"] == "arcoiris":
                        rr, gg, bb = colorsys.hsv_to_rgb((k / 6 + t * 0.01) % 1, 0.8, 1.0)
                        col = (int(rr * 255), int(gg * 255), int(bb * 255))
                    pygame.draw.circle(pantalla, col, (int(rect.x + 50 + math.cos(a) * 26), int(rect.y + 60 + math.sin(a) * 26)), 5)
                pantalla.blit(sprite_jugador("abajo", t, tam=40), (rect.x + 30, rect.y + 40))
                texto(pantalla, ef["nombre"], F_PEQ, (255, 255, 255), (rect.x + 100, rect.y + 24), desp=1)
                if puesta:
                    texto(pantalla, "EQUIPADO", F_PEQ, (130, 245, 160), (rect.x + 100, rect.y + 70), desp=1)
                elif tengo:
                    texto(pantalla, "Tuyo (ENTER: equipar)", fuente(14), (150, 180, 255), (rect.x + 100, rect.y + 70), desp=1)
                else:
                    precio_texto(rect.x + 100, rect.y + 70, ef["precio"], True, PROG.monedas >= ef["precio"], centro=False)
        if msg_t > 0:
            msg_t -= 1
            texto(pantalla, msg, F_MED, (255, 255, 255), (ANCHO // 2, ALTO - 62), centro=True)
        pie("Flechas / rueda: elegir   ENTER: comprar / equipar   ESC: volver")
        presentar()


def pantalla_tareas():
    """MISIONES: una activa por cadena; al completarla aparece la siguiente."""
    fondo = crear_degradado_v(ANCHO, ALTO, (18, 26, 58), (52, 36, 86))
    f13 = fuente(13)
    pag = 0
    while True:
        reloj.tick(FPS)
        keys, salir = leer_teclas()
        if salir:
            return
        activas = PROG.tareas_activas()
        por_pag = 20
        paginas = (len(activas) + por_pag - 1) // por_pag
        for k in keys:
            if k in K_ATRAS or k == pygame.K_RETURN:
                return
            if k in K_DER or k in K_ABAJO:
                pag = min(paginas - 1, pag + 1)
            if k in K_IZQ or k in K_ARRIBA:
                pag = max(0, pag - 1)
        pantalla.blit(fondo, (0, 0))
        encabezado("MISIONES", "Al completar una misión aparece la siguiente, más difícil. Premio: estrellas y Frutacoins")
        vis = activas[pag * por_pag:(pag + 1) * por_pag]
        filas = (len(vis) + 1) // 2
        paso_y = 60
        for i, (tarea, completa) in enumerate(vis):
            col, fila = divmod(i, filas)
            x = 24 + col * 486
            y = 110 + fila * paso_y
            card = pygame.Surface((466, 54), pygame.SRCALPHA)
            pygame.draw.rect(card, (36, 56, 48, 235) if completa else (24, 22, 46, 225), card.get_rect(), border_radius=12)
            pygame.draw.rect(card, (110, 240, 140) if completa else (76, 76, 108), card.get_rect(), 2, border_radius=12)
            pantalla.blit(card, (x, y))
            pantalla.blit(ICONO_TROFEO if completa else ICONO_TROFEO_GRIS, (x + 10, y + 13))
            texto(pantalla, tarea["texto"], F_PEQ, (255, 255, 255) if completa else (215, 215, 240), (x + 46, y + 6), desp=1)
            actual, meta = PROG.avance(tarea)
            pygame.draw.rect(pantalla, (14, 14, 30), (x + 46, y + 32, 230, 10), border_radius=5)
            if actual > 0:
                pygame.draw.rect(pantalla, (110, 240, 140) if completa else (255, 208, 60),
                                 (x + 46, y + 32, max(6, int(230 * actual / meta)), 10), border_radius=5)
            texto(pantalla, f"{actual}/{meta}", fuente(15), (200, 205, 235), (x + 284, y + 28), desp=1)
            etiqueta = "¡COMPLETA!" if completa else f"Paso {tarea['paso']}/{tarea['pasos']}"
            texto(pantalla, etiqueta, f13, (130, 245, 160) if completa else (170, 190, 255), (x + 456 - f13.size(etiqueta)[0], y + 36), desp=1)
            if not completa:
                r = texto(pantalla, f"+{tarea['premio']}", fuente(17), (255, 232, 110), (x + 330, y + 8), desp=1)
                pantalla.blit(ICONO_ESTRELLA, (r.right + 2, y + 6))
                r2 = texto(pantalla, f"+{PROG.monedas_tarea(tarea)}", fuente(17), (255, 200, 80), (r.right + 36, y + 8), desp=1)
                pantalla.blit(pygame.transform.scale(SPR_MONEDA, (20, 20)), (r2.right + 2, y + 8))
        if paginas > 1:
            texto(pantalla, f"Página {pag + 1}/{paginas}  (← →)", F_PEQ, (200, 200, 230), (ANCHO // 2, ALTO - 52), centro=True)
        pie("En cada nivel también hay una misión rápida (mira la barra de arriba)   ·   ESC: volver")
        presentar()


def pantalla_logros():
    fondo = crear_degradado_v(ANCHO, ALTO, (24, 20, 60), (70, 34, 80))
    sel, t = 0, 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return
        for k in keys:
            if k in K_ATRAS or k in K_OK:
                return
            if k in K_ARRIBA:
                sel = max(0, sel - 1)
            if k in K_ABAJO:
                sel = min(len(LOGROS) - 1, sel + 1)
        pantalla.blit(fondo, (0, 0))
        encabezado("LOGROS Y TROFEOS", f"{len(PROG.logros)}/{len(LOGROS)} desbloqueados")
        ini = max(0, min(sel - 5, len(LOGROS) - 11))
        for i, lg in enumerate(LOGROS[ini:ini + 11]):
            idx = ini + i
            tengo = lg["id"] in PROG.logros
            rect = pygame.Rect(60, 108 + i * 62, ANCHO - 120, 56)
            dibujar_tarjeta(rect, (255, 208, 60) if tengo else (70, 70, 96), (50, 46, 30, 235) if tengo else (22, 20, 40, 225), idx == sel)
            pantalla.blit(ICONO_TROFEO if tengo else ICONO_TROFEO_GRIS, (rect.x + 14, rect.y + 14))
            texto(pantalla, lg["nombre"], F_MED, (255, 240, 170) if tengo else (170, 170, 200), (rect.x + 58, rect.y + 4))
            texto(pantalla, lg["texto"], F_PEQ, (220, 220, 240) if tengo else (140, 140, 170), (rect.x + 58, rect.y + 32), desp=1)
            act = min(PROG.stats.get(lg["stat"], 0), lg["meta"])
            if not tengo and lg["meta"] > 1:
                texto(pantalla, f"{act}/{lg['meta']}", F_PEQ, (180, 190, 230), (rect.right - 230, rect.y + 18), desp=1)
            r = texto(pantalla, f"+{lg['premio']}", F_PEQ, (255, 200, 80), (rect.right - 100, rect.y + 18), desp=1)
            pantalla.blit(pygame.transform.scale(SPR_MONEDA, (22, 22)), (r.right + 4, rect.y + 16))
            if tengo:
                texto(pantalla, "¡HECHO!", F_PEQ, (130, 245, 160), (rect.right - 180, rect.y + 18), desp=1)
        pie("Flechas: recorrer   ESC: volver")
        presentar()


def pantalla_records():
    fondo = crear_degradado_v(ANCHO, ALTO, (18, 30, 60), (56, 30, 84))
    t = 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return
        if any(k in K_ATRAS or k in K_OK for k in keys):
            return
        pantalla.blit(fondo, (0, 0))
        encabezado("RÉCORDS Y ESTADÍSTICAS")
        rc, st = PROG.records, PROG.stats
        tr = rc["tiempo_rapido"]
        filas = [
            ("Mayor puntuación", f"{PROG.mejor_puntos:,}"), ("Mayor combo", f"x{rc['mejor_combo']}"),
            ("Más frutas en una partida", str(rc["max_frutas"])), ("Más enemigos en una partida", str(rc["max_enemigos"])),
            ("Nivel completado más rápido", f"{tr // 60}:{tr % 60:02d}" if tr else "—"), ("Nivel más alto", str(rc["nivel_max"])),
            ("Jefes derrotados", f"{len(PROG.jefes)}/11"), ("Frutacoins obtenidas", f"{rc['monedas_total']:,}"),
        ]
        for i, (a, b) in enumerate(filas):
            rect = pygame.Rect(60, 112 + i * 50, 520, 44)
            dibujar_tarjeta(rect, (96, 90, 160), (24, 22, 56, 225))
            texto(pantalla, a, F_PEQ, (200, 205, 235), (rect.x + 16, rect.y + 11), desp=1)
            texto(pantalla, b, F_MED, (255, 232, 120), (rect.right - 16 - F_MED.size(b)[0], rect.y + 6))
        texto(pantalla, "TOTALES", F_MED, (255, 255, 255), (620, 112))
        tot = [("Frutas recogidas", st.get("frutas", 0)), ("Enemigos derrotados", st.get("enemigos", 0)),
               ("Secretos hallados", st.get("secretos", 0)), ("Habitaciones secretas", st.get("habitaciones", 0)),
               ("Niveles completados", st.get("niveles", 0)), ("Veces sin daño", st.get("sin_dano", 0)),
               ("Eventos superados", st.get("eventos", 0)), ("Modo Furia usado", st.get("furias", 0)),
               ("El Cazador derrotado", st.get("cazador_derrotado", 0))]
        for i, (a, b) in enumerate(tot):
            texto(pantalla, a, F_PEQ, (200, 205, 235), (620, 154 + i * 30), desp=1)
            texto(pantalla, f"{b:,}", F_PEQ, (255, 232, 120), (880 - F_PEQ.size(f"{b:,}")[0], 154 + i * 30), desp=1)
        texto(pantalla, "COLECCIÓN DE FRUTAS", F_MED, (255, 255, 255), (60, 524))
        for i, fr in enumerate(FRUTAS):
            x = 60 + i * 104
            rect = pygame.Rect(x, 566, 96, 120)
            tengo = fr[0] in PROG.frutas_desc
            dibujar_tarjeta(rect, fr[3] if tengo else (70, 70, 96), (24, 22, 56, 225))
            spr = SPR_FRUTAS_GRANDES[i]
            if not tengo:
                spr = spr.copy()
                spr.fill((20, 20, 30), special_flags=pygame.BLEND_RGB_MULT)
            pantalla.blit(spr, (rect.centerx - 30, rect.y + 10 + int(math.sin(t * 0.08 + i) * 2 if tengo else 0)))
            texto(pantalla, fr[0].capitalize() if tengo else "???", fuente(14), (255, 255, 255) if tengo else (120, 120, 150), (rect.centerx, rect.y + 84), centro=True, desp=1)
            texto(pantalla, f"{st.get('fruta_' + fr[0], 0)}" if tengo else "", fuente(13), (255, 232, 120), (rect.centerx, rect.y + 102), centro=True, desp=1)
        pie("ESC: volver")
        presentar()


PREGUNTAS_HISTORIA = [
    ("¿Quién creó el laberinto?", ("intro",)), ("¿Por qué existen las frutas?", ("mundo_1",)),
    ("¿Por qué los enemigos protegen los mundos?", ("mundo_0", "secreto_7")),
    ("¿Quién es El Cazador?", ("cazador",)), ("¿Qué existe después del nivel 50?", ("fin_50",)),
]


def pantalla_historia():
    fondo = crear_degradado_v(ANCHO, ALTO, (30, 20, 50), (70, 40, 60))
    AUDIO.musica("historia")
    sel, t = 0, 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return
        for k in keys:
            if k in K_ATRAS:
                return
            if k in K_ARRIBA:
                sel = max(0, sel - 1)
            if k in K_ABAJO:
                sel = min(len(HISTORIA) - 1, sel + 1)
            if k in K_OK and HISTORIA[sel][0] == "intro" and "intro" in PROG.fragmentos:
                cinematica("intro")
                AUDIO.musica("historia")
        pantalla.blit(fondo, (0, 0))
        encabezado("HISTORIA", f"Fragmentos descubiertos: {len(PROG.fragmentos)}/{len(HISTORIA)}")
        ini = max(0, min(sel - 7, len(HISTORIA) - 15))
        for i, h in enumerate(HISTORIA[ini:ini + 15]):
            idx = ini + i
            tengo = h[0] in PROG.fragmentos
            rect = pygame.Rect(40, 110 + i * 40, 330, 36)
            dibujar_tarjeta(rect, (255, 208, 60) if tengo else (70, 70, 96), (40, 34, 30, 235) if tengo else (22, 20, 40, 225), idx == sel)
            texto(pantalla, h[1] if tengo else "???  (sin descubrir)", F_PEQ, (255, 240, 190) if tengo else (130, 130, 160), (rect.x + 14, rect.y + 8), desp=1)
        # lectura
        h = HISTORIA[sel]
        pan = pygame.Rect(400, 110, ANCHO - 440, 330)
        dibujar_tarjeta(pan, (255, 208, 60), (22, 18, 40, 235))
        pantalla.blit(SPR_PERGAMINO, (pan.x + 16, pan.y + 14))
        if h[0] in PROG.fragmentos:
            texto(pantalla, h[1], F_MED, (255, 232, 130), (pan.x + 60, pan.y + 14))
            texto_ajustado(pantalla, h[2], fuente(22), (235, 235, 250), pan.x + 24, pan.y + 70, pan.w - 48, 8)
            if h[0] == "intro":
                texto(pantalla, "ENTER: ver la introducción otra vez", F_PEQ, (150, 180, 255), (pan.x + 24, pan.bottom - 34), desp=1)
        else:
            texto(pantalla, "Fragmento oculto", F_MED, (150, 150, 180), (pan.x + 60, pan.y + 14))
            texto_ajustado(pantalla, "Explora los mundos, derrota jefes y busca habitaciones secretas para descubrirlo.", fuente(20), (150, 150, 180), pan.x + 24, pan.y + 70, pan.w - 48, 8)
        # preguntas
        texto(pantalla, "LOS GRANDES MISTERIOS", F_MED, (255, 255, 255), (400, 452))
        for i, (q, req) in enumerate(PREGUNTAS_HISTORIA):
            ok = any(r in PROG.fragmentos for r in req)
            texto(pantalla, ("✔ " if ok else "? ") + q, F_PEQ, (140, 255, 170) if ok else (170, 170, 200), (400, 496 + i * 34), desp=1)
        pie("Flechas: elegir fragmento   ESC: volver")
        presentar()


def pantalla_controles():
    fondo = crear_degradado_v(ANCHO, ALTO, (24, 22, 56), (56, 30, 80))
    acciones = list(CONTROLES_DEF)
    sel, esperando, msg = 0, False, ""
    while True:
        reloj.tick(FPS)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return
            if ev.type == pygame.KEYDOWN:
                if esperando:
                    esperando = False
                    if ev.key == pygame.K_ESCAPE:
                        msg = "Cancelado"
                        continue
                    acc = acciones[sel]
                    for otra in acciones:  # una tecla no puede hacer dos cosas
                        if otra != acc and ev.key in CONTROLES[otra]:
                            CONTROLES[otra].remove(ev.key)
                            if not CONTROLES[otra]:
                                CONTROLES[otra] = list(CONTROLES_DEF[otra])
                    CONTROLES[acc] = [ev.key] + [k for k in CONTROLES_DEF[acc][1:] if k != ev.key]
                    if acc in ("arriba", "abajo", "izquierda", "derecha"):
                        CONTROLES[acc] = [ev.key] + [k for k in CONTROLES_DEF[acc][1:] if k != ev.key]
                    msg = f"{NOMBRES_CONTROL[acc]}: {pygame.key.name(ev.key).upper()}"
                    AUDIO.sfx("ok")
                    continue
                if ev.key in K_ATRAS:
                    PROG.guardar()
                    return
                if ev.key in K_ARRIBA:
                    sel = (sel - 1) % len(acciones)
                elif ev.key in K_ABAJO:
                    sel = (sel + 1) % len(acciones)
                elif ev.key in K_OK:
                    esperando = True
                elif ev.key == pygame.K_r:
                    for a in acciones:
                        CONTROLES[a] = list(CONTROLES_DEF[a])
                    msg = "Controles restaurados"
        pantalla.blit(fondo, (0, 0))
        encabezado("CONTROLES", "Elige una acción y pulsa ENTER para asignarle otra tecla")
        for i, a in enumerate(acciones):
            rect = pygame.Rect(150, 112 + i * 50, ANCHO - 300, 44)
            dibujar_tarjeta(rect, (96, 90, 160), (24, 22, 56, 225), i == sel)
            texto(pantalla, NOMBRES_CONTROL[a], F_MED, (255, 255, 255), (rect.x + 20, rect.y + 6))
            teclas_txt = " / ".join(pygame.key.name(k).upper() for k in CONTROLES[a])
            if esperando and i == sel:
                teclas_txt = "Pulsa una tecla..."
            texto(pantalla, teclas_txt, F_MED, (255, 232, 120), (rect.right - 20 - F_MED.size(teclas_txt)[0], rect.y + 6))
        if msg:
            texto(pantalla, msg, F_PEQ, (140, 255, 170), (ANCHO // 2, ALTO - 62), centro=True)
        pie("ENTER: cambiar tecla   R: restaurar por defecto   ESC: volver")
        presentar()


def pantalla_config():
    fondo = crear_degradado_v(ANCHO, ALTO, (22, 22, 54), (50, 34, 80))
    sel, t = 0, 0
    opciones = ["Volumen de la música", "Volumen de los efectos", "Música", "Efectos de sonido", "Pantalla completa",
                "Resolución de la ventana", "Partículas", "Efectos visuales", "Controles", "Borrar progreso", "Volver"]
    confirmar_borrar = 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            PROG.guardar()
            return
        for k in keys:
            n = opciones[sel]
            if k in K_ATRAS:
                PROG.guardar()
                return
            if k in K_ARRIBA:
                sel = (sel - 1) % len(opciones)
                confirmar_borrar = 0
            elif k in K_ABAJO:
                sel = (sel + 1) % len(opciones)
                confirmar_borrar = 0
            elif k in K_IZQ or k in K_DER or k in K_OK:
                d = -1 if k in K_IZQ else 1
                if n == "Volumen de la música" and k not in K_OK:
                    AUDIO.set_vol_musica(CONFIG["vol_musica"] + 0.1 * d)
                    AUDIO.sfx("mover")
                elif n == "Volumen de los efectos" and k not in K_OK:
                    CONFIG["vol_efectos"] = max(0.0, min(1.0, CONFIG["vol_efectos"] + 0.1 * d))
                    AUDIO.sfx("moneda")
                elif n == "Música":
                    AUDIO.alternar()
                elif n == "Efectos de sonido":
                    CONFIG["efectos_on"] = not CONFIG["efectos_on"]
                    AUDIO.sfx("ok")
                elif n == "Pantalla completa":
                    CONFIG["pantalla_completa"] = not CONFIG["pantalla_completa"]
                    aplicar_ventana()
                elif n == "Resolución de la ventana":
                    CONFIG["resolucion"] = (CONFIG["resolucion"] + (d if k not in K_OK else 1)) % len(RESOLUCIONES)
                    if not CONFIG["pantalla_completa"]:
                        aplicar_ventana()
                elif n == "Partículas":
                    CONFIG["particulas"] = not CONFIG["particulas"]
                elif n == "Efectos visuales":
                    CONFIG["efectos"] = not CONFIG["efectos"]
                elif n == "Controles" and k in K_OK:
                    pantalla_controles()
                elif n == "Borrar progreso" and k in K_OK:
                    confirmar_borrar += 1
                    if confirmar_borrar >= 2:
                        for attr, val in (("estrellas", 0), ("monedas", 0), ("trofeos", []), ("skins", ["verde"]), ("equipada", "verde"),
                                          ("stats", {}), ("jefes", []), ("mejor_puntos", 0), ("mejoras", {}), ("mascotas", []),
                                          ("mascota", None), ("efectos", []), ("efecto", None), ("logros", []), ("frutas_desc", []),
                                          ("fragmentos", []), ("dim_desbloqueada", False), ("dim_completa", False), ("partida", None)):
                            setattr(PROG, attr, val)
                        PROG.records = dict(PROG.RECORDS_DEF)
                        PROG.guardar()
                        confirmar_borrar = 0
                        AUDIO.sfx("gameover")
                elif n == "Volver" and k in K_OK:
                    PROG.guardar()
                    return
        pantalla.blit(fondo, (0, 0))
        encabezado("CONFIGURACIÓN")
        for i, n in enumerate(opciones):
            rect = pygame.Rect(150, 100 + i * 56, ANCHO - 300, 50)
            dibujar_tarjeta(rect, (96, 90, 160), (24, 22, 56, 225), i == sel)
            texto(pantalla, n, F_MED, (255, 255, 255), (rect.x + 20, rect.y + 9))
            vx = rect.right - 330
            if n in ("Volumen de la música", "Volumen de los efectos"):
                v = CONFIG["vol_musica" if "música" in n else "vol_efectos"]
                pygame.draw.rect(pantalla, (14, 14, 30), (vx, rect.y + 18, 260, 14), border_radius=7)
                pygame.draw.rect(pantalla, (255, 208, 60), (vx, rect.y + 18, int(260 * v), 14), border_radius=7)
                texto(pantalla, f"{int(v * 100)}%", F_PEQ, (255, 232, 120), (vx + 270, rect.y + 14), desp=1)
            else:
                val = {"Música": CONFIG["musica_on"], "Efectos de sonido": CONFIG["efectos_on"], "Pantalla completa": CONFIG["pantalla_completa"],
                       "Partículas": CONFIG["particulas"], "Efectos visuales": CONFIG["efectos"]}.get(n)
                if val is not None:
                    texto(pantalla, "SÍ" if val else "NO", F_MED, (130, 245, 160) if val else (255, 130, 130), (vx + 200, rect.y + 9))
                elif n == "Resolución de la ventana":
                    texto(pantalla, RESOLUCIONES[CONFIG["resolucion"]][0], F_MED, (255, 232, 120), (vx + 200, rect.y + 9))
                elif n == "Controles":
                    texto(pantalla, "ENTER ▶", F_MED, (255, 232, 120), (vx + 160, rect.y + 9))
                elif n == "Borrar progreso":
                    texto(pantalla, "¡pulsa ENTER 2 veces!" if confirmar_borrar else "ENTER", F_PEQ, (255, 130, 130), (vx + 120, rect.y + 16))
        pie("Flechas: elegir y cambiar   ESC: volver   (los cambios se guardan solos)")
        presentar()


def cinematica(clave):
    """Escenas sencillas con texto que se escribe solo. ENTER avanza, ESC salta."""
    paginas = CINEMATICAS[clave]
    AUDIO.musica("historia")
    fondo = crear_degradado_v(ANCHO, ALTO, (8, 4, 24), (60, 20, 60) if clave != "fin_dim" else (80, 50, 20))
    estrellas = [[random.uniform(0, ANCHO), random.uniform(0, ALTO), random.uniform(0.2, 1.2)] for _ in range(80)]
    for i, txt in enumerate(paginas):
        n, t = 0.0, 0
        while True:
            reloj.tick(FPS)
            t += 1
            n = min(len(txt), n + 0.9)
            keys, salir = leer_teclas()
            if salir:
                return
            fin = False
            for k in keys:
                if k == pygame.K_ESCAPE:
                    return
                if k in K_OK:
                    if n < len(txt):
                        n = len(txt)
                    else:
                        fin = True
            if fin:
                break
            pantalla.blit(fondo, (0, 0))
            for e in estrellas:
                e[1] = (e[1] + e[2]) % ALTO
                pygame.draw.circle(pantalla, (200, 200, 255), (int(e[0]), int(e[1])), 1 if e[2] < 0.7 else 2)
            cx, cy = ANCHO // 2, 270
            if clave == "fin_50" and i >= 1 or clave == "fin_dim":
                r = 70 + int(8 * math.sin(t * 0.12))
                g = crear_brillo_cache(110, (255, 70, 110) if clave == "fin_50" else (255, 215, 90))
                pantalla.blit(g, (cx - 110, cy - 110))
                pygame.draw.circle(pantalla, (255, 90, 130) if clave == "fin_50" else (255, 220, 100), (cx, cy), r // 2)
            else:
                pantalla.blit(pygame.transform.smoothscale(sprite_jugador("abajo", t, tam=60), (150, 150)), (cx - 75, cy - 75 + int(math.sin(t * 0.08) * 6)))
            if clave == "intro" and i == 2:
                pantalla.blit(pygame.transform.smoothscale(sprite_cazador(t // 10, 1), (110, 134)), (cx + 160, cy - 60))
            panel = pygame.Surface((ANCHO - 160, 190), pygame.SRCALPHA)
            pygame.draw.rect(panel, (0, 0, 10, 190), panel.get_rect(), border_radius=20)
            pantalla.blit(panel, (80, 500))
            texto_ajustado(pantalla, txt[:int(n)], fuente(26), (255, 255, 255), 110, 530, ANCHO - 220, 10)
            texto(pantalla, f"{i + 1}/{len(paginas)}   ENTER: seguir   ESC: saltar", F_PEQ, (170, 170, 210), (ANCHO // 2, 710), centro=True)
            presentar()


def pantalla_fragmento(id_):
    """Ventana que muestra un fragmento de historia recien encontrado."""
    h = HISTORIA_POR_ID[id_]
    snap = pantalla.copy()
    AUDIO.sfx("secreto")
    t = 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return
        if any(k in K_OK or k in K_ATRAS for k in keys):
            return
        pantalla.blit(snap, (0, 0))
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((0, 0, 10, 190))
        pantalla.blit(velo, (0, 0))
        r = pygame.Rect(150, 230, ANCHO - 300, 340)
        dibujar_tarjeta(r, (255, 208, 60), (28, 22, 44, 245))
        pantalla.blit(pygame.transform.smoothscale(SPR_PERGAMINO, (60, 56)), (r.x + 20, r.y + 18 + int(math.sin(t * 0.1) * 3)))
        texto(pantalla, "¡FRAGMENTO DE HISTORIA!", F_MED, (255, 232, 130), (r.x + 100, r.y + 20))
        texto(pantalla, h[1], F_PEQ, (200, 190, 230), (r.x + 100, r.y + 54), desp=1)
        texto_ajustado(pantalla, h[2], fuente(24), (255, 255, 255), r.x + 30, r.y + 110, r.w - 60, 10)
        texto(pantalla, "ENTER: continuar   (lo puedes releer en HISTORIA)", F_PEQ, (170, 180, 210), (r.centerx, r.bottom - 28), centro=True)
        presentar()


def pantalla_game_over(puntos, mejor, record, nivel, nivel_cp, extra=""):
    """Devuelve 'cp', 'nueva', ('mundo', nivel), 'menu' o None (salir)."""
    snapshot = pantalla.copy()
    velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    velo.fill((10, 0, 0, 185))
    t = 0
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return None
        for k in keys:
            if k == pygame.K_t:
                pantalla_tienda("tienda")
            elif k == pygame.K_c:
                elegido = pantalla_mundos()
                if elegido is not None:
                    return ("mundo", elegido)
            elif k in K_OK:
                return "cp"
            elif k == pygame.K_n:
                return "nueva"
            elif k == pygame.K_ESCAPE:
                return "menu"
        pantalla.blit(snapshot, (0, 0))
        pantalla.blit(velo, (0, 0))
        texto_borde(pantalla, "GAME OVER", F_TITULO, (255, 80, 80), (80, 0, 0), (ANCHO // 2, 270), 4)
        lim = f"Llegaste al nivel {nivel} de {MAX_NIVELES}" if nivel <= MAX_NIVELES else f"Llegaste a la dimensión oculta (nivel {nivel})"
        texto(pantalla, lim, F_MED, (255, 220, 150), (ANCHO // 2, 350), centro=True)
        texto(pantalla, f"Puntos: {puntos}", F_GRANDE, (255, 255, 255), (ANCHO // 2, 415), centro=True)
        if record:
            col = (255, 225, 90) if (t // 15) % 2 == 0 else (255, 160, 60)
            texto(pantalla, "¡NUEVO RECORD!", F_MED, col, (ANCHO // 2, 470), centro=True)
        else:
            texto(pantalla, f"Mejor: {mejor}", F_MED, (200, 205, 230), (ANCHO // 2, 470), centro=True)
        dibujar_saldo(ANCHO // 2 - 190, 512)
        if (t // 30) % 2 == 0:
            txt = f"ENTER: seguir desde el nivel {nivel_cp}" if nivel_cp > 1 else "ENTER: reintentar"
            texto(pantalla, txt, F_MED, (255, 255, 255), (ANCHO // 2, 590), centro=True)
        texto(pantalla, "N: partida nueva      T: tienda      ESC: menú principal", F_PEQ, (200, 200, 225), (ANCHO // 2, 635), centro=True)
        boton = pygame.Rect(ANCHO // 2 - 150, 665, 300, 44)
        pygame.draw.rect(pantalla, (40, 60, 120), boton, border_radius=22)
        pygame.draw.rect(pantalla, (255, 226, 90), boton, 2, border_radius=22)
        texto(pantalla, "C: CAMBIAR MUNDO", F_MED, (255, 240, 150), boton.center, centro=True)
        dibujar_indicador_musica((20, ALTO - 34))
        presentar()


def pantalla_victoria(puntos, mejor, record, final=False):
    """Tras el nivel 50 devuelve 'dim' (entrar a la dimension oculta), 'nueva' o None. final=True: fin del Corazon."""
    fondo = crear_degradado_v(ANCHO, ALTO, (30, 20, 80), (150, 60, 100) if not final else (150, 100, 40))
    lluvia = [[random.uniform(0, ANCHO), random.uniform(-ALTO, 0), random.uniform(1.5, 4.0), random.randrange(len(FRUTAS)), random.uniform(0, math.tau)] for _ in range(40)]
    t = 0
    AUDIO.musica("historia")
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            return None
        for k in keys:
            if k == pygame.K_t:
                pantalla_tienda("tienda")
            elif k in K_OK:
                return "nueva" if (final or not PROG.dim_desbloqueada) else "dim"
            elif k == pygame.K_n:
                return "nueva"
            elif k == pygame.K_ESCAPE:
                return "menu"
        pantalla.blit(fondo, (0, 0))
        for f in lluvia:
            f[1] += f[2]
            if f[1] > ALTO + 40:
                f[1] = -60
                f[0] = random.uniform(0, ANCHO)
            pantalla.blit(SPR_FRUTAS_GRANDES[f[3]], (int(f[0] + math.sin(t * 0.04 + f[4]) * 25), int(f[1])))
        panel = pygame.Surface((ANCHO - 200, 640), pygame.SRCALPHA)
        pygame.draw.rect(panel, (10, 8, 30, 190), panel.get_rect(), border_radius=28)
        pantalla.blit(panel, (100, 110))
        bob = math.sin(t * 0.06) * 6
        texto_borde(pantalla, "¡FELICIDADES!", F_TITULO, (255, 226, 90), (120, 50, 10), (ANCHO // 2, 190 + bob), 4)
        txt = "¡Liberaste EL CORAZÓN DEL LABERINTO!" if final else f"Completaste los {MAX_NIVELES} niveles"
        texto(pantalla, txt, F_GRANDE if not final else F_MED, (255, 255, 255), (ANCHO // 2, 285), centro=True)
        pantalla.blit(sprite_jugador("abajo", t, tam=110), (ANCHO // 2 - 55, int(330 + math.sin(t * 0.12) * 10)))
        texto(pantalla, f"Puntos finales: {puntos}", F_GRANDE, (255, 240, 150), (ANCHO // 2, 470), centro=True)
        if record:
            col = (255, 225, 90) if (t // 15) % 2 == 0 else (255, 160, 60)
            texto(pantalla, "¡NUEVO RECORD!", F_MED, col, (ANCHO // 2, 520), centro=True)
        else:
            texto(pantalla, f"Mejor: {mejor}", F_MED, (200, 205, 230), (ANCHO // 2, 520), centro=True)
        dibujar_saldo(ANCHO // 2 - 190, 560)
        if not final and PROG.dim_desbloqueada:
            col = (255, 110, 150) if (t // 20) % 2 == 0 else (255, 220, 120)
            texto_borde(pantalla, "¡DIMENSIÓN OCULTA DESBLOQUEADA!", F_MED, col, (60, 0, 20), (ANCHO // 2, 625), 2)
            texto(pantalla, "ENTER: entrar a EL CORAZÓN DEL LABERINTO", F_MED, (255, 255, 255), (ANCHO // 2, 676), centro=True)
            texto(pantalla, "N: partida nueva      T: tienda      ESC: menú", F_PEQ, (200, 200, 225), (ANCHO // 2, 722), centro=True)
        else:
            if (t // 30) % 2 == 0:
                texto(pantalla, "ENTER: jugar de nuevo", F_MED, (255, 255, 255), (ANCHO // 2, 650), centro=True)
            texto(pantalla, "T: tienda      ESC: menú principal", F_PEQ, (200, 200, 225), (ANCHO // 2, 700), centro=True)
        dibujar_indicador_musica((20, ALTO - 34))
        presentar()


def pantalla_pausa(juego):
    """Pausa. Devuelve 'seguir' o 'menu'."""
    snap = pantalla.copy()
    AUDIO.pausar(True)
    sel, t = 0, 0
    ops = ["CONTINUAR", "CONFIGURACIÓN", "MENÚ PRINCIPAL"]
    while True:
        reloj.tick(FPS)
        t += 1
        keys, salir = leer_teclas()
        if salir:
            AUDIO.pausar(False)
            return "menu"
        for k in keys:
            if k in K_ARRIBA:
                sel = (sel - 1) % 3
            elif k in K_ABAJO:
                sel = (sel + 1) % 3
            elif k == pygame.K_ESCAPE or es_tecla(k, "pausa"):
                AUDIO.pausar(False)
                return "seguir"
            elif k in K_OK:
                if sel == 0:
                    AUDIO.pausar(False)
                    return "seguir"
                if sel == 1:
                    pantalla_config()
                    pantalla.blit(snap, (0, 0))
                else:
                    AUDIO.pausar(False)
                    return "menu"
        pantalla.blit(snap, (0, 0))
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((0, 0, 0, 160))
        pantalla.blit(velo, (0, 0))
        texto_borde(pantalla, "PAUSA", F_TITULO, (255, 255, 255), (30, 30, 60), (ANCHO // 2, 250), 4)
        for i, o in enumerate(ops):
            texto(pantalla, o, F_GRANDE if i == sel else F_MED, (255, 240, 150) if i == sel else (215, 215, 240), (ANCHO // 2, 360 + i * 70), centro=True)
        texto(pantalla, f"Nivel {juego.nivel}   ·   Puntos {juego.puntos}   ·   Frutacoins {PROG.monedas}", F_PEQ, (200, 205, 230), (ANCHO // 2, 590), centro=True)
        texto(pantalla, "Tu partida se guarda sola al salir al menú", F_PEQ, (170, 175, 205), (ANCHO // 2, 620), centro=True)
        presentar()


# ======================================================
# Bucle de la partida y programa principal
# ======================================================
def procesar_modales(juego):
    while juego.cola_modales:
        tipo, dato = juego.cola_modales.pop(0)
        if tipo == "fragmento":
            pantalla_fragmento(dato)
        elif tipo == "cinematica":
            cinematica(dato)
            juego.actualizar_musica()


def bucle_partida(juego):
    """Juega hasta salir. Devuelve 'menu' o 'salir'."""
    juego.actualizar_musica()
    while True:
        reloj.tick(FPS)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                juego.guardar_partida()
                return "salir"
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_F1 and juego.estado == "jugando":
                    dialogo_opciones("AYUDA RÁPIDA · CONTROLES", [
                        "Flechas / WASD: mover al personaje",
                        "ESPACIO: disparar · C: ataque cargado",
                        "B / SHIFT: bomba · E: ataque especial",
                        "R: rayo · Q: hielo · X: ráfaga",
                        "M: música · P / ESC: pausa",
                        "VOLVER A LA PARTIDA",
                    ])
                elif ev.key == pygame.K_ESCAPE and juego.estado in ("jugando", "nivel_completo"):
                    if pantalla_pausa(juego) == "menu":
                        juego.guardar_partida()
                        return "menu"
                elif es_tecla(ev.key, "musica"):
                    AUDIO.alternar()
                elif es_tecla(ev.key, "pausa") and juego.estado == "jugando":
                    if pantalla_pausa(juego) == "menu":
                        juego.guardar_partida()
                        return "menu"
        juego.actualizar(pygame.key.get_pressed())
        juego.dibujar()
        presentar()
        if juego.cola_modales:
            procesar_modales(juego)
        if juego.estado == "game_over":
            record = juego.puntos > 0 and juego.puntos > juego.record_previo
            eleccion = pantalla_game_over(juego.puntos, juego.mejor, record, juego.nivel, juego.cp_nivel)
            if isinstance(eleccion, tuple):
                juego.nueva_partida(eleccion[1])
            elif eleccion == "cp":
                juego.continuar()
            elif eleccion == "nueva":
                juego.nueva_partida()
            elif eleccion == "menu":
                PROG.partida = None
                PROG.guardar()
                return "menu"
            else:
                return "salir"
        elif juego.estado in ("victoria", "victoria_final"):
            final = juego.estado == "victoria_final"
            record = juego.puntos > juego.record_previo
            PROG.partida = None
            eleccion = pantalla_victoria(juego.puntos, juego.mejor, record, final)
            if eleccion == "dim":
                juego.nivel = NIVEL_DIM_INI
                juego.iniciar_nivel()
            elif eleccion == "nueva":
                juego.nueva_partida()
            elif eleccion == "menu":
                PROG.guardar()
                return "menu"
            else:
                return "salir"


def main():
    nivel_inicial = 1
    if "--nivel" in sys.argv:  # practicar un nivel concreto: --nivel 12
        try:
            nivel_inicial = max(1, min(MAX_NIVEL_TOTAL, int(sys.argv[sys.argv.index("--nivel") + 1])))
        except (ValueError, IndexError):
            pass
    pantalla.fill((18, 14, 40))
    texto(pantalla, "Cargando...", F_GRANDE, (255, 255, 255), (ANCHO // 2, ALTO // 2), centro=True)
    presentar()
    pygame.event.pump()
    AUDIO.iniciar()
    AUDIO.musica("menu")
    juego = Juego(nivel_inicial)
    while True:
        eleccion = pantalla_inicio(juego, nivel_inicial)
        if eleccion is None:
            break
        if eleccion[0] == "continuar" and PROG.partida:
            if not PROG.fragmentos:
                pass
            juego.nueva_partida(PROG.partida["nivel"], PROG.partida)
        else:
            if "intro" not in PROG.fragmentos:
                PROG.desbloquear_fragmento("intro")
                PROG.guardar()
                cinematica("intro")
            juego.nueva_partida(eleccion[1] if eleccion[0] == "nueva" else 1)
        resultado = bucle_partida(juego)
        if resultado == "salir":
            break
    PROG.guardar()
    pygame.quit()


if __name__ == "__main__":
    main()