import requests
import shutil
import psutil
import qrcode
import os
from PIL import Image
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

back_path = ""

def main(argv):
    deck_id = -1
    try:
        opts, args = getopt.getopt(argv, 'd:b:rc', ["deckid=","back="]) #Get the deck id from the command line

        back = "../nsg-runner.tiff"

        for opt, arg in opts:
            if opt in ("-d", "--deckid"):
                deck_id = arg
            elif opt in ("-r"):
                back_path = runner_back
            elif opt in ("-c"):
                back_path = corp_back
            elif opt in ("-b", "--back"):
                back_path = arg
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

                for card_id, number in deck_data['data'][0]['cards'].items():
                    # note: human-centric page is https://netrunnerdb.com/en/card/{card_id}
                    #
                    with session.get(f"http://netrunnerdb.com/api/2.0/public/card/{card_id}") as card_response:
                        # print_memory_usage()
                        if card_response.status_code == 200:
                            card_json = card_response.json()
                            card_data = card_json['data'][0]
                            cache_name  = f"{cache_path}/{card_id}.tiff"
                            # print(card_data)
                            print(f"{number} x {card_data['stripped_title']} ({card_data['type_code']})")
                            sanitized_title = sanitize_filename(card_data['stripped_title'])

                            if card_data['type_code'] == "identity":
                                # Identity card -- put at the front
                                output_name = f"00_0_back.tiff"
                                get_card_front(card_id, session, cache_path)
                                shutil.copy(back_path, output_name)
                                print(f"  {output_name}")

                                output_name = f"00_1_{sanitized_title}.tiff"
                                shutil.copy(cache_name, output_name)
                                print(f"  {output_name}")

                            else:
                                get_card_front(card_id, session, cache_path)

                                for i in range(number):
                                    output_name = f"{card_nr:02d}_0_back.tiff"
                                    shutil.copy(back_path, output_name)
                                    print(f"  {output_name}")

                                    output_name = f"{card_nr:02d}_1_{sanitized_title}.tiff"
                                    shutil.copy(cache_name, output_name)
                                    print(f"  {output_name}")
                                    card_nr += 1

                print("  Cards downloaded and converted.")

                print("  Adding QR code card.")
                output_name = f"{card_nr:02d}_0_back.tiff"
                shutil.copy(back_path, output_name)
                output_name = f"{card_nr:02d}_1_qrcode.tiff"
                create_qr_card_cmyk(decklist_url, output_name)

                tiffs_to_cmyk_pdf(".", "./deck.pdf")



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
        "-colorspace", "CMYK",             # preserve CMYK
        "-compress", "zip",                # good quality
        "-density", "300",                 # DPI for print
        f"PDF:{output_pdf}"
    ]

    print("  Running:", " ".join(command))
    subprocess.run(command, check=True)
    print(f"Saved to {output_pdf}")


def get_card_front(card_id, session, cache_path):
    nrdb_file      = f"{cache_path}/{card_id}.jpg"
    converted_file = f"{cache_path}/{card_id}.tiff"

    # print(f"https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg")
    if not os.path.exists(nrdb_file):
        print(f"  Getting https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg.")
        image_response = session.get(f"https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg")
        if image_response.status_code == 200:
            dpi     = (300, 300)
            size_in = (2.5, 3.5)
            size_px = (int(size_in[0]*dpi[0]), int(size_in[1]*dpi[1]))
       
            with open(nrdb_file, "wb") as f:
                f.write(image_response.content)
            time.sleep(3)

    if not os.path.exists(converted_file):
        print(f"  Converting {nrdb_file} to CMYK TIFF with border.")
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
        "-colorspace", "CMYK",
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

import qrcode
from PIL import Image

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
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("L")

    # === 2. Convert QR to RGBA and recolor to rich black ===
    qr_rgba = qr_img.convert("RGBA")
    pixels = qr_rgba.load()

    # Map black pixels to rich CMYK black approximation
    for y in range(qr_rgba.height):
        for x in range(qr_rgba.width):
            r, g, b, a = pixels[x, y]
            if (r, g, b) == (0, 0, 0):
                # Rich black RGB approximation (you can tweak this)
                pixels[x, y] = (30, 20, 20, 255)
            elif (r, g, b) == (255, 255, 255):
                pixels[x, y] = (255, 255, 255, 255)

    # Convert back to CMYK
    qr_cmyk = qr_rgba.convert("CMYK")

    # Resize QR to 2.0" × 2.0"
    qr_cmyk = qr_cmyk.resize((600, 600), Image.LANCZOS)

    # === 3. Create CMYK canvas ===
    canvas_size = (825, 1125)  # 2.75" × 3.75" @ 300dpi
    canvas = Image.new("CMYK", canvas_size, (0, 0, 0, 0))  # White CMYK background

    # === 4. Paste in center ===
    pos = ((canvas_size[0] - qr_cmyk.width) // 2, (canvas_size[1] - qr_cmyk.height) // 2)
    canvas.paste(qr_cmyk, pos)

    # === 5. Save ===
    canvas.save(output_path, dpi=(dpi, dpi), format="TIFF")
    print(f"Saved to {output_path}")

# Example usage


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(usage)
    else:
        main(sys.argv[1:])


