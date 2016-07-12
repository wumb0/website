Title: Reversing and Backdooring IP Camera Firmware
Date: 2016-07-11 21:50
Category: Reversing
Tags: camera, firmware, binwalk, reversing
Slug: reversing-and-backdooring-ip-camera-firmware
Status: draft
Authors: wumb0

RIT's Competitive Cybersecurity Club (*RC3*) held it's 2nd annual Incident Response Security Competition (*IRSeC*) in May and I once again had the privilege to be on both the red and white teams! This year we had IP cameras to play with, so one of my buddies on the white team and I decided to try to mess with the firmware. 

<div class="uk-clearfix">
<img width="300px" class="uk-align-medium-right" src="/images/dlink-front.jpg" />
<img width="300px" class="uk-align-medium-right" src="/images/dlink-back.jpg" />
We had 9 *D-Link DCS-930L Rev. A* cameras; eight for teams and one <s>to brick</s> for testing. We wanted to accomplish a few things: 
<div><ul>
    <li>Install sshd for pivoting,</li>
    <li>Make telnetd listen and provide unauthenticated access, and</li>
    <li>Modify some pages on the web UI</li>
</ul></div>
But first we had to figure out <strong>where do we start</strong>? Our first thought was to dive right into reversing the firmware update image to try and find a filesystem to modify. We were able to download the image from the <a href="http://support.dlink.com/ProductInfo.aspx?m=DCS-930L">D-Link website</a>.
</div>

## Diving in with Binwalk
After unzipping the downloaded file there is a PDF with firmware release notes and a bin file (the image). Running *binwalk* on the image yields the following:
<pre><code>
→ binwalk dcs930l_v1.14.02.bin
DECIMAL       HEXADECIMAL     DESCRIPTION
\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-
106352        0x19F70         U-Boot version string, "U-Boot 1.1.3"
106816        0x1A140         CRC32 polynomial table, little endian
124544        0x1E680         HTML document header
124890        0x1E7DA         HTML document footer
124900        0x1E7E4         HTML document header
125092        0x1E8A4         HTML document footer
125260        0x1E94C         HTML document header
125953        0x1EC01         HTML document footer
327680        0x50000         uImage header, header size: 64 bytes, header CRC: 0x18734A1, created: 2015-10-06 10:09:23, 
                              image size: 3745900 bytes, Data Address: 0x80000000, Entry Point: 0x803B8000, 
                              data CRC: 0xFBA580C6, OS: Linux, CPU: MIPS, image type: OS Kernel Image, compression type: lzma, 
                              image name: "Linux Kernel Image"
327744        0x50040         LZMA compressed data, properties: 0x5D, dictionary size: 33554432 bytes, uncompressed size: 6500922 bytes
</code></pre>
[[more]]
Looks like there is a Linux Kernel image at 0x50040 underneath a "U-Boot" header. What is U-Boot? It is a first- and second- stage bootloader that is used for embedded devices. You can read more about it at [Wikipedia](https://en.wikipedia.org/wiki/Das_U-Boot U-Boot). All of the other entries were boring, so we used *dd* to extract the LZMA compressed data. 
<pre><code>
→ dd if=dcs930l_v1.14.02.bin of=linux.bin.lzma skip=$((0x50040)) bs=1
3866560+0 records in
3866560+0 records out
3866560 bytes transferred in 6.389888 secs (605106 bytes/sec)
→ lzma -vd linux.bin.lzma
linux.bin.lzma (1/1)
  96.8 %   3,658.1 KiB / 6,348.6 KiB = 0.576
 lzma: linux.bin.lzma: Compressed data is corrupt
  96.8 %   3,658.1 KiB / 6,348.6 KiB = 0.576
</code></pre>
Uh oh. That's not good. We knew that the magic on that section of the firmware binary indicated LZMA, so we looked at the end of the file for issues, because it failed at 96.8%.
<pre><code>
003aff20: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003aff30: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003aff40: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003aff50: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003aff60: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003aff70: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003aff80: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003aff90: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003affa0: ffff ffff ffff ffff ffff ffff ffff ffff  ................
003affb0: ffff ffff ffff ffff ffff ffff 216a ad36  ............!j.6
</code></pre>
Seems like it was just padding, with 4 bytes at the end that we will get back to later.
To take off the padding we used *xxd*, *fgrep*, and *tail* to find the last line of data before the "ffff"s started
<pre><code>
→ xxd linux.bin.lzma | fgrep -v '................' | tail
003927e0: c3c6 f0e7 d906 8bfa b487 3754 766e 8bcd  ..........7Tvn..
003927f0: 9155 93b1 7c9a 585c b1c9 c6f1 afac 6b7c  .U..|.X\......k|
00392800: c499 123d 5dde d313 9ccf a5ce ee2c 17aa  ...=]........,..
00392810: 6fef 44b9 1152 d912 1d22 a8f4 d26b 7552  o.D..R..."...kuR
00392820: 1c52 7a04 bce8 6f3f 67cc a9a4 5b08 156a  .Rz...o?g...[..j
00392830: 4a05 f0f6 7e63 5dff 4b6d 1cab bd70 19f6  J...~c].Km...p..
00392840: 1288 3f3a dc47 8d6e d1ea a8f6 b4ac 4d01  ..?:.G.n......M.
00392850: a8c6 e24e f1f0 1782 f6c4 6edb 7127 ba5a  ...N......n.q'.Z
00392860: 329f 0a77 54af 0ff7 6a8e 2d25 ffff ffff  2..wT...j.-%....
003affb0: ffff ffff ffff ffff ffff ffff 216a ad36  ............!j.6
</code></pre>
The last line is the same as the previous dump, so we ignored it. So we found that the lines of all "ffff"s started at 0x00392860 + 12. We plugged this number into *dd* as the count to copy and tried the decompression again.

