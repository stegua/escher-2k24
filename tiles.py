# -*- coding: utf-8 -*-
"""
Libreria di supporto alla lezione sulle "Immagini Ricorsive", tenuta per il corso di Programmazione 1 al Dipartimento di Matematica
dell'Università di Pavia, nel 2018-2024.

SOURCES: 
    
    1. La libreria svgpath2mpl (appare nella seconda meta di questo file)
       e` stata presa da questa repository:
          https://github.com/nvictus/svgpath2mpl

    2. La classe Tile e` stata ripresa e riadatta da questo sito:
          https://github.com/mapio/programming-with-escher/blob/master/notebook.ipynb
                  
Per le licenze d'uso, controllare i rispettivi siti
"""

from __future__ import division, print_function

from math import sqrt

import re
import numpy as np

from matplotlib import rcParams, pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle, Arc
from matplotlib.transforms import Affine2D as T

from copy import deepcopy

"""
SVGPATH2MPL
~~~~~~~~~~~
Parse SVG path data strings into matplotlib `Path` objects.

A path in SVG is defined by a 'path' element which contains a
``d="(path data)"`` attribute that contains moveto, line, curve (both
cubic and quadratic Béziers), arc and closepath instructions. See the SVG
Path specification at <https://www.w3.org/TR/SVG/paths.html>.

:copyright: (c) 2016, Nezar Abdennur.
:license: BSD.

"""
__version__ = '0.1.0'
__all__ = ['parse_path', 'EndpointArc']


COMMAND_RE = re.compile(r"([MLHVCSQTAZ])([^MLHVCSQTAZ]*)", re.IGNORECASE)
FLOAT_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?")
COMMANDS = {
    'M' : (Path.MOVETO,),    # moveto
    'L' : (Path.LINETO,),    # line
    'H' : (Path.LINETO,),    # shorthand for horizontal line
    'V' : (Path.LINETO,),    # shorthand for vertical line
    'Q' : (Path.CURVE3,)*2,  # quadratic bezier
    'T' : (Path.CURVE3,)*2,  # shorthand for smooth quadratic bezier
    'C' : (Path.CURVE4,)*3,  # cubic bezier
    'S' : (Path.CURVE4,)*3,  # shorthand for smooth cubic bezier
    'Z' : (Path.CLOSEPOLY,), # closepath
    'A' : None               # arc
}
PARAMS = {
    'M' : 2, # moveto
    'L' : 2, # line
    'H' : 1, # shorthand for horizontal line
    'V' : 1, # shorthand for vertical line
    'Q' : 4, # quadratic bezier
    'T' : 4, # shorthand for smooth quadratic bezier
    'C' : 6, # cubic bezier
    'S' : 6, # shorthand for smooth cubic bezier
    'Z' : 0, # closepath
    'A' : 7  # arc
}

class EndpointArc(Arc):
    """
    Compute the path of an elliptical arc specified using "endpoint"
    parameterization.

    Parameters
    ----------
    start : pair of numbers
        The starting point of the arc path.
    radius : pair of numbers
        The x and y-components of the arc radius.
    angle : number
        The angle in degrees.
    large : bool
        Whether to generate a large arc spanning > 180 degrees (True) or a
        small arc spanning <= 180 degrees (False).
    sweep : bool
        Whether the line joining the center to arc sweeps through increasing
        angles (True) or decreasing angles (False).
    end : pair of numbers
        The final point of the arc path.

    Notes
    -----
    We must translate the "endpoint" to "center" parameterization.
    See <http://www.w3.org/TR/SVG/implnote.html#ArcConversionEndpointToCenter>.
    See also <http://stackoverflow.com/questions/197649/how-to-calculate-
    center-of-a-ellipse-by-two-points-and-radius-sizes>.

    """
    def __init__(self, start, radius, angle, large, sweep, end, **kwargs):
        x1, y1 = start
        rx, ry = radius
        x2, y2 = end
        def find_angle(u, v):
            u, v = map(np.asarray, [u, v])
            c = np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v)
            return np.arccos(np.clip(c, -1, 1))

        # Handle out-of-range parameters
        # http://www.w3.org/TR/SVG/implnote.html#ArcOutOfRangeParameters
        if rx == 0 or ry == 0:
            return Path([[x2, y2]], [Path.MOVETO])
        if rx < 0: rx = abs(rx)
        if ry < 0: ry = abs(ry)
        angle = angle % 360

        # Translate the origin to the midpoint of the line joining (x1,y1) and
        # (x2,y2) and rotate the x & y axes to align with the axes of the
        # ellipse
        # step 1: transform (x1, y1) to the new coordinate system
        phi_rad = angle * np.pi / 180
        x1p = np.cos(phi_rad)*(x1-x2)/2 + np.sin(phi_rad)*(y1-y2)/2
        y1p = -np.sin(phi_rad)*(x1-x2)/2 + np.cos(phi_rad)*(y1-y2)/2
        lambd = ( (x1p * x1p) / (rx * rx) ) + ( (y1p * y1p) / (ry * ry) )
        if lambd > 1:
            rx = np.sqrt(lambd) * rx
            ry = np.sqrt(lambd) * ry

        # step 2: find the center of the ellipse in the new coordinate system
        sign = -1 if large == sweep else 1
        a = ((rx*rx*ry*ry - rx*rx*y1p*y1p - ry*ry*x1p*x1p) /
             (rx*rx*y1p*y1p + ry*ry*x1p*x1p))
        cxp = sign * np.sqrt(a) * (rx*y1p / ry)
        cyp = sign * np.sqrt(a) * (-ry*x1p / rx)

        # step 3: transform (cx', cy') back to the original coordinate system
        cx = np.cos(phi_rad)*cxp - np.sin(phi_rad)*cyp + (x1+x2)/2
        cy = np.sin(phi_rad)*cxp + np.cos(phi_rad)*cyp + (y1+y2)/2

        # step 4: compute angles
        theta1 = find_angle(
            [1, 0],
            [(x1p - cxp)/rx, (y1p - cyp)/ry]) * 180/np.pi
        dt = find_angle(
            [(x1p-cxp)/rx,   (y1p-cyp)/ry],
            [(-x1p-cxp)/rx, (-y1p-cyp)/ry]) * 180/np.pi
        dt %= 360
        if not sweep and dt > 0:
            dt -= 360
        elif sweep and dt < 0:
            dt += 360
        theta2 = theta1 - dt

        # generate an arc using center parameterization
        super(EndpointArc, self).__init__(
            xy=(cx, cy),
            width=rx*2,
            height=ry*2,
            angle=angle,
            theta1=theta1,
            theta2=theta2)


