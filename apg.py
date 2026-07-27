import requests
import shutil
import psutil
import qrcode
import os
from PIL import Image, ImageOps
from io import BytesIO
from pathlib import Path
import subprocess
import time
import math
import sys
import getopt
import re
import tempfile
import json
import xml.etree.ElementTree as ET
from decklist import create_decklist_card_grouped_cmyk

base_url     = "https://netrunnerdb.com/api/2.0/public/decklist/"
runner_back  = "backs/chatgpt-runner-back.tiff"
corp_back    = "backs/chatgpt-corp-back.tiff"
rgb_profile_name = "sRGB_v4_ICC_preference.icc"
cmyk_profile_name = "CGATS21_CRPC1.icc"
rgb_profile_url = "https://registry.color.org/rgb-registry/profiles/sRGB_v4_ICC_preference.icc"
cmyk_profile_url = "https://help.drivethrupartners.com/hc/en-us/article_attachments/12904358770455/CGATS21_CRPC1.icc"
default_cache_path = Path.home() / "nrdb-cache"

program_name = Path(sys.argv[0]).name or "apg.py"
usage = f'{program_name} (-d <deck id> | --json <deck json> | --octgn <deck octgn>) [--cache <cache path>]'

def main(argv):
    deck_id   = None
    json_path = None
    octgn_source = None
    add_qr    = False
    back_path = ""
    xl_img    = True
    cache_path = default_cache_path

    try:
        opts, args = getopt.getopt(argv, 'd:b:rcqx', ["qrcode","deckid=","back=", "cache=", "json=", "octgn="]) #Get the deck id from the command line

        for opt, arg in opts:
            if opt in ("-d", "--deckid"):
                deck_id = arg
            elif opt == "--json":
                json_path = Path(arg).expanduser()
            elif opt == "--octgn":
                octgn_source = arg
            elif opt == "-r":
                back_path = runner_back
            elif opt == "-x":
                xl_img = True
            elif opt == "-c":
                back_path = corp_back
            elif opt in ("-b", "--back"):
                back_path = arg
            elif opt == "--cache":
                cache_path = Path(arg).expanduser()
            elif opt in ("-q", "--qrcode"):
                add_qr = True
            else:
                print ("Unsupported argument found!")

        input_count = sum(value is not None for value in (deck_id, json_path, octgn_source))
        if input_count != 1:
            print("Error: provide exactly one of --deckid, --json, or --octgn")
            print(usage)
            sys.exit(2)

        cache_path.mkdir(parents=True, exist_ok=True)
        rgb_profile = ensure_profile(Path.cwd() / rgb_profile_name, rgb_profile_url)
        cmyk_profile = ensure_profile(Path.cwd() / cmyk_profile_name, cmyk_profile_url)

        with requests.Session() as session:
            if deck_id is not None:
                deck = load_nrdb_deck(deck_id, session)
            elif json_path is not None:
                deck = load_json_deck(json_path)
            else:
                deck = load_octgn_deck(octgn_source, session)

            build_dir = Path(tempfile.mkdtemp(prefix=f"nrproxystuff-{deck['build_tag']}-"))
            print(f"Selected {deck['name']}.")
            print(f"Building PDF assets in {build_dir}.")

            generate_deck(
                deck,
                session,
                cache_path,
                build_dir,
                back_path,
                xl_img,
                add_qr,
                cmyk_profile,
            )

            return

    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(usage)
        sys.exit(2)


def load_nrdb_deck(deck_id, session):
    decklist_url = base_url + str(deck_id)
    print(decklist_url)
    deck_response = session.get(decklist_url)
    deck_response.raise_for_status()
    deck_data = deck_response.json()['data'][0]
    return {
        'name': deck_data['name'],
        'deck_id': str(deck_id),
        'source_url': f"https://www.netrunnerdb.com/en/decklist/{str(deck_id)}",
        'output_stem': f"deck-{deck_id}",
        'build_tag': str(deck_id),
        'cards': [
            {
                'card_id': card_id,
                'count': count,
                'name': None,
            }
            for card_id, count in deck_data['cards'].items()
        ],
    }


