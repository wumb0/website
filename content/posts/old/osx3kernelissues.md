Title: OS X^3 Kernel Issues
Date: 2014-11-03 00:23
Category: Old Posts
Tags: old
Slug: OS-X3-Kernel-Issues
Authors: wumb0

With the upgrade from Mavericks to Yosemite (pronounced Yo-sem-eye-t) came problems for me. Kernel panics every couple of hours after putting my Mac to sleep. I fear that it is my SSD that is causing the problem but I will try to fix it nonetheless. I wanted to recompile my kernel so it would be easier to debug so I patiently awaited the 10.10 source code on <a href="https://opensource.apple.com/" target="_blank">https://opensource.apple.com/</a>. When it was released I got to downloading AvailabilityVersions 9, dtrace 147, and the xnu 2782.1.97 source code. Apparently not that many people know that the OSX kernel is open source, but it is and it is pretty straight forward to compile and install (except if you are me, and then random problems come up). Regardless, here are the steps that I followed to recompile my kernel:
<ol>
	<li>Get the three packages</li>
<pre><code class="lang:shell">
curl -O https://opensource.apple.com/tarballs/AvailabilityVersions/AvailabilityVersions-9.tar.gz
curl -O https://opensource.apple.com/tarballs/dtrace/dtrace-147.tar.gz
curl -O https://opensource.apple.com/tarballs/xnu/xnu-2782.1.97.tar.gz
</code></pre>
	<li>Build ctfmerge/ctfdump/ctfconvert from dtrace</li>
<pre><code class="lang:shell">
gunzip dtrace-147.tar.gz;tar -xf dtrace-147.tar;cd dtrace-147
mkdir -p obj sym dst
xcodebuild install -target ctfconvert -target ctfdump -target ctfmerge ARCHS="x86_64" SRCROOT=$PWD OBJROOT=$PWD/obj SYMROOT=$PWD/sym DSTROOT=$PWD/dst
sudo ditto $PWD/dst/usr/local /usr/local
</code></pre>
	<li>Build AvailabilityVersions</li>
<pre><code class="lang:shell">
gunzip AvailabilityVersions-9.tar.gz;tar -xf AvailabilityVersions-9.tar;cd AvailabilityVersions-9
mkdir -p dst
make install SRCROOT=$PWD DSTROOT=$PWD/dst
sudo ditto $PWD/dst/usr/local \`xcrun -sdk / -show-sdk-path\`/usr/local
</code></pre>
	<li>Untar the kernel:</li>
<pre><code class="lang:shell">
gunzip xnu-2782.1.97.tar.gz;tar -xf xnu-2782.1.97.tar;cd xnu-2782.1.97
</code></pre>
	<li>At this point you could run make, but this is where I ran into trouble. I installed the 10.10 SDK via xCode in <em>Preferences-&gt;Downloads</em> and made sure it was installed with xcodebuild -showsdks. Everything seemed good to go, but when I ran make...
<pre><code>
make ARCH_CONFIGS=X86_64 KERNEL_CONFIGS=RELEASE
xcodebuild: error: SDK "macosx.internal" cannot be located.
xcodebuild: error: SDK "macosx.internal" cannot be located.
xcrun: error: unable to lookup item 'Path' in SDK 'macosx.internal'
...Lots more errors...
</code></pre>
The wrong SDK was being used. Whatever macosx.internal was, it wasn't working. So my solution was just to do a grep for 'macosx.internal' and replace it with 'macosx10.10':
<pre><code class="lang:shell">
grep -Rl "macosx.internal" . | while read i;do sed -i '' 's/macosx.internal/macosx10.10/' "$i";done
</code></pre>
</li>
	<li>Now we run</li> 
<pre><code class="lang:shell">
make ARCH_CONFIGS=X86_64 KERNEL_CONFIGS=RELEASE
</code></pre>
and it works just fine!
</ol>
The bare minimum kernel compilation instructions were taken from <a href="http://shantonu.blogspot.com/2013/10/building-xnu-for-os-x-109-mavericks.html" target="_blank">http://shantonu.blogspot.com/2013/10/building-xnu-for-os-x-109-mavericks.html</a>

I hope this helps anyone having the same issues recompiling their Yosemite kernels!
