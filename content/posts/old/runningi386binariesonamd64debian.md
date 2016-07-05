Title: Running i386 Binaries on amd64 Debian
Date: 2014-07-31 18:24
Category: Old Posts
Tags: old
Slug: Running-i386-Binaries-on-amd64-Debian
Authors: wumb0

I ran into this recently and thought it was worth a post. During the Pwnium CTF I was trying to run some of the programs on my Kali VM/partition, which is an amd64 install. Unfortunately the binaries were for the i386 architecture. I did a quick search and all I could find was to run <strong>dpkg --add-architecture i386</strong> and <strong>install ia32-libs</strong>.

. This doesn't play very nice with Kali and requires about 800MB of extra packages. Not so great. So I was searching around again today as I was upgrading Kali to 1.1.8 and found the better answer:
<pre><code class="bash">
dpkg --add-architecture i386
apt-get update
apt-get install libc6:i386
</code></pre>

After I did that i386 programs would run. The best part, though: only 11MB. Big improvement, same result.
Neat.

ref: <a href="http://stackoverflow.com/questions/20032019/to-install-ia32-libs-on-debian-wheezy-amd64">http://stackoverflow.com/questions/20032019/to-install-ia32-libs-on-debian-wheezy-amd64</a>