def load_json_deck(json_path):
    print(f"Loading deck from {json_path}")
    deck_data = json.loads(Path(json_path).read_text())
    cards = deck_data.get('cards')
    if not isinstance(cards, list) or not cards:
        raise ValueError("JSON deck must contain a non-empty 'cards' list")

    normalized_cards = []
    for card in cards:
        if 'card_id' not in card or 'count' not in card:
            raise ValueError("Each JSON card entry must contain 'card_id' and 'count'")
        normalized_cards.append({
            'card_id': str(card['card_id']),
            'count': int(card['count']),
            'name': card.get('name'),
        })

    deck_name = deck_data.get('name') or json_path.stem
    deck_id = deck_data.get('deck_id')
    source_url = deck_data.get('source_url') or source_url_from_deck_id(deck_id)
    return {
        'name': deck_name,
        'deck_id': deck_id,
        'source_url': source_url,
        'output_stem': f"deck-{sanitize_filename(deck_name) or sanitize_filename(json_path.stem) or 'json'}",
        'build_tag': sanitize_filename(deck_name) or sanitize_filename(json_path.stem) or 'json',
        'cards': normalized_cards,
    }


def load_octgn_deck(octgn_source, session):
    octgn_url = octgn_source if is_url(octgn_source) else None
    nrdb_deck_id = nrdb_deck_id_from_octgn_url(octgn_url) if octgn_url else None
    if nrdb_deck_id is not None:
        return load_nrdb_deck(nrdb_deck_id, session)

    if octgn_url is not None:
        print(f"Loading OCTGN deck from {octgn_url}")
        response = session.get(octgn_url)
        response.raise_for_status()
        octgn_text = response.text
        source_url = octgn_url
        source_stem = octgn_url.rstrip('/').split('/')[-1] or 'octgn'
    else:
        octgn_path = Path(octgn_source).expanduser()
        print(f"Loading OCTGN deck from {octgn_path}")
        octgn_text = octgn_path.read_text()
        source_url = None
        source_stem = octgn_path.stem

    cards = parse_octgn_cards(octgn_text)
    deck_name = sanitize_filename(source_stem) or 'octgn'
    return {
        'name': source_stem,
        'deck_id': None,
        'source_url': source_url,
        'output_stem': f"deck-{deck_name}",
        'build_tag': deck_name,
        'cards': cards,
    }


def parse_octgn_cards(octgn_text):
    root = ET.fromstring(octgn_text)
    cards = []
    for card in root.findall('.//card'):
        octgn_card_id = card.attrib.get('id', '')
        card_id = octgn_card_id_from_card_id(octgn_card_id)
        cards.append({
            'card_id': card_id,
            'count': int(card.attrib['qty']),
            'name': (card.text or '').strip() or None,
        })
    if not cards:
        raise ValueError("OCTGN deck must contain at least one <card> entry")
    return cards


def source_url_from_deck_id(deck_id):
    if not deck_id:
        return None
    return f"https://www.netrunnerdb.com/en/decklist/{deck_id}"


def is_url(value):
    return value.startswith("http://") or value.startswith("https://")


def nrdb_deck_id_from_octgn_url(octgn_url):
    if octgn_url is None:
        return None
    match = re.search(r'/decklist/export/octgn/([0-9a-fA-F-]+)$', octgn_url)
    if not match:
        return None
    return match.group(1)


def octgn_card_id_from_card_id(octgn_card_id):
    match = re.search(r'(\d+)$', octgn_card_id)
    if match is None:
        raise ValueError(f"Could not extract NRDB card ID from OCTGN card id: {octgn_card_id}")
    return match.group(1)


