# nrproxystuff
Me hacking on a Netrunner proxy card project. Takes a deck ID from
netrunnerDB and spits out a PDF ready for submission to DriveThruCards.com.

US poker is the target size.

I've done a few runs of this now. Color and saturation are good (not identical), clarity is good (could be clearer), but my assessment is "totally usable". 

## Details:
- Caches images in ~/nrdb-cache to speed processing of multiple lists.
- Includes an additional card with a QR code pointing to the netrunnerDB decklist, for
  reference, as well as the decklist itself.
- Can also take a local JSON deck file via `--json`; if no `source_url` is present in the JSON,
  the decklist card is printed on both sides instead of generating a QR card.
- By default uses some unencumbered card backs I generated, but it's easy to pick your own.
- Uses ImageMagick for conversion to TIFF format, addition of black border, and CMYK format.
- Uses GhostScript to deduplicate the PDF, shrinking a good bit.
- There's an option to include a QR code on every card, linking to the netrunnerDB page, but
  it's not fully baked.
- Correctly handles 1-sided and 2-sided identities, simply printing 1-sided versions on both
  sides of the card.

## Shout out
I started from Ecophagy's ANRProxyGenerator:
  https://github.com/Ecophagy/ANRProxyGenerator

That code is also MIT licensed. There isn't a lot of it left, here.

## Environment
The checked-in environment definition lives in `./environment.yml`.

Create the environment with:
```
conda env create -f ./environment.yml
conda activate nrproxystuff
```

Or manually, this is what I originally did:
```
conda create python=3.10 requests pillow psutil
conda install conda-forge::ghostscript
pip install qrcode[pil]
```

ImageMagick needs LCMS support enabled for ICC profile conversion to work correctly. If you see warnings like:
```
magick: delegate library support not built-in ... (LCMS)
```
then the profile conversion is not actually happening. A quick check is:
```
magick -list configure
```

You want to see `lcms` in the delegates list, and you do not want a build configured with `--with-lcms=no`.

## JSON Input
You can provide a deck by netrunnerDB decklist ID or by local JSON:
```
python apg.py -d d71397b7-af7b-475c-8984-18360a64f6ee
python apg.py --json ./examples/d71397b7-af7b-475c-8984-18360a64f6ee.json
```

The minimal JSON shape is:
```
{
  "cards": [
    {
      "count": 3,
      "card_id": "30030"
    }
  ]
}
```

Optional fields:
- `name`: used for logs and output naming.
- `source_url`: used for the QR card on the back of the decklist/reference card.
- `cards[].name`: just for readability in the source file; card metadata still comes from `card_id`.

If `source_url` is omitted, the tool duplicates the decklist card on both sides instead of generating a QR card.

## ICC Files
You need two, one for the RGB (source) colorspace and one for the CMYK (target) colorspace. Notes below, but my suggestion is to:
- Use sRGB_v4_ICC_preference.icc for source.
- Use CGATS21_CRPC1.icc for target.
- Put these in the directory above the source directory, and it'll find them.

DriveThruCards provides one for the CMYK side:
- https://help.drivethrupartners.com/hc/en-us/article_attachments/12904358770455/CGATS21_CRPC1.icc

I've tried other options, it seems to work best.

Previously I had tried ISOcoated_v2_eci.icc from eci_offset_2009.zip, which can be found here:
- https://www.eci.org/doku.php?id=en:downloads

That version seems to be oversaturated (it's 330% TAC).
I'm going to try ISOcoated_v2_300_eci.icc next (300% TAC).

This [Reddit post](https://www.reddit.com/r/mpcproxies/comments/1axn285/updated_drivethrucards_guide/)
suggests that maybe sRGB_v4_ICC_preference.icc is the best to use
on the RGB side of things, which can be found here:
- https://www.color.org/srgbprofiles.xalter#v4pref

ChatGPT5 says that I'm better off with the ECI-RGB.V1.0.icc, found in ecirgbv10.zip here:
- https://www.eci.org/doku.php?id=en:downloads

## Card Backs
There are some card backs provided. I generated them with ChatGPT5. The corp back uses an image found here:
-  https://www.clipartmax.com/middle/m2i8A0Z5m2N4A0A0_company-corporation-factory-icon-company-corporation-factory-icon/

It's free for personal use.

Converted to correct format with something like this:
```
magick ./backs/chatgpt-corp-back.png -resize 785x1100^ -gravity center -background black -extent 825x1125 -units PixelsPerInch -density 300 -profile ../ECI-RGB.V1.0.icc -profile ../CGATS21_CRPC1.icc -filter Mitchell -compress Zip ./chatgpt-corp-back.tiff
```

## Experiments

- 750x1050 + Mitchell + ECI-RGB.V1.0.icc + ISOcoated_v2_eci.icc -> oversaturated.
- 750x1050 + Lanczos + sharpen (0x0.5) + ECI-RGB.V1.0.icc + CGATS21_CRPC1.icc -> undersaturated / washed out.
- 749x1049 + Lanczos + sharpen (0x0.5) + sRGB_v4_ICC_preference.icc + CGATS21_CRPC1.icc -> good enough.
