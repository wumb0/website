Title: Anti-Debugging
Date: 2014-11-10 19:20
Category: Old Posts
Tags: old
Slug: Anti-Debugging
Authors: wumb0

I know anti-debugging and anti-reversing methods can be beaten fairly easily, but I played around with some today and thought it was worth sharing. My goal at the beginning was to be able to detect if a software breakpoint had been set (0xCC or 0xCD in memory). With a bit of searching around and figuring out different things I came up with the following code:

```c
#include <unistd.h>
#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>

extern char __executable_start;
extern char __etext;
void check_bp(){
    //Check debugger breakpoints (software)
    unsigned char bp1 = 0xCB; //We need to define the interrupt
    unsigned char bp2 = 0xCB; //codes without actually including them
    bp1++; bp2++; bp2++;

    //Point to the beginning of the .text section and then figure out the size
    unsigned char* ch = (unsigned char *)(unsigned long)&__executable_start;
    size_t size = (unsigned long)&__etext - (unsigned long)&__executable_start;

    //Scan through memory (.text) to find breakpoints :)
    for (size_t i = 0; i != size; i++){
        if (ch[i] == bp1 || ch[i] == bp2){
            printf("Breakpoint detected. @0x%lx: 0x%x\nAborting.\n", (unsigned long)&ch[i], ch[i]);
            raise(SIGSEGV);
        }
    }
}

int main(){
    check_bp();
    //do main stuff
    return 0;
}
```

The external symbol __executable_start denotes where the text section starts in Linux. The external symbol __etext denotes the end of the text section in Linux. Basically this code finds where the text section starts and the size of the text section then scans through it to look for 0xCC or 0xCD. If it finds a breakpoint then the address and hex code of the breakpoint are printed to the screen and a segfault is raised. 
This can easily be bypassed by skipping over the check_bp function in GDB, but it is still a neat proof of concept.

Other things that can help prevent debugging/reversing are checking LD_PRELOAD, checking ptrace, and obfuscating the code. The first two can be beaten by the same trick that the breakpoint finder can, but obfuscation is not as easily defeated because it just makes the code really hard to reverse. Perhaps a combination of all four things can make a safer program, or perhaps a kernel module that prohibits tracing/breakpoints from any userland program. Just thoughts.