def generate_deck(deck, session, cache_path, build_dir, back_path, xl_img, add_qr, cmyk_profile):
    card_nr = 1 # count for printing purposes, 0 reserved for identity
    side = ""
    card_meta = {}

    for deck_card in deck['cards']:
        card_id = deck_card['card_id']
        number = deck_card['count']
        with session.get(f"https://netrunnerdb.com/api/2.0/public/card/{card_id}") as card_response:
            card_response.raise_for_status()
            card_json = card_response.json()
            card_data = card_json['data'][0]

            card_meta[card_id] = {
                'title': card_data['stripped_title'],
                'type_code': card_data['type_code'],
                'count': number,
            }

            if back_path == "":
                if card_data['side_code'] == "corp":
                    print("Autodetected corp deck.")
                    side = "corp"
                    back_path = corp_back
                else:
                    print("Autodetected runner deck.")
                    side = "runner"
                    back_path = runner_back

            print(f"  {number} x {card_data['stripped_title']} ({card_data['type_code']})")
            sanitized_title = sanitize_filename(card_data['stripped_title'])

            if card_data['type_code'] == "identity":
                if "Flip side:" in card_data['stripped_text']:
                    output_name = build_dir / f"00_0_{sanitized_title}-flip.tiff"
                    flip_id = f"{card_id}-0"
                    cache_name = cache_path / f"{flip_id}.tiff"
                    get_card_front(flip_id, session, cache_path, xl_img)
                    shutil.copy(cache_name, output_name)
                else:
                    cache_name = cache_path / f"{card_id}.tiff"
                    output_name = build_dir / f"00_0_{sanitized_title}.tiff"
                    get_card_front(card_id, session, cache_path, xl_img)
                    shutil.copy(cache_name, output_name)

                cache_name = cache_path / f"{card_id}.tiff"
                output_name = build_dir / f"00_1_{sanitized_title}.tiff"
                get_card_front(card_id, session, cache_path, xl_img)
                shutil.copy(cache_name, output_name)
            else:
                get_card_front(card_id, session, cache_path, xl_img)

                for i in range(number):
                    cache_name = cache_path / f"{card_id}.tiff"
                    output_name = build_dir / f"{card_nr:02d}_1_{sanitized_title}.tiff"
                    shutil.copy(cache_name, output_name)
                    if add_qr == True:
                        print(f"  Adding QR code.")
                        add_qr_to_cmyk_tiff(output_name, f"https://netrunnerdb.com/en/card/{card_id}")
                    card_nr += 1

    print("All cards downloaded and converted.")

    print("Adding backs.")
    for i in range(1, card_nr):
        output_name = build_dir / f"{i:02d}_0_back.tiff"
        shutil.copy(back_path, output_name)

    print("Adding decklist card.")
    decklist_output = build_dir / f"{card_nr:02d}_0_list.tiff"
    create_decklist_card_grouped_cmyk(card_meta, side, decklist_output)

    reference_output = build_dir / f"{card_nr:02d}_1_qrcode.tiff"
    if deck['source_url']:
        create_qr_card_cmyk(deck['source_url'], reference_output)
    else:
        reference_output = build_dir / f"{card_nr:02d}_1_list.tiff"
        shutil.copy(decklist_output, reference_output)

    deck_pre_pdf = build_dir / "deck-pre.pdf"
    tiffs_to_cmyk_pdf(build_dir, deck_pre_pdf)
    deck_name = Path(f"./{deck['output_stem']}.pdf")
    dedup_pdf(deck_pre_pdf, deck_name, cmyk_profile)

def tiffs_to_cmyk_pdf(input_dir, output_pdf):
    input_path = Path(input_dir)
    tiff_files = sorted(input_path.glob("*.tiff"))

    if not tiff_files:
        print("No TIFF files found.")
        return

    # Create command to pass to ImageMagick
    command = [
        "magick",
        *[str(f) for f in tiff_files],     # list of .tiff file paths
        # "-colorspace", "CMYK",             # preserve CMYK
        "-compress", "Zip",                # good quality
        "-density", "300",                 # DPI for print
        f"PDF:{str(output_pdf)}"
    ]

    print("Running:", " ".join(command))
    subprocess.run(command, check=True)
    print(f"Saved to {output_pdf}")


