from PIL import Image, ImageDraw, ImageFont, ImageOps
from collections import defaultdict, Counter

def _pt(pt, dpi):  # points -> pixels
    return max(1, int(round(pt * dpi / 72.0)))

def _try_load_font(pref_paths, size_px):
    for p in pref_paths:
        try:
            return ImageFont.truetype(p, size_px)
        except Exception:
            pass
    return ImageFont.load_default()

def _section_order_for_side(side):
    if side == "corp":
        # Common Corp order
        return [
            ("identity", "Identity"),
            ("agenda",   "Agendas"),
            ("asset",    "Assets"),
            ("operation","Operations"),
            ("upgrade",  "Upgrades"),
            ("ice",      "ICE"),
        ]
    # Runner order
    return [
        ("identity",   "Identity"),
        ("event",      "Events"),
        ("hardware",   "Hardware"),
        ("resource",   "Resources"),
        ("program",    "Programs"),
        ("icebreaker", "Icebreakers"),
    ]

def create_decklist_card_grouped_cmyk(card_meta, side, output_path,
                                      dpi=300, size_in=(2.75, 3.75),
                                      two_columns=True, body_pt=9):
    """
    card_meta: dict { card_id: { 'title': str, 'type_code': str, 'count': int } }
    """
    W, H = int(size_in[0]*dpi), int(size_in[1]*dpi)     # 825 x 1125
    img = Image.new("CMYK", (W, H), (0,0,0,0))          # white CMYK
    draw = ImageDraw.Draw(img)

    preferred_fonts = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    header_font = _try_load_font(preferred_fonts, _pt(11, dpi))
    body_font   = _try_load_font(preferred_fonts, _pt(body_pt, dpi))

    M  = _pt(12, dpi)    # outer margin
    G  = _pt(10, dpi)    # column gutter
    y  = M
    k  = (0,0,0,255)
    k60= (0,0,0,int(255*0.6))

    items = []
    for key, val in card_meta.items():
        items.append((val['count'], val['title'], val['type_code']))

    # Normalize "icebreaker" subclass: sometimes breakers are "program" with subtype
    # If you already resolved real type_code as "icebreaker", great. Otherwise, leave as-is.

    type_codes_present = {t for _,_,t in items}
    order = _section_order_for_side(side)
    order_map = {t:i for i,(t,_) in enumerate(order)}

    # group and sort within groups by title
    grouped = defaultdict(list)
    for cnt, title, tcode in items:
        grouped[tcode].append((title, cnt))

    # Make an ordered list of rendered lines with headers
    sections = []
    for tcode, label in order:
        if tcode not in grouped:
            continue
        # header marker
        sections.append(("__HEADER__", label))
        for title, cnt in sorted(grouped[tcode], key=lambda x: x[0].lower()):
            sections.append(("__LINE__", f"{cnt}× {title}"))

    if not sections:
        sections = [("__HEADER__", "Cards"), ("__LINE__", "No cards found")]

    # Columns
    col_count = 2 if two_columns else 1
    col_w = (W - 2*M - (G if col_count==2 else 0)) // col_count
    col_x = [M, M + col_w + G][:col_count]
    usable_height = H - M - y

    # Draw for real (sequential column fill: left column top-to-bottom, then right column)
    col_y = [y]*col_count
    col_used = [0]*col_count
    col_idx = 0

    # Precompute block heights and wrapped lines in order
    prepared = []
    for kind, text in sections:
        if kind == "__HEADER__":
            fh = header_font.getbbox("Ag")[3] - header_font.getbbox("Ag")[1]
            prepared.append(("__HEADER__", text, fh, [text]))
        else:
            fh = body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1]
            wrap = []
            words = text.split()
            cur = ""
            while words:
                w = words.pop(0)
                t = (cur + " " + w).strip()
                if (body_font.getbbox(t)[2] - body_font.getbbox(t)[0]) <= (col_w - _pt(2, dpi)):
                    cur = t
                else:
                    if cur: wrap.append(cur)
                    cur = w
            if cur: wrap.append(cur)
            prepared.append(("__LINE__", text, fh, wrap))

    for kind, text, fh, lines_wrapped in prepared:
        # compute block height
        if kind == "__HEADER__":
            block_h = fh + _pt(3, dpi)
        else:
            block_h = fh*len(lines_wrapped) + _pt(2, dpi)

        # If doesn't fit in current column, move to next column
        if col_used[col_idx] + block_h > usable_height and col_idx + 1 < col_count:
            col_idx += 1

        # If still doesn't fit and no more columns, stop
        if col_used[col_idx] + block_h > usable_height and col_idx == col_count - 1:
            break

        # Draw
        x = col_x[col_idx]
        yy = col_y[col_idx]
        if kind == "__HEADER__":
            draw.text((x, yy), text, fill=k, font=header_font)
            yy += fh + _pt(3, dpi)
        else:
            for line in lines_wrapped:
                draw.text((x, yy), line, fill=k, font=body_font)
                yy += fh
            yy += _pt(2, dpi)

        # Update column usage
        col_y[col_idx] = yy
        col_used[col_idx] += block_h

    img.save(output_path, format="TIFF", dpi=(dpi, dpi), compression="tiff_adobe_deflate")
    print(f"Saved grouped decklist to {output_path}")

