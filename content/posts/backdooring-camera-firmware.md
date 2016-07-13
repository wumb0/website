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
We had 9 *D-Link DCS-930L Rev. B2* cameras; eight for teams and one <s>to brick</s> for testing. We wanted to accomplish a few things:
<div><ul>
    <li>Install sshd for pivoting,</li>
    <li>Make telnetd listen and provide unauthenticated access, and</li>
    <li>Modify some pages on the web UI</li>
</ul></div>
But first we had to figure out <strong>where do we start</strong>? Our first thought was to dive right into reversing the firmware update image to try and find a filesystem to modify. We were able to download the image from the <a href="http://support.dlink.com/ProductInfo.aspx?m=DCS-930L">D-Link website</a>.
</div>

## Diving in with Binwalk
The firmware archive contains a PDF with firmware release notes and a bin file (the image). Running *binwalk* on the image yields the following:
<pre><code>
→ binwalk DCS-930L_REVB1_FW_v2.12.01.bin
DECIMAL       HEXADECIMAL     DESCRIPTION
\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-
0             0x0             uImage header, header size: 64 bytes, header CRC: 0x9678CD8, created: 2015-10-01 02:33:35, image size: 111116 bytes,
Data Address: 0x80200000, Entry Point: 0x80200000, data CRC: 0xCD95F789, OS: Linux, CPU: MIPS, image type: Standalone Program, compression type: none,
image name: "SPI Flash Image"
91040         0x163A0         U-Boot version string, "U-Boot 1.1.3"
105424        0x19BD0         HTML document header
105770        0x19D2A         HTML document footer
105780        0x19D34         HTML document header
105972        0x19DF4         HTML document footer
106140        0x19E9C         HTML document header
106833        0x1A151         HTML document footer
327680        0x50000         uImage header, header size: 64 bytes, header CRC: 0xCDBF3E85, created: 2015-10-01 02:33:29, image size: 3705182 bytes,
Data Address: 0x80000000, Entry Point: 0x8038B000, data CRC: 0xC8AFE19B, OS: Linux, CPU: MIPS, image type: OS Kernel Image, compression type: lzma,
image name: "Linux Kernel Image"
327744        0x50040         LZMA compressed data, properties: 0x5D, dictionary size: 33554432 bytes, uncompressed size: 6369023 bytes
</code></pre>
[[more]]
Looks like there are two sections of interest underneath "uImage" headers. The first section at the start of the binary seems to contain something called "U-Boot". What is U-Boot? It is a first- and second- stage bootloader that is used for embedded devices. You can read more about it on [Wikipedia](https://en.wikipedia.org/wiki/Das_U-Boot U-Boot). The other uImage is a Linux Kernel Image. Since we are looking for the filesystem, the Linux Kernel Image seems like the path to go down from here. It can be extracted with *dd*.
<pre><code>
→ dd if=DCS-930L_REVB1_FW_v2.12.01.bin of=linux.bin.lzma skip=$((0x50040)) bs=1
3866560+0 records in
3866560+0 records out
3866560 bytes (3.9 MB) copied, 5.20757 s, 742 kB/s
→ lzma -vd linux.bin.lzma
linux.bin.lzma (1/1)
 95.7 %   3,618.3 KiB / 6,219.7 KiB = 0.582                                    
lzma: linux.bin.lzma: Compressed data is corrupt
 95.7 %   3,618.3 KiB / 6,219.7 KiB = 0.582
</code></pre>
Uh oh. That's not good. We know that the magic on that section of the firmware binary indicates LZMA and because it failed at 95.7% we can look at the end of the file for issues.
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
003affb0: ffff ffff ffff ffff ffff ffff f4a4 e2e5  ................
</code></pre>
Seems like it is just padding, with 4 bytes at the end that we will get back to later.
To take off the padding we needed to find the last line of data before the "ffff"s start. This can be done using  *xxd*, *fgrep*, and *tail* .
<pre><code>
→ xxd linux.bin.lzma | fgrep -v '................' | tail
003888d0: 041f 72f2 d595 72be 18d1 7f21 97e7 4fa0  ..r...r....!..O.
003888e0: b791 4084 0d9f af4a b5e0 acb6 7b83 2c5c  ..@....J....{.,\
003888f0: 360c 955e 5640 d236 f295 8a22 49c7 a011  6..^V@.6..."I...
00388900: 3f71 1b85 1325 2020 2d4a 2653 abb1 9b2b  ?q...%  -J&S...+
00388910: a133 364a b44f 8b1d 15ab 108f b5da 5e93  .36J.O........^.
00388920: c53e 01ba 6b15 d0ea 5a27 0442 5b9f a1a2  .>..k...Z'.B[...
00388930: 882f 8ab9 68d1 42d3 a8ae e8f9 7a33 4952  ./..h.B.....z3IR
00388940: 383c 2831 803a 1603 197b c150 c33c d522  8<(1.:...{.P.<."
00388950: 34e0 0a68 e451 10eb 4a88 ccf3 4600 ffff  4..h.Q..J...F...
003affb0: ffff ffff ffff ffff ffff ffff f4a4 e2e5  ................
</code></pre>
The last line is the same as the previous dump, so we ignore it. We see above that the lines of all "ffff"s start at 0x388950+14. We plug this number into *dd* as the count to copy and try the decompression again.

<pre><code>
→ dd if=DCS-930L_REVB1_FW_v2.12.01.bin of=linux.bin.lzma skip=$((0x50040)) count=$((0x388950+14)) bs=1
3705182+0 records in
3705182+0 records out
3705182 bytes (3.7 MB) copied, 5.01361 s, 739 kB/s
→ lzma -vd linux.bin.lzma
linux.bin.lzma (1/1)
  100 %   3,618.3 KiB / 6,219.7 KiB = 0.582
</code></pre>
Success! The next logical step is to check out the newly extracted linux.bin with *binwalk*.

<pre><code>
→ binwalk linux.bin
DECIMAL       HEXADECIMAL     DESCRIPTION
--------------------------------------------------------------------------------
1108304       0x10E950        LZMA compressed data, properties: 0xC0, dictionary size: 16777216 bytes, uncompressed size: 525370 bytes
3256396       0x31B04C        Linux kernel version "2.6.21 (andy@ipcam-linux.alphanetworks.com) (gcc version 3.4.2) #385 Thu Oct 1 10:33:24 CST 2015"
3257408       0x31B440        CRC32 polynomial table, little endian
3285504       0x322200        SHA256 hash constants, little endian
3350344       0x331F48        Copyright string: "Copyright (c) 2010 Alpha Networks Inc."
...
3449422       0x34A24E        Unix path: /net/wireless/rt2860v2_sta/../rt2860v2/common/wsc.c:%d assert pWscPeer != NULLfailed
3453470       0x34B21E        Unix path: /net/wireless/rt2860v2_sta/../rt2860v2/common/wsc_v2.c:%d assert pEntry!=NULLfailed
3514907       0x35A21B        Neighborly text, "neighbor %.2x%.2x.%.2x:%.2x:%.2x:%.2x:%.2x:%.2x lost on port %d(%s)(%s)"
3637728       0x3781E0        CRC32 polynomial table, little endian
3850240       0x3AC000        LZMA compressed data, properties: 0x5D, dictionary size: 1048576 bytes, uncompressed size: 8126976 bytes
</code></pre>

Quite a few entries. Grepping out the word "path" yields less.

<pre><code>
→ binwalk linux.bin | grep -v path
DECIMAL       HEXADECIMAL     DESCRIPTION
--------------------------------------------------------------------------------
1108304       0x10E950        LZMA compressed data, properties: 0xC0, dictionary size: 16777216 bytes, uncompressed size: 525370 bytes
3256396       0x31B04C        Linux kernel version "2.6.21 (andy@ipcam-linux.alphanetworks.com) (gcc version 3.4.2) #385 Thu Oct 1 10:33:24 CST 2015"
3257408       0x31B440        CRC32 polynomial table, little endian
3285504       0x322200        SHA256 hash constants, little endian
3350344       0x331F48        Copyright string: "Copyright (c) 2010 Alpha Networks Inc."
3514907       0x35A21B        Neighborly text, "neighbor %.2x%.2x.%.2x:%.2x:%.2x:%.2x:%.2x:%.2x lost on port %d(%s)(%s)"
3637728       0x3781E0        CRC32 polynomial table, little endian
3850240       0x3AC000        LZMA compressed data, properties: 0x5D, dictionary size: 1048576 bytes, uncompressed size: 8126976 bytes
</code></pre>

Two LZMA compressed sections! We then extracted them from the binary and attempted decompression.
<pre><code>
→ dd if=linux.bin of=linux1.bin.lzma bs=1 skip=1108304 count=$((3256396-1108304))
2148092+0 records in
2148092+0 records out
2148092 bytes transferred in 3.627930 secs (592099 bytes/sec)
→ dd if=linux.bin of=linux2.bin.lzma bs=1 skip=3850240
2518783+0 records in
2518783+0 records out
2518783 bytes transferred in 4.272323 secs (589558 bytes/sec)
→ lzma -vd linux1.bin.lzma
linux1.bin.lzma (1/1)
lzma: linux1.bin.lzma: Compressed data is corrupt
→ lzma -vd linux2.bin.lzma
linux2.bin.lzma (1/1)
  100 %   2,459.7 KiB / 7,936.5 KiB = 0.310
</code></pre>

It doesn't seem like the *lzma* utility even attempted to extract the contents of linux1.bin.lzma. Better luck was had with linux2.bin.lzma, so we went down this path further.

Running *binwalk* against the newly extracted binary yields the following:
<pre><code>
→ binwalk linux2.bin
DECIMAL       HEXADECIMAL     DESCRIPTION
\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-
0             0x0             ASCII cpio archive (SVR4 with no CRC), file name: "/bin", file name length: "0x00000005", file size: "0x00000000"
116           0x74            ASCII cpio archive (SVR4 with no CRC), file name: "/bin/chmod", file name length: "0x0000000B", file size: "0x00000008"
248           0xF8            ASCII cpio archive (SVR4 with no CRC), file name: "/bin/busybox", file name length: "0x0000000D", file size: "0x00056100"
372           0x174           ELF, 32-bit LSB MIPS-II executable, MIPS, version 1 (SYSV)
...
6684188       0x65FE1C        ASCII cpio archive (SVR4 with no CRC), file name: "/etc_ro/servercert.pem", file name length: "0x00000017", file size: "0x00000487"
6685484       0x66032C        ASCII cpio archive (SVR4 with no CRC), file name: "/etc_ro/serverkey.pem", file name length: "0x00000016", file size: "0x00000377"
...
8126464       0x7C0000        ASCII cpio archive (SVR4 with no CRC), file name: "/usr/sbin/telnetd", file name length: "0x00000012", file size: "0x00000012"
8126612       0x7C0094        ASCII cpio archive (SVR4 with no CRC), file name: "/proc", file name length: "0x00000006", file size: "0x00000000"
8126728       0x7C0108        ASCII cpio archive (SVR4 with no CRC), file name: "TRAILER!!!", file name length: "0x0000000B", file size: "0x00000000"
</pre></code>
Lots of CPIO archive data here. It turns out that it's just a single CPIO! This certainly looks promising because there are Linux filesystem paths in the output. We extracted it using the *cpio* utility. (the Mac version of *cpio* does not come with the *--no-absolute-filenames* option, so this was done on Linux)

<pre><code>
$ mkdir extract && mv linux2.bin $\_ && cd $\_
$ cpio -i --no-absolute-filenames < linux2.bin
cpio: Removing leading `/' from member names
15873 blocks
$ ls
bin  etc     home  lib         media  mydlink  sbin  tmp  var
dev  etc_ro  init  linux2.bin  mnt    proc     sys   usr
</pre></code>
Jackpot! Looks like a valid Linux filesystem!
<img width="300px" class="uk-align-center" src="/images/money.gif" />

## Examining the filesystem
Before extracting the firmware we connected the camera like a normal user would to a network and tried gaining access via the web interface. D-Link did a decent job sanitizing input boxes to make sure we weren't able to pass linux commands straight to the command line. We found that the web application lived in */etc_ro* which we assumed was a read only folder based on the name. After a while of poking and prodding the web app we thought "We have physical access, why not just make malware?" So that's what we did. Now comes the fun part of dissecting filesystem. Lets take a look at some of these folders we just extracted.

Since the web app runs in */etc_ro* lets look there first.
<pre><code>
/etc_ro
  \-rw\-r\-\-r\-\- 1 501 501 15086 Jul 12 21:36 icon.large.ico
  \-rw\-r\-\-r\-\- 1 501 501    45 Jul 12 21:36 inittab
  drwxrwxr\-x 2 501 501  4096 Jul 12 21:36 linuxigd
  \-rw\-r\-\-r\-\- 1 501 501    79 Jul 12 21:36 lld2d.conf
  \-rw\-r\-\-r\-\- 1 501 501   326 Jul 12 21:36 motd
  \-rw\-r\-\-r\-\- 1 501 501  9373 Jul 12 21:36 openssl.cnf
  drwxrwxr\-x 5 501 501  4096 Jul 12 21:36 ppp
  \-rwxr\-xr\-x 1 501 501  1626 Jul 12 21:36 rcS
  \-rw\-r\-\-r\-\- 1 501 501  1159 Jul 12 21:36 servercert.pem
  \-rw\-r\-\-r\-\- 1 501 501   887 Jul 12 21:36 serverkey.pem
  drwxrwxr-x 2 501 501  4096 Jul 12 21:36 usb
  drwxrwxr-x 5 501 501  4096 Jul 12 21:36 web
  drwxrwxr-x 5 501 501  4096 Jul 12 21:36 Wireless
  drwxrwxr-x 2 501 501  4096 Jul 12 21:36 wlan
  drwxrwxr-x 2 501 501  4096 Jul 12 21:36 xml
</code></pre>

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