def ensure_profile(profile_path, profile_url):
    if profile_path.exists():
        return profile_path

    print(f"Downloading {profile_path.name}.")
    response = requests.get(profile_url)
    response.raise_for_status()
    profile_path.write_bytes(response.content)
    return profile_path


def get_card_front(card_id, session, cache_path, xl_img):
    if not xl_img:
        nrdb_file      = cache_path / f"{card_id}.jpg"
    else:
        nrdb_file      = cache_path / f"{card_id}.webp"

    converted_file = cache_path / f"{card_id}.tiff"

    if not os.path.exists(nrdb_file):
        if not xl_img:
            print(f"    Getting https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg.")
            image_response = session.get(f"https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg")
        else:
            print(f"    Getting https://card-images.netrunnerdb.com/v2/xlarge/{card_id}.webp.")
            image_response = session.get(f"https://card-images.netrunnerdb.com/v2/xlarge/{card_id}.webp")
        if image_response.status_code == 200:
            dpi     = (300, 300)
            size_in = (2.5, 3.5)
            size_px = (int(size_in[0]*dpi[0]), int(size_in[1]*dpi[1]))
       
            with open(nrdb_file, "wb") as f:
                f.write(image_response.content)
            time.sleep(3)

    if not os.path.exists(converted_file):
        print(f"    Converting {nrdb_file} to CMYK TIFF with border.")
        convert_to_cmyk_icc(nrdb_file, converted_file, Path.cwd() / rgb_profile_name, Path.cwd() / cmyk_profile_name)

    return True

def convert_to_cmyk_icc(input_path, output_path, rgb_profile, cmyk_profile):
    subprocess.run([
        "magick",
        str(input_path),
        "-resize", "785x1100", # was 750x1050, then 749x1050 (adding 10px/side)
        "-filter", "Lanczos", # Lanczos, RobidouxSharp, Mitchell, Catrom
        "-background", "black",
	"-gravity", "center",
	"-extent", "825x1125",
        "-sharpen", "0x0.5",
        "-units", "PixelsPerInch",
        "-density", "300",
        "-profile", str(rgb_profile),
        "-profile", str(cmyk_profile),
        "-compress", "Zip",
        str(output_path)
    ], check=True)

    return

def sanitize_filename(s):
    # Replace all non-alphanumeric, non-underscore, non-dash characters with "_"
    return re.sub(r'[^a-zA-Z0-9_-]+', '_', s).strip('_')

def print_memory_usage(note=""):
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 ** 2
    print(f"[MEM] {note} {mem_mb:.2f} MB")

