# nrproxystuff
Me hacking on a Netrunner proxy card project.

Started from Ecophagy's ANRProxyGenerator:
  https://github.com/Ecophagy/ANRProxyGenerator

That code is also MIT licensed.

conda create python=3.10 requests pillow psutil

## Card Backs
I found some online. Converted to correct format with something like this:
```
magick ./nsg-corp.png -resize 750x1050 -bordercolor black -border 38x38 -density 300 -profile ../git/ECI-RGB.V1.0.icc -profile ../git/ISOcoated_v2_eci.icc -filter Mitchell -colorspace CMYK ./nsg-corp.tiff
```