<pre><code>
→ dd if=dcs930l_v1.14.02.bin of=linux.bin.lzma skip=$((0x50040)) count=$((0x392860+12)) bs=1
3745900+0 records in
3745900+0 records out
3745900 bytes transferred in 6.032942 secs (620908 bytes/sec)
→ lzma -vd linux.bin.lzma
linux.bin.lzma (1/1)
  100 %   3,658.1 KiB / 6,348.6 KiB = 0.576
</code></pre>
Success. The next logical step was to check out the newly extracted linux.bin with *binwalk*.

<pre><code>
→ binwalk linux.bin
DECIMAL       HEXADECIMAL     DESCRIPTION
--------------------------------------------------------------------------------
747977        0xB69C9         LZMA compressed data, properties: 0x88, dictionary size: 1048576 bytes, uncompressed size: 4608 bytes
3145804       0x30004C        Linux kernel version "2.6.21 (andy@ipcam-linux.alphanetworks.com) (gcc version 3.4.2) #3011 Tue Oct 6 18:09:10 CST 2015"
3175792       0x307570        SHA256 hash constants, little endian
3408212       0x340154        Copyright string: "Copyright (c) 2010 Alpha Networks Inc."
...
3483802       0x35289A        Unix path: /net/wireless/rt2860v2_sta/../rt2860v2/os/linux/rt_ate.c:%d assert (BbpValue == 0x00)failed
3483906       0x352902        Unix path: /net/wireless/rt2860v2_sta/../rt2860v2/os/linux/rt_ate.c:%d assert (BbpValue == 0x04)failed
3485590       0x352F96        Unix path: /net/wireless/rt2860v2_sta/../rt2860v2/os/linux/rt_ate.c:%d assert bbp_data == valuefailed
3486542       0x35334E        Unix path: /net/wireless/rt2860v2_sta/../rt2860v2/os/linux/rt_ate.c:%d assert pRaCfg != NULLfailed
3486906       0x3534BA        Unix path: /net/wireless/rt2860v2_sta/../rt2860v2/os/linux/rt_pci_rbus.c:%d assert pAdfailed
3491316       0x3545F4        Unix path: /etc/Wireless/RT2860STA/RT2860STA.dat
3572967       0x3684E7        Neighborly text, "neighbor %.2x%.2x.%.2x:%.2x:%.2x:%.2x:%.2x:%.2x lost on port %d(%s)(%s)"
3807776       0x3A1A20        CRC32 polynomial table, little endian
4038656       0x3DA000        LZMA compressed data, properties: 0x5D, dictionary size: 1048576 bytes, uncompressed size: 7852544 bytes
</code></pre>

Quite a few entries. Grepping out the word "path" yielded less.

<pre><code>
→ binwalk linux.bin | grep -v path
DECIMAL       HEXADECIMAL     DESCRIPTION
--------------------------------------------------------------------------------
747977        0xB69C9         LZMA compressed data, properties: 0x88, dictionary size: 1048576 bytes, uncompressed size: 4608 bytes
3145804       0x30004C        Linux kernel version "2.6.21 (andy@ipcam-linux.alphanetworks.com) (gcc version 3.4.2) #3011 Tue Oct 6 18:09:10 CST 2015"
3175792       0x307570        SHA256 hash constants, little endian
3408212       0x340154        Copyright string: "Copyright (c) 2010 Alpha Networks Inc."
3572967       0x3684E7        Neighborly text, "neighbor %.2x%.2x.%.2x:%.2x:%.2x:%.2x:%.2x:%.2x lost on port %d(%s)(%s)"
3807776       0x3A1A20        CRC32 polynomial table, little endian
4038656       0x3DA000        LZMA compressed data, properties: 0x5D, dictionary size: 1048576 bytes, uncompressed size: 7852544 bytes
</code></pre>