def add_qr_to_cmyk_tiff(
    tiff_path,
    data,
    qr_size_in=0.6,      # physical size of the QR on the card (inches)
    margin_in=0.125,      # distance from edges (inches)
    dpi_default=300,
    pure_k=True           # True = K-only; False = rich black CMYK tuple
):
    tiff_path = Path(tiff_path)
    im = Image.open(tiff_path)

    # Ensure CMYK base
    if im.mode != "CMYK":
        im = im.convert("CMYK")

    # Pull DPI & ICC profile if present
    dpi = im.info.get("dpi", (dpi_default, dpi_default))
    icc = im.info.get("icc_profile", None)

    # Build 1-bit QR mask (crisp edges)
    qr = qrcode.QRCode(
        version=None,  # auto fit
        error_correction=qrcode.constants.ERROR_CORRECT_M, # H is more robust
        box_size=10,
        border=3 # spec says 4
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_mask = qr.make_image(fill_color="black", back_color="white").convert("1")

    # Size in pixels
    qr_px = (int(qr_size_in * dpi[0]), int(qr_size_in * dpi[1]))
    qr_mask = qr_mask.resize(qr_px, Image.NEAREST)  # keep edges crisp

    # Make the ink tile (pure K or rich black)
    if pure_k:
        # C=M=Y=0, K=100%
        tile_color = (0, 0, 0, 255)
    else:
        # e.g., rich black C60 M40 Y40 K100
        tile_color = (153, 102, 102, 255)  # 0..255 scaling of 60/40/40/100%

    qr_tile = Image.new("CMYK", qr_px, tile_color)

    # Compute NE (upper-right) position with margin
    margin_px = (int(margin_in * dpi[0]), int(margin_in * dpi[1]))
    x = im.width - qr_px[0] - margin_px[0]
    y = margin_px[1]

    # 5) Lay down a solid WHITE background first (covers quiet zone & modules)
    white_cmyk = (0,0,0,0)
    white_tile = Image.new("CMYK", qr_px, white_cmyk)
    im.paste(white_tile, (x, y))  # no mask → fully opaque white patch

    # Paste via mask (ink where mask is black → invert to use as alpha)
    mask = ImageOps.invert(qr_mask.convert("L"))  # white=opaque for paste
    im.paste(qr_tile, (x, y), mask)

    # Save back, preserving DPI and ICC, with TIFF compression
    im.save(
        # tiff_path.with_suffix(".qr.tiff"),
        tiff_path,
        format="TIFF",
        dpi=dpi,
        compression="tiff_adobe_deflate",
        icc_profile=icc
    )

def create_qr_card_cmyk(data, output_path, dpi=300):
    # === 1. Generate QR code ===
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_mask = qr.make_image(fill_color="black", back_color="white").convert("1") # 1-bit mask

    # 2) Sizes
    card_px = (int(2.75 * dpi), int(3.75 * dpi))  # 825x1125 at 300 DPI
    qr_target = int(2.0 * dpi)                    # 2.0" square → 600px
    qr_mask = qr_mask.resize((qr_target, qr_target), Image.NEAREST)  # preserve crisp edges

    # 3) CMYK canvas (paper white)
    card = Image.new("CMYK", card_px, (0, 0, 0, 0))  # CMYK white

    # 4) Rich black swatch in CMYK: C=60%, M=40%, Y=40%, K=100% → scale 0..255
    # rich_black = (int(0.60*255), int(0.40*255), int(0.40*255), 255)
    rich_black = (0,0,0,255)

    # Create a solid CMYK tile the size of the QR
    qr_tile = Image.new("CMYK", (qr_target, qr_target), rich_black)

    # 5) Paste using the 1-bit mask (ink where mask is black)
    x = (card_px[0] - qr_target) // 2
    y = (card_px[1] - qr_target) // 2
    # Invert mask because paste uses non-zero mask as “use source”
    qr_mask_inv = ImageOps.invert(qr_mask.convert("L"))
    card.paste(qr_tile, (x, y), qr_mask_inv)

    # 6) Save CMYK TIFF with proper units/DPI and compression
    card.save(output_path, format="TIFF", dpi=(dpi, dpi), compression="tiff_adobe_deflate")
    # print(f"Saved QR card to {output_path}")

def dedup_pdf(input_path, output_path, cmyk_profile):
    cmd = [
        "gs", "-q",
        "-dBATCH",
        "-dNOSAFER", # This is strictly here to let gs get to the CMYK profile listed below.
        "-dNOPAUSE",
        "-sDEVICE=pdfwrite",
        "-sProcessColorModel=DeviceCMYK",
        f"-sOutputICCProfile={str(cmyk_profile)}",
        "-dPDFX=true",
        "-dPDFSETTINGS=/prepress",  # high quality for print
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=false",
        "-dCompressFonts=true",
        f"-sOutputFile={str(output_path)}",
        str(input_path)
    ]

    subprocess.run(cmd, check=True)
    print(f"Saved deduped, hopefully PDF/X-1a:2003 compliant PDF to {output_path}.")



# Example usage


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(usage)
    else:
        main(sys.argv[1:])
