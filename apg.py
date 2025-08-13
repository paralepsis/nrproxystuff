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

base_url     = "https://netrunnerdb.com/api/2.0/public/decklist/"
runner_back  = "../nsg-runner.tiff"
corp_back    = "../nsg-corp.tiff"
rgb_profile  = "../ECI-RGB.V1.0.icc"
cmyk_profile = "../ISOcoated_v2_eci.icc"
cache_path   = "/Volumes/HomeX/rbross/nrdb-cache/"

resize_height = 346
resize_width = 243
usage = 'ANRProxyGenerator.py -d <deck id>'

def main(argv):
    deck_id = -1
    add_qr  = False
    back_path    = ""

    try:
        opts, args = getopt.getopt(argv, 'd:b:rcq', ["qrcode","deckid=","back="]) #Get the deck id from the command line

        for opt, arg in opts:
            if opt in ("-d", "--deckid"):
                deck_id = arg
            elif opt == "-r":
                back_path = runner_back
            elif opt == "-c":
                back_path = corp_back
            elif opt in ("-b", "--back"):
                back_path = arg
            elif opt in ("-q", "--qrcode"):
                add_qr = True
            else:
                print ("Unsupported argument found!")

        with requests.Session() as session:

            # print_memory_usage()
            decklist_url = base_url + str(deck_id)
            print(decklist_url)
            deck_response = session.get(decklist_url)
            # print_memory_usage()

            if deck_response.status_code == 200:
                deck_data = deck_response.json()
                card_nr = 1 # count for printing purposes, 0 reserved for identity

                print(f"Selected {deck_data['data'][0]['name']}.")

                for card_id, number in deck_data['data'][0]['cards'].items():
                    # note: human-centric page is https://netrunnerdb.com/en/card/{card_id}
                    #
                    with session.get(f"https://netrunnerdb.com/api/2.0/public/card/{card_id}") as card_response:
                        # print_memory_usage()
                        if card_response.status_code == 200:
                            card_json = card_response.json()
                            card_data = card_json['data'][0]
                            # print(card_data)
                            if back_path == "":
                                if card_data['side_code'] == "corp":
                                    print("Autodetected corp deck.")
                                    back_path = corp_back
                                else:
                                    print("Autodetected runner deck.")
                                    back_path = runner_back

                            print(f"  {number} x {card_data['stripped_title']} ({card_data['type_code']})")
                            sanitized_title = sanitize_filename(card_data['stripped_title'])

                            if card_data['type_code'] == "identity":
                                # Back of identity card: flipped card or duplicate of front
                                if "Flip side:" in card_data['stripped_text']:
                                    output_name = f"00_0_{sanitized_title}-flip.tiff"
                                    flip_id = f"{card_id}-0"
                                    cache_name  = f"{cache_path}/{flip_id}.tiff"
                                    get_card_front(flip_id, session, cache_path)
                                    shutil.copy(cache_name, output_name)
                                    # print(f"  {output_name} (flipped)")
                                else:
                                    cache_name  = f"{cache_path}/{card_id}.tiff"
                                    output_name = f"00_0_{sanitized_title}.tiff"
                                    get_card_front(card_id, session, cache_path)
                                    shutil.copy(cache_name, output_name)
                                    # print(f"  {output_name} (dup)")

                                # Normal front of identity card
                                cache_name  = f"{cache_path}/{card_id}.tiff"
                                output_name = f"00_1_{sanitized_title}.tiff"
                                get_card_front(card_id, session, cache_path)
                                shutil.copy(cache_name, output_name)
                                # print(f"  {output_name}")

                            else:
                                get_card_front(card_id, session, cache_path)

                                for i in range(number):
                                    # output_name = f"{card_nr:02d}_0_back.tiff"
                                    # shutil.copy(back_path, output_name)
                                    # print(f"  {output_name}")

                                    cache_name  = f"{cache_path}/{card_id}.tiff"
                                    output_name = f"{card_nr:02d}_1_{sanitized_title}.tiff"
                                    shutil.copy(cache_name, output_name)
                                    # print(f"  {output_name}")
                                    # inefficient, but effective way to add QR code
                                    if add_qr == True:
                                        add_qr_to_cmyk_tiff(output_name, f"https://netrunnerdb.com/en/card/{card_id}")
                                    card_nr += 1

                print("All cards downloaded and converted.")

                print("Adding QR code card.")
                output_name = f"{card_nr:02d}_0_back.tiff"
                shutil.copy(back_path, output_name)
                output_name = f"{card_nr:02d}_1_qrcode.tiff"
                create_qr_card_cmyk(decklist_url, output_name)

                print("Adding backs.")
                for i in range(1,card_nr+1):
                    output_name = f"{i:02d}_0_back.tiff"
                    shutil.copy(back_path, output_name)
                    # print(f"  {output_name}")


                tiffs_to_cmyk_pdf(".", "./deck-pre.pdf")
                dedup_pdf("./deck-pre.pdf", "./deck.pdf");



                return
            else:
                print("Error: Could not retrieve decklist")

    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(usage)
        sys.exit(2)

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
        f"PDF:{output_pdf}"
    ]

    print("Running:", " ".join(command))
    subprocess.run(command, check=True)
    print(f"Saved to {output_pdf}")


def get_card_front(card_id, session, cache_path):
    nrdb_file      = f"{cache_path}/{card_id}.jpg"
    converted_file = f"{cache_path}/{card_id}.tiff"

    if not os.path.exists(nrdb_file):
        print(f"    Getting https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg.")
        image_response = session.get(f"https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg")
        if image_response.status_code == 200:
            dpi     = (300, 300)
            size_in = (2.5, 3.5)
            size_px = (int(size_in[0]*dpi[0]), int(size_in[1]*dpi[1]))
       
            with open(nrdb_file, "wb") as f:
                f.write(image_response.content)
            time.sleep(3)

    if not os.path.exists(converted_file):
        print(f"    Converting {nrdb_file} to CMYK TIFF with border.")
        convert_to_cmyk_icc(nrdb_file, converted_file)

    return True

def convert_to_cmyk_icc(input_path, output_path):
    subprocess.run([
        "magick",
        input_path,
        "-resize", "750x1050",
        "-filter", "Mitchell", # Lanczo, Robidoux, Mitchell, Catrom
        "-bordercolor", "black",
        "-units", "PixelsPerInch",
        "-border", "38x38",
        "-density", "300",
        "-profile", rgb_profile,
        "-profile", cmyk_profile,
        "-compress", "Zip",
        output_path
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
    rich_black = (int(0.60*255), int(0.40*255), int(0.40*255), 255)

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

def dedup_pdf(input_path, output_path):
    cmd = [
        "gs",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress",  # high quality for print
        f"-sOutputFile={output_path}",
        input_path
    ]

    subprocess.run(cmd, check=True)
    print(f"Saved deduped PDF to {output_path}")



# Example usage


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(usage)
    else:
        main(sys.argv[1:])