Two LZMA compressed sections! We extracted them both with dd and tried decompressing.
<pre><code>
→ dd if=linux.bin of=linux1.bin.lzma bs=1 skip=747977 count=$((3145804-747977))
2397827+0 records in
2397827+0 records out
2397827 bytes transferred in 3.856383 secs (621781 bytes/sec)
→ dd if=linux.bin of=linux2.bin.lzma bs=1 skip=4038656
2462266+0 records in
2462266+0 records out
2462266 bytes transferred in 4.002699 secs (615151 bytes/sec)
→ lzma -vd linux1.bin.lzma
linux1.bin.lzma (1/1)
lzma: linux1.bin.lzma: Compressed data is corrupt
→ lzma -vd linux2.bin.lzma
linux2.bin.lzma (1/1)
  100 %   2,404.6 KiB / 7,668.5 KiB = 0.314
</code></pre>

It didn't even seem like the *lzma* utility tried to extract the contents of linux1.bin.lzma. Better luck was had with linux2.bin.lzma, so we went down this path further. 

Running *binwalk* against the new binary yielded the following:
<pre><code>
DECIMAL       HEXADECIMAL     DESCRIPTION
\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-
0             0x0             ASCII cpio archive (SVR4 with no CRC), file name: "/bin", file name length: "0x00000005", file size: "0x00000000"
116           0x74            ASCII cpio archive (SVR4 with no CRC), file name: "/bin/chmod", file name length: "0x0000000B", file size: "0x00000008"
248           0xF8            ASCII cpio archive (SVR4 with no CRC), file name: "/bin/busybox", file name length: "0x0000000D", file size: "0x00067224"
372           0x174           ELF, 32-bit LSB MIPS-II executable, MIPS, version 1 (SYSV)
...
7851756       0x77CEEC        ASCII cpio archive (SVR4 with no CRC), file name: "/usr/sbin/telnetd", file name length: "0x00000012", file size: "0x00000012"
7851904       0x77CF80        ASCII cpio archive (SVR4 with no CRC), file name: "/proc", file name length: "0x00000006", file size: "0x00000000"
7852020       0x77CFF4        ASCII cpio archive (SVR4 with no CRC), file name: "TRAILER!!!", file name length: "0x0000000B", file size: "0x00000000"
</pre></code>
Lots of CPIO archive data here. It turns out that it's just a single CPIO! This certainly looks promising because there are Linux filesystem paths in the output. So we extracted it using the *cpio* utility. (the Mac version of *cpio* does not come with the *--no-absolute-filenames* option, so this was done on Linux)

<pre><code>
$ cpio -i --no-absolute-filenames < linux2.bin
cpio: Removing leading `/' from member names
cpio: dev/mtd3: Cannot mknod: Operation not permitted
cpio: dev/ttyS1: Cannot mknod: Operation not permitted
cpio: dev/swnat0: Cannot mknod: Operation not permitted
cpio: dev/mem: Cannot mknod: Operation not permitted
cpio: dev/mtd1ro: Cannot mknod: Operation not permitted
...
cpio: dev/hwnat0: Cannot mknod: Operation not permitted
cpio: dev/mtd4: Cannot mknod: Operation not permitted
cpio: dev/mtd0ro: Cannot mknod: Operation not permitted
cpio: dev/rdm0: Cannot mknod: Operation not permitted
cpio: dev/gpio: Cannot mknod: Operation not permitted
15337 blocks
$ ls
bin                   etc     init             linux2.bin  mnt      sbin  usr
dcs930l_v1.14.02.bin  etc_ro  lib              linux.bin   mydlink  sys   var
dev                   home    linux1.bin.lzma  media       proc     tmp
</pre></code>
Jackpot! Looks like a valid Linux filesystem!

## Examining the filesystem

## Trying to re-pack the firmware

## Getting the source

## Issues compiling

## Issues flashing

## Backdooring telnetd

## Installing sshd

## Installing <s>sshd</s> dropbear

## Making space

## Missing web front-end

## Results
