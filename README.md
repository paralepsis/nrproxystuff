# nrproxystuff
Me hacking on a Netrunner proxy card project. Takes a deck ID from
netrunnerDB and spits out a PDF ready for submission to DriveThruCards.com.

*Or, I think it does ... waiting on my first order.*

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
Found here:
- https://www.eci.org/doku.php?id=en:downloads
- You want ecirgbv10.zip and ecu_offset_2009.zip.
- From those you can grab ECI-RGB.V1.0.icc and ISOcoated_v2_eci.icc (respectively).

## Card Backs
There are some card backs provided. I generated them with ChatGPT5. The corp back uses an image found here:
  https://www.clipartmax.com/middle/m2i8A0Z5m2N4A0A0_company-corporation-factory-icon-company-corporation-factory-icon/

It's free for personal use.

Converted to correct format with something like this:
```
magick ./chatgpt-corp.png -resize 750x1050 -bordercolor black -border 38x38
-units PixelsPerInch -density 300 -profile ../../ECI-RGB.V1.0.icc
-profile ../../ISOcoated_v2_eci.icc -filter Mitchell -compress Zip
./chatgpt-corp.tiff
```
