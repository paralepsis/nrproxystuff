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
pip install qrcode[pil]
```

## ICC Files
Found here:
- https://www.eci.org/doku.php?id=en:downloads
- You want ecirgbv10.zip and ecu_offset_2009.zip.
- From those you can grab ECI-RGB.V1.0.icc and ISOcoated_v2_eci.icc (respectively).

## Card Backs
I found some online. Converted to correct format with something like this:
```
magick ./nsg-corp.png -resize 750x1050 -bordercolor black -border 38x38 -units PixelsPerInch \
   -density 300 -profile ../git/ECI-RGB.V1.0.icc -profile ../git/ISOcoated_v2_eci.icc \
   -filter Mitchell -colorspace CMYK ./nsg-corp.tiff
```
