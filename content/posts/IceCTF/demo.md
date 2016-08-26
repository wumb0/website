Title: IceCTF 2016 - Demo
Date: 2016-08-15 19:18
Category: CTF
Tags: icectf2016 CTF
Slug: icectf-2016-demo
Authors: wumb0

Challenge description:
> I found this awesome premium shell, but my demo version just ran out... can you help me crack it? /home/demo/ on the shell. 
The source for this challenge was provided:
```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <libgen.h>
#include <string.h>

void give_shell() {
    gid_t gid = getegid();
    setresgid(gid, gid, gid);
    system("/bin/sh");
}

int main(int argc, char *argv[]) {
    if(strncmp(basename(getenv("_")), "icesh", 6) == 0){
        give_shell();
    }
    else {
        printf("I'm sorry, your free trial has ended.\n");
    }
    return 0;
}
```
So to get the flag we need to make the _ shell variable equal icesh. The _ shell variable in bash is always set to the program name of the command being run. So I decided to use a different shell to see what would happen.

```sh
sh
ls icesh; /home/demo/demo
cat flag.txt
IceCTF{wH0_WoU1d_3vr_7Ru5t_4rgV}
```

And there we have our flag:
**IceCTF{wH0_WoU1d_3vr_7Ru5t_4rgV}**
