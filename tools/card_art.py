"""Cut the illustration out of an official card scan and make it a game card picture (155x155 JPEG, like the
originals in Local Store asset/cards, notes 6.55).

The art box of a normal (non-Pendulum) card sits at a fixed place on the card: on the 421x614 scans it is
x 49-371, y 111-433 (323x323, measured on several cards: a grey bevel frame surrounds it). Larger scans of the same
layout scale. Pendulum cards have a wider art box and are not supported.

    python tools/card_art.py <scan.jpg> <out.jpg> [--preview out_big.png]
"""
import argparse
import sys

from PIL import Image

GAME_SIZE = 155
ART_BOX = (49 / 421, 111 / 614, 372 / 421, 434 / 614)  # left, top, right, bottom (exclusive)
CARD_RATIO = 614 / 421


def find_art_box(card):
    w, h = card.size
    return round(w * ART_BOX[0]), round(h * ART_BOX[1]), round(w * ART_BOX[2]), round(h * ART_BOX[3])


def cut_art(card):
    w, h = card.size
    if abs(h / w - CARD_RATIO) > 0.02:
        raise ValueError(f"{w}x{h} is not a full card scan")
    return card.convert("RGB").crop(find_art_box(card))


def game_picture(art):
    return art.resize((GAME_SIZE, GAME_SIZE), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("out")
    ap.add_argument("--preview", help="also save the full-size cut")
    args = ap.parse_args()
    card = Image.open(args.scan)
    try:
        art = cut_art(card)
    except ValueError as e:
        sys.exit(f"{args.scan}: {e}")
    print(f"{args.scan}: {card.size[0]}x{card.size[1]}, art box {find_art_box(card)}")
    if args.preview:
        art.save(args.preview)
    game_picture(art).save(args.out, quality=90)


if __name__ == "__main__":
    main()
