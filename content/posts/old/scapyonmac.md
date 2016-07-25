Title: Scapy on Mac
Date: 2014-07-16 23:05
Category: Old Posts
Tags: old
Slug: Scapy-on-Mac
Authors: wumb0

Just a quick note here about an issue I was having getting Scapy to work with my Mac. It can be installed from MacPorts but you need to make sure the Python you are using is the MacPorts one in /opt/local/bin and not in /usr/bin. The Apple one has it's own issues and cannot see modules installed by macports. Alternatively you can just invoke Scapy from the command line by typing <strong>scapy</strong> into terminal.

Another issue I had was with bridged or vbox adapters. Scapy will throw the following error:
<blockquote>
"/opt/local/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/scapy/arch/pcapdnet.py", line 168, in get_if_raw_addr return i.get(ifname)["addr"].data File "dnet.pyx", line 990, in dnet.intf.get OSError: Device not configured</blockquote>
The error has to do with getting details about interfaces on the computer. To fix edit /opt/local/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/scapy/arch/unix.py:
```python
# from
f=os.popen("netstat -rn") # -f inet
```
```python
# to
f=os.popen("netstat -rn | grep -v vboxnet | grep -v bridge") # -f inet
```
(/opt/local/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/scapy/arch/unix.py will change based on the version you are using, replace 2.7 and python 2.7 with your version)
And that should fix everything! Happy hacking!
