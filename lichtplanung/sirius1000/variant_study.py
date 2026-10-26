"""
Varianten der neuen Blende B3a: Tiefe, Neigung, Lochung und Wangentiefe gegen Blendung der Person,
Abweichung zur Blende 3 und Gleichmäßigkeit der Arena-Reihe bei 8 m.

    python variant_study.py [ordner]
"""

import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
import arena  # noqa: E402
from blendung import LVK, PERSON_DISTANCE, evaluate, floor_eh_mean  # noqa: E402
from ldt2ies import read_ies  # noqa: E402
from perforation import free_lvk, lumen  # noqa: E402
from visor_design import CHEEK_DEPTH, SOURCE_IES, TARGET_IES, Visor, design_lvk, target_error  # noqa: E402


def lvk_from_table(c, g, table):
    lvk = LVK.__new__(LVK)
    lvk.c, lvk.g, lvk.t = np.array(c), np.array(g), np.array(table)
    lvk.flux, lvk.name = lumen(c, g, table), "variante"
    return lvk


def main():
    c, g, table, t_old, i_free, _ = free_lvk(os.path.join(DATA_DIR, SOURCE_IES))
    base = (c, g, table, t_old, i_free)
    target = np.array(read_ies(os.path.join(DATA_DIR, TARGET_IES))[2])
    lines = ["Tiefe  Wange  Neig.  Loch | Fehler  Lm-Verl. | GR 5 m  GR 8 m | Reihe 8 m: E   U0    Klasse"]
    combos = [(cheek, depth, beta, p) for cheek in (None, CHEEK_DEPTH)  # None: wie Stirnblech
              for depth in (0.35, 0.40, 0.45, 0.50) for beta in (0, 10, 20) for p in (0.10, 0.20)]
    for cheek, depth, beta, p in combos:
        v = Visor(depth, beta, p, cheek)
        i_new, _ = design_lvk(v, base)
        err, _ = target_error(i_new, target, c, g)
        lvk = lvk_from_table(c, g, i_new)
        gr = [evaluate(lvk, h, PERSON_DISTANCE, eh_mean=floor_eh_mean(lvk, h)[0], d_hole=v)["GR"]
              for h in (5.0, 8.0)]
        em, _, u0 = arena.continuous_row(lvk, 8.0)
        loss = 1 - lvk.flux / 111141.0
        lines.append(f"{depth * 1000:4.0f}  {v.Dc * 1000:4.0f}   {beta:+3d}°  {p * 100:3.0f} % | "
                     f"{err:.3f}  {loss * 100:5.1f} %  | {gr[0]:5.1f}  {gr[1]:5.1f}  | "
                     f"{em:6.0f}  {u0:.3f}  {arena.classify(em, u0)}")
        print(lines[-1], flush=True)
    open(os.path.join(DATA_DIR, "variant_study.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
