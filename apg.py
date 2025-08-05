import requests
import shutil
import psutil
import os
from PIL import Image
from io import BytesIO
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
                    #card_picture = session.get("http://netrunnerdb.com/card_image/" + card_id + ".png")
                    with session.get(f"http://netrunnerdb.com/api/2.0/public/card/{card_id}") as card_response:
                        # print_memory_usage()
                        if card_response.status_code == 200:
                            card_json = card_response.json()
                            card_data = card_json['data'][0]
                            cache_name  = f"{cache_path}/{card_id}.tiff"
                            # print(card_data)
                            print(f"{number} x {card_data['stripped_title']} ({card_data['type_code']})")
                            sanitized_title = sanitize_filename(card_data['stripped_title'])
                            time.sleep(3)

                            if card_data['type_code'] == "identity":
                                # Identity card -- put at the front
                                output_name = f"00_back.tiff"
                                get_card_front(card_id, session, cache_path)
                                shutil.copy(back_path, output_name)
                                print(f"  {output_name}")

                                output_name = f"00_{sanitized_title}.tiff"
                                shutil.copy(cache_name, output_name)
                                print(f"  {output_name}")

                            else:
                                output_name = f"{card_nr:02d}_{0}_back.tiff"
                                get_card_front(card_id, session, cache_path)

                                for i in range(number):
                                    output_name = f"{card_nr:02d}_{i}_back.tiff"
                                    shutil.copy(back_path, output_name)
                                    print(f"  {output_name}")

                                    output_name = f"{card_nr:02d}_{i}_{sanitized_title}.tiff"
                                    shutil.copy(cache_name, output_name)
                                    print(f"  {output_name}")
                                    card_nr += 1

                    time.sleep(3)


                return
            else:
                print("Error: Could not retrieve decklist")

    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(usage)
        sys.exit(2)

def get_card_front(card_id, session, cache_path):
    nrdb_file      = f"{cache_path}/{card_id}.jpg"
    converted_file = f"{cache_path}/{card_id}.tiff"

    # print(f"https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg")
    if not os.path.exists(nrdb_file):
        print(f"  Getting https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg")
        image_response = session.get(f"https://card-images.netrunnerdb.com/v2/large/{card_id}.jpg")
        if image_response.status_code == 200:
            dpi     = (300, 300)
            size_in = (2.5, 3.5)
            size_px = (int(size_in[0]*dpi[0]), int(size_in[1]*dpi[1]))
       
            with open(nrdb_file, "wb") as f:
                f.write(image_response.content)

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

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(usage)
    else:
        main(sys.argv[1:])


