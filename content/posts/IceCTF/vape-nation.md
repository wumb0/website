Title: IceCTF 2016 - Vape Nation
Date: 2016-08-15 19:18
Category: CTF
Tags: icectf2016, ctf, stego
Slug: icectf-2016-vape-nation
Authors: wumb0

Challenge description:
> Go Green!

They provide a png called vape_nation.png:

![vape nation]({filename}/images/icectf/vape_nation.png)

With the hint I figured it must be a green filter of some sort so I loaded up [Stegsolve](http://www.caesum.com/handbook/Stegsolve.jar) and checked out the green plane filters. Green plane 0 resulted in the following:

![solved nation]({filename}/images/icectf/solved_nation.png)

Looks like a flag :)

**IceCTF{420_CuR35_c4NCEr}**
