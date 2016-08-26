Title: IceCTF 2016 - Thor is a hacker now
Date: 2016-08-15 19:18
Category: CTF
Tags: icectf2016, ctf
Slug: icectf-2016-thor-is-a-hacker-now
Authors: wumb0

Challenge description:
> Thor has been staring at this for hours and he can't make any sense out of it, can you help him figure out what it is?

The text file provided is just a hexdump produced with xxd. xxd actually has a feature to reverse a hexdump back into the original file, from there I identified the resulting file's format with the file command. It was an lzip. Extracting the lzip resulted in the following image:

![thor]({filename}/images/icectf/thor.jpg)

Flag: 

**IceCTF{h3XduMp1N9_l1K3_A_r341_B14Ckh47}**

Commands that were run in order:

```bash
→ xxd -r thor.txt > thor.bin
→ file thor.bin
thor.bin: lzip compressed data, version: 1
lzip -d thor.bin
→ file thor.bin.out
thor.bin.out: JPEG image data, JFIF standard 1.01
→ mv thor.bin.out thor.jpg
```
