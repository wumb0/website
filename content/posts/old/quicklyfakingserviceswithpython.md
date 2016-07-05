Title: Quickly Faking Services With Python
Date: 2014-09-30 17:36
Category: Old Posts
Tags: old
Slug: Quickly-Faking-Services-With-Python
Authors: wumb0

I was developing a port scanning exercise for RIT's Competitive Cybersecurity Club (RC3) a few weeks ago and I thought it would be neat to develop a tool to fake services on the fly. Out of this came fakesrv.py, which allows you to specify a protocol, port, and message or file to spit back when someone connects. 
<pre><code class="bash">
./fakesrv.py -t -p 1337 -m "This is a TCP server listening on port 1337!"
./fakesrv.py -u -p 12345 -m "This is a UDP server listening on port 12345!"
./fakesrv.py -t -p 31337 -f /etc/passwd
</code></pre>

Quick, easy, and fun.

Check it out: <a href="https://github.com/jgeigerm/fakesrv" title="fakesrv">https://github.com/jgeigerm/fakesrv</a>
