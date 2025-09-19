# nrproxystuff
Me hacking on a Netrunner proxy card project. Takes a deck ID from
netrunnerDB and spits out a PDF ready for submission to DriveThruCards.com.

*Or, I think it does ... waiting on my first order.*

## Details:
- Caches images in ~/nrdb-cache to speed processing of multiple lists.
- Includes an additional card with a QR code pointing to the netrunnerDB decklist, for
  reference, as well as the decklist itself.
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
This is what I did:
```
conda create python=3.10 requests pillow psutil
conda install conda-forge::ghostscript
pip install qrcode[pil]
```

## ICC Files
You need two, one for the RGB (source) colorspace and one for the CMYK (target) colorspace. Notes below, but my suggestion is to:
- Use sRGB_v4_ICC_preference.icc for source.
- Use CGATS21_CRPC1.icc for target.
- Put these in the directory above the source directory, and it'll find them.

DriveThruCards provides one for the CMYK side:
- https://help.drivethrupartners.com/hc/en-us/article_attachments/12904358770455/CGATS21_CRPC1.icc

However I found that one to result in washed out colors.

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
magick ./chatgpt-runner-back.png -resize 750x1050 -bordercolor black -border 38x38 -units PixelsPerInch -density 300 -profile ../../ECI-RGB.V1.0.icc -profile ../../CGATS21_CRPC1.icc -filter Mitchell -compress Zip ./chatgpt-runner-back.tiff
```

## Experiments

750x1050 + Mitchell + ECI-RGB.V1.0.icc + ISOcoated_v2_eci.icc -> oversaturated.
750x1050 + Lanczos + sharpen (0x0.5) + ECI-RGB.V1.0.icc + CGATS21_CRPC1.icc -> undersaturated / washed out.
749x1049 + Lanczos + sharpen (0x0.5) + sRGB_v4_ICC_preference.icc + CGATS21_CRPC1.icc -> good enough.