def _tokenize_path(d):
    for command, args in COMMAND_RE.findall(d):
        values = [float(v) for v in FLOAT_RE.findall(args)]
        while values:
            params = PARAMS[command.upper()]
            consumed, values = values[:params], values[params:]
            yield command, consumed
            

def parse_path(d):
    """
    Parse a path definition string (i.e., path data or ``d`` attribute)
    defining a shape in SVG into a matplotlib path object for plotting.

    Parameters
    ----------
    d : str
        SVG path data string.

    Returns
    -------
    ``matplotlib.path.Path`` object.

    """
    all_verts = []
    all_codes = []
    current_point = np.array([0., 0.])
    last_verts = None
    last_command = None
    start_point = current_point

    for command, values in _tokenize_path(d):

        is_relative = command.islower()
        command = command.upper()

        if command == 'Z':
            # Close path. A point is required but ignored.
            verts = np.array(start_point)
            codes = COMMANDS[command]

        elif command == 'H':
            # Horizontal line.
            verts = np.r_[values, 0.]
            codes = COMMANDS[command]

        elif command == 'V':
            # Vertical line.
            verts = np.r_[0., values]
            codes = COMMANDS[command]

        elif command == 'T':
            # Smooth quadratic curve. If previous command was a Q/q or T/t,
            # the control point is the "reflection" of the second control point
            # in the previous segment.
            control_point = np.array([0., 0.])
            if last_command in ('Q', 'T'):
                x1, y1 = last_verts[-2]
                x2, y2 = current_point
                dx, dy = x2 - x1, y2 - y1
                control_point += [dx, dy]
            verts = np.r_[control_point, values]
            codes = COMMANDS[command]

        elif command == 'S':
            # Smooth cubic curve. If previous command was a C/c or S/s,
            # the control point is the "reflection" of the third control point
            # in the previous segment.
            control_point = np.array([0., 0.])
            if last_command in ('C', 'S'):
                x1, y1 = last_verts[-3]
                x2, y2 = current_point
                dx, dy = x2 - x1, y2 - y1
                control_point += [dx, dy]
            verts = np.r_[control_point, values]
            codes = COMMANDS[command]

        elif command == 'A':
            # Elliptical arc using endpoint parameterization.
            x1, y1 = 0., 0.
            rx, ry, phi, large, sweep, x2, y2 = values
            arc = EndpointArc((x1, y1), (rx, ry), phi, large, sweep, (x2, y2))
            arcpath = arc.get_path()
            # Get the right vertex coordinates
            verts = arc.get_patch_transform().transform(arcpath.vertices)
            codes = arcpath.codes
            # First command is a MOVETO, which would make a new subpath. Drop it.
            verts = verts[1:, :].ravel()
            codes = codes[1:].ravel()

        else:
            # M, L, Q, C
            verts = np.array(values)
            codes = COMMANDS[command]

        verts = verts.reshape(len(verts)//2, 2)

        if is_relative:
            verts += current_point

        last_verts = verts
        last_command = command
        current_point = verts[-1]
        all_verts.extend(verts.tolist())
        all_codes.extend(codes)

    return Path(all_verts, all_codes)


"""
----------------------------------------------------------------------------------
"""
__all__ = ['parse', 'flip', 'rot', 'rot45', 'over', 'beside', 'above', 'setSize', 'saveTile', 'quartet', 'nonet', 'TR', 'TQ', 'EDGE', 'ARC']

from collections import namedtuple 

Tile = namedtuple('Tile', ['path', 'fill', 'faceColor', 'edgeColor'])

class Tiles(namedtuple('Tiles', ['ts'])):
    def _ipython_display_(self):
        fig, ax = plt.subplots()
        for tile in self.ts:
            ax.add_patch(PathPatch(tile.path, 
                                   fill = tile.fill, 
                                   facecolor = tile.faceColor, 
                                   edgecolor = tile.edgeColor))    
        r = Rectangle((0,0), 1, 1, fill = False, edgecolor='white', linestyle = 'None')
        ax.add_patch(r)    
        plt.axis('equal')
        plt.axis('off')

def parse(p, color='black', fill=False, edgeColor='black', faceColor='white'):
    # Create path to draw
    path = parse_path(p).transformed(T().scale(1, -1).translate(0, 1))
    # Return new tile
    return Tiles(ts=[Tile(path, fill, faceColor, edgeColor)])

def setSize(n):
    rcParams['figure.figsize'] = n, n

def saveTile(tiles, filename, fmt="svg", dpi=600, title=''):
    fig, ax = plt.subplots()
    for tile in tiles.ts:
        ax.add_patch(PathPatch(tile.path, 
                               fill = tile.fill, 
                               facecolor = tile.faceColor, 
                               edgecolor = tile.edgeColor))    
    r = Rectangle((0,0), 1, 1, fill = False, edgecolor='white', linestyle='None')
    ax.add_patch(r)    
    plt.axis('equal')
    plt.axis('off')
    plt.figtext(0.5, 0.9, title, fontsize=30, ha='center')
    plt.savefig(filename, format=fmt, dpi=dpi)
    
def transform(tiles, transform):
    ts = []
    for tile in tiles.ts:
        ts.append(Tile(path=tile.path.transformed(transform),
                       fill=tile.fill,
                       edgeColor=tile.edgeColor,
                       faceColor=tile.faceColor))
    return Tiles(ts)

def union(tile0, tile1):
    ts = []
    for tile in tile0.ts:
        ts.append(tile)
    for tile in tile1.ts:
        ts.append(tile)
    return Tiles(ts) 

def flip(tiles):
    return transform(tiles, T().scale(-1, 1).translate(1, 0))
    
def rot(tiles):
    return transform(tiles, T().rotate_deg(90).translate(1, 0))
    
def rot45(tiles):
    return transform(tiles, T().rotate_deg(45).scale(1 / sqrt(2), 1 / sqrt(2)).translate(1 / 2, 1 / 2))
    
def over(tiles0, tiles1):
    return union(tiles0, tiles1)

def beside(tiles0, tiles1, n = 1, m = 1):
    den = n + m
    return union(
        transform(tiles0, T().scale(n / den, 1)),
        transform(tiles1, T().scale(m / den, 1).translate(n / den, 0))
    )

def above(tile0, tile1, n = 1, m = 1):
    den = n + m
    return union(
        transform(tile0, T().scale(1, n / den).translate(0, m / den)),
        transform(tile1, T().scale(1, m / den))
    )    

def quartet(p, q, r, s):
    return above(beside(p,q), beside(r,s))

def nonet(p, q, r, s, t, u, v, w, x):
    return above(
            beside(p, beside(q,r), 1, 2),
            above(
                beside(s, beside(t, u), 1, 2),
                beside(v, beside(w, x), 1, 2)
            ),
            1, 2)
   
blank = parse("M 0.0,0.0")
setSize(10)
 
# Sequenza di comandi per disegnare un triangolo
# Leggere la documentazione delle 'SVG path':
#    https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Paths
TR = """ M 0.,1.
         L 1.,1.
         L 0.,0.
         L 0.,1. """


# Sequenza di comandi per disegnare un triangolo
# Leggere la documentazione delle 'SVG path':
#    https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Paths
TQ = """ M 0.,1.
         L 1.,1.
         L 1.,0.
         L 0.,0.
         L 0.,1. """

# Sequenza di comandi per generare un 'edge'
# Per capire come funzionano le curve di Bezier, vedi:
#    https://en.wikipedia.org/wiki/B%C3%A9zier_curve
EDGE = """  M 0.,0.
            C 1.0,0.0 0.0,1.0 0.0,0.0 """

ARC = """  M 0.,1.
            C 0.0,1.0 0.0,0.0 1.0,0.0 """
            