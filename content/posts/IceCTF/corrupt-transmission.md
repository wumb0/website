Title: IceCTF 2016 - Corrupt Transmission
Date: 2016-08-15 19:18
Category: CTF
Tags: icectf2016 CTF forensics
Slug: icectf-2016-corrupt-transmission
Authors: wumb0

Challenge description: 
> We intercepted this image, but it must have gotten corrupted during the transmission. Can you try and fix it?

For this challenge a file with the extension .png was provided. A common CTF challenge is to corrupt some part of an image, so the solution is to fix it! I started with the header. According to [Wikipedia](https://en.wikipedia.org/wiki/Portable_Network_Graphics#File_header) the file header is supposed to start with `89 50 4E 47 0D 0A 1A 0A`. Looking at the file using xxd we can see that this png does **not** start with those bytes:
```
→ xxd corrupt_orig.png | head -1
00000000: 9050 4e47 0e1a 0a1b 0000 000d 4948 4452  .PNG........IHDR
```
The first byte and bytes 5-8 are wrong.
To fix, I opened the image up in hexedit and changed the bytes to their correct values. 
Opening the file provided a valid image:

![flag]({filename}/images/icectf/corrupt.png)

And of course, the flag: 
**IceCTF{t1s_but_4_5cr4tch}**
