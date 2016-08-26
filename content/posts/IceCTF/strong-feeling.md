Title: IceCTF 2016 - A Strong Feeling
Date: 2016-08-15 19:18
Category: CTF
Tags: icectf2016, ctf, reversing
Slug: icectf-2016-a-strong-feeling
Authors: wumb0

Challenge description:
> Do you think you could defeat this password checker for us? It's making me real pissed off! /home/a_strong_feeling/ on the shell or download it here

I started by loading the bin into radare2 and once I realized how big the main function was I just tried running it with input.
<script type="text/javascript" src="https://asciinema.org/a/3rj0b4rtx4gybtqwg9q1c0fp0.js" id="asciicast-3rj0b4rtx4gybtqwg9q1c0fp0" async></script>

It looks like the sentence returned is different the more characters we get right and the same if we get the same number wrong. I had the idea to write a python script with pwntools that ran the binary over and over until a different sentence was produced:
```
from pwn import *
import string
charset = string.ascii_letters + string.digits + "{}_#"
context.log_level = 'error'

flag = "I"
b = ELF("./strong_feeling")

p = process(b.path)
p.sendline(flag)
out = p.recvall()

while flag[-1] != '}':
    for c in charset:
        p = process(b.path)
        p.sendline(flag+c)
        newout = p.recvall()
        if newout != out:
            out = newout
            flag += c
            print flag
            continue
```

The results were quite satisfying:
<script type="text/javascript" src="https://asciinema.org/a/d4imjlama9reyom1iypwr46s3.js" id="asciicast-d4imjlama9reyom1iypwr46s3" async></script>

Flag acquired

**IceCTF{pip_install_angr}**

And yes I realize now that this could have just been solved with angr, but this was a cool way to do it too!
