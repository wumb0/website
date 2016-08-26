Title: IceCTF 2016 - Blue Monday
Date: 2016-08-15 19:18
Category: CTF
Tags: icectf2016, ctf
Slug: icectf-2016-blue-monday
Authors: wumb0

Challenge Description:
> Those who came before me lived through their vocations From the past until completion, they'll turn away no more And still I find it so hard to say what I need to say But I'm quite sure that you'll tell me just how I should feel today.
A file download was given for this challenge. Running file yielded the following result:
```
→ file blue_monday.mid
blue_monday.mid: Standard MIDI data (format 1) using 1 track at 1/220
```
Assuming it actually was MIDI, I opened it up in audacity with no luck. It was just a bunch of constant tones. This was at about 2:30AM so as a last effort before bed I just `cat`ted the file:

```
→ cat blue_monday.mid
MThdTrkId\Icd\ced\eCd\CTd\TFd\F{d\{Hd\HAd\Acd\ckd\k1d\1nd\n9d\9_d\_md\mUd\U5d\5Id\Icd\c_d\_Wd\W1d\17d\7hd\h_d\_md\mId\IDd\D1d\15d\5_d\_Ld\L3d\3td\t5d\5_d\_Hd\H4d\4vd\vEd\E_d\_ad\a_d\_rd\r4d\4vd\v3d\3}d\}h/
```
The point of interest here for me was that it looked like the beginning was spelling IceCTF{ but with extra characters in between. I loaded it up into ipython and ended up with this snippet to solve it:

```python
with open("blue_monday") as f:
    print(''.join([i for i in f.read() if ord(i)<127 and ord(i)>0x10 and i!='\\' and i !='d'])[7:][:-2][::2])
```
Basically this just removes any character that is non-ascii, a backslash, or d, and then cuts off the first 7 characters (the header) and the last 2, and then takes every other character. They had just embedded the flag into a working MIDI file it seems. Anyway, when you run this it prints the flag:
**IceCTF{HAck1n9_mU5Ic_W17h_mID15_L3t5_H4vE_a_r4v3}**
