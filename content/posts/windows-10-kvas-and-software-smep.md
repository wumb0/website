Title: Windows 10 KVAS and Software SMEP  
Date: 2020-11-14 20:32  
Category: System Internals  
Tags: windows windows-internals  
Slug: windows-10-kvas-and-software-smep  
Authors: wumb0  
Status: draft   

Kernel Virtual Address Shadow (KVAS) is the Windows implementation of Kernel Page Table Isolation (KPTI). It was introduced to mitigate the [Meltdown](https://meltdownattack.com/meltdown.pdf) vulnerability, which allowed an attacker that could execute code in user mode to leak out data from the kernel by abusing a side channel. While there are plenty of papers and blog posts on Meltdown and KVAS, there isn't much info on an interesting feature that KVAS enables: software SMEP. Unfortunately or fortunately, depending on your interest level in this post and Windows internals, understanding how software SMEP works requires knowlege of x86\_64 paging, regular SMEP, and KVAS, so I'll be getting into those topics enough to give you an understanding of the underlying technology. Near the end I'll be running some experiments to show the internals of what I covered in the technical sections prior.  

# x64 Paging on Windows
First, I'm going to dive into a short introduction to x86\_64 (4-level) paging, the structures involved, and WinDbg commands to interact with the page hierarchy, just so the experiments later on are more understandable; plus a lot of this information is almost never presented together, so I think collecting it in a *here's what you need to know* format is useful. If you want more info consult the Intel manuals or check out [Connor McGarr's blog](https://connormcgarr.github.io/paging/). Connor does a great job of explaining the basics, so you may want to read his post over before continuing here if you don't already have at least a vague understanding of multi-level paging.  

[[more]]

## \_MMPTE\_HARDWARE
The structure that represents a page table entry on x86\_64 is `nt!_MMPTE_HARDWARE`. It is an 8 byte structure with a lot of information:  
<pre><code class="plaintext">0: kd> dt -v nt!_MMPTE_HARDWARE
struct _MMPTE_HARDWARE, 18 elements, 0x8 bytes
   +0x000 Valid               : Bitfield Pos 0, 1 Bit
   +0x000 Dirty1              : Bitfield Pos 1, 1 Bit
   +0x000 Owner               : Bitfield Pos 2, 1 Bit
   +0x000 WriteThrough        : Bitfield Pos 3, 1 Bit
   +0x000 CacheDisable        : Bitfield Pos 4, 1 Bit
   +0x000 Accessed            : Bitfield Pos 5, 1 Bit
   +0x000 Dirty               : Bitfield Pos 6, 1 Bit
   +0x000 LargePage           : Bitfield Pos 7, 1 Bit
   +0x000 Global              : Bitfield Pos 8, 1 Bit
   +0x000 CopyOnWrite         : Bitfield Pos 9, 1 Bit
   +0x000 Unused              : Bitfield Pos 10, 1 Bit
   +0x000 Write               : Bitfield Pos 11, 1 Bit
   +0x000 PageFrameNumber     : Bitfield Pos 12, 36 Bits
   +0x000 ReservedForHardware : Bitfield Pos 48, 4 Bits
   +0x000 ReservedForSoftware : Bitfield Pos 52, 4 Bits
   +0x000 WsleAge             : Bitfield Pos 56, 4 Bits
   +0x000 WsleProtection      : Bitfield Pos 60, 3 Bits
   +0x000 NoExecute           : Bitfield Pos 63, 1 Bit
</code></pre>

Some fields of particular importance:  

* **Valid** - this entry is valid. must be 1 to consider the data inside the rest of the structure valid.  
* **Owner** - 0 for kernel mode pages, 1 for user mode pages. corresponds to the `KPROCESSOR_MODE` enum in the DDK.  
* **LargePage** - noted here, discussed below!  
* **Write** - 0 if the page is read only, 1 if R/W  
* **PageFrameNumber** - the physical address of the base of the next level of paging. mask these bits out or pull them out and shift left by 12 (0xc) to get the address, shown in detail below. abbreviated PFN.    
* **NoExecute** - NX bit. code canot be executed in these pages.  

Each level of the page table hierarchy has an `_MMPTE_HARDWARE` entry. If a permission is set at a lower level, then the permission must be set at all higher levels as well in order for it to take effect. Conversely, if a permission is set at a higher level, it must also be set at all lower levels in order for it to have effect.  

Let's look at an example in user mode on a system with KVAS disabled:  

<pre><code class="plaintext">0: kd> !process 0 0 explorer.exe
PROCESS ffffc8064497b340
    SessionId: 1  Cid: 1038    Peb: 0090c000  ParentCid: 100c
    DirBase: bc33c000  ObjectTable: ffffa2827c3a1800  HandleCount: 1884.
    Image: explorer.exe
0: kd> .process /p /i ffffc8064497b340
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
0: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff805`2e1fd0b0 cc              int     3
1: kd> .reload
Connected to Windows 10 19041 x64 target at (Sun Nov 15 19:51:29.691 2020 (UTC - 5:00)), ptr64 TRUE
Loading Kernel Symbols
...
1: kd> bp /p @$proc ntdll!NtCreateFile
1: kd> g
Breakpoint 0 hit
ntdll!NtCreateFile:
0033:00007ffc`3608c830 4c8bd1          mov     r10,rcx
1: kd> !pte kernel32
                                           VA 00007ffc35ee0000
PXE at FFFFE5F2F97CB7F8    PPE at FFFFE5F2F96FFF80    PDE at FFFFE5F2DFFF0D78    PTE at FFFFE5BFFE1AF700
contains 0A000000BBF48867  contains 0A000000BC34E867  contains 0A000000BC34F867  contains 8100000003806025
pfn bbf48     ---DA--UWEV  pfn bc34e     ---DA--UWEV  pfn bc34f     ---DA--UWEV  pfn 3806      ----A--UR-V
</code></pre>

There are executable pages in `kernel32`, but the page containing the header should not be executable. This is reflected in the page hierarchy above, where the PXE, PPE, and PDE are all RWX, but the PTE indicates that the page is read only. The `!pte` command is detailed more in a few sections, so don't worry if the output is confusing at this moment.  

## Manually Walking the Page Tables
To appreciate tools like `!pte` let's look at an example of manually walking the page tables to resolve the physical address of data from it's virtual address. I'm going to be walking the page tables on a system that has KVAS disabled, to reduce complexity, but note there will be a slight twist in this example.  
Let's look for `nt!NtCreateFile`. First, we can use the `.formats` command to get the binary representation of the address of `nt!NtCreateFile`. The `CR3` register is also required here, since it holds the hardware address of the base of the page tables.  

<pre><code class="plaintext">0: kd> .formats nt!NtCreateFile
Evaluate expression:
  Hex:     fffff805`2e3ff090
  Decimal: -8773842243440
  Octal:   1777777600245617770220
  Binary:  11111111 11111111 11111000 00000101 00101110 00111111 11110000 10010000
  Chars:   .....?..
  Time:    ***** Invalid FILETIME
  Float:   low 4.3642e-011 high -1.#QNAN
  Double:  -1.#QNAN
0: kd> r cr3
cr3=00000000001ad000
</code></pre>

 Since addresses must be canonical, bits **63-49** will all be the same. Then we have bits representing the index into each level of the page tables (9 bits at a time until the page offset):  

* Bits **47-39** = Page-Map Level 4 (*PML4*) entry (sometimes *PXE*)  
* Bits **38-30** = Page Directory Pointer Table (*PDPT*) entry (sometimes *PPE*)  
* Bits **29-21** = Page Directory Entry (*PDE*)  
* Bits **20-12** = Page Table Entry (*PTE*)  
* Bits **11-0** = Offset into physical page where the start of the data resides  

Let's break down the `.formats` output into each index:  

<pre><code class="plaintext">                            PML4 idx.   PDPT idx.   PDT idx.    PTE idx.     page idx.
Binary:  11111111 11111111 [11111000 0][0000101 00][101110 001][11111 11110][000 10010000]
</code></pre>

Each level of the page hierarchy is just an array of 512 (0x200) `_MMPTE_HARDWARE` structures. To get the PML4 entry, index into the array starting at `CR3` by the PML4 index found from the `.formats` command above. Remember the `-p` flag to `dt` or this will fail. Also, instead of prefixing binary with `0b`, which would make too much sense, WinDbg prefixes binary with `0y`.  

<pre><code class="plaintext">0: kd> dt -p _MMPTE_HARDWARE @@C++(@cr3+@@(0y111110000)*sizeof(_MMPTE_HARDWARE))
nt!_MMPTE_HARDWARE
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y1
`  +0x000 Owner            : 0y0
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y0
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y0
   +0x000 PageFrameNumber  : 0y000000000000000000000100101100001001 (0x4b09)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y0000
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y0
</code></pre>

Let's also look at the entry with `!dq`:  

<pre><code class="plaintext">0: kd> !dq @@C++(@cr3+@@(0y111110000)*sizeof(_MMPTE_HARDWARE)) L1
#  1adf80 00000000`04b09063
</code></pre>

To get to the Page Directory Pointer Table (PDPT) entry from here we need to take the `PageFrameNumber`, shift it back into its original position in `_MMPTE_HARDWARE` via a shift left by 12 (0xc) bits and then take the PDPT index. You can also just mask the QWORD that represents the entry (ex. 0x0000000004b09063 & 0xfffffffff000).  

<pre><code class="plaintext">0: kd> dt -p _MMPTE_HARDWARE @@C++((0x4b09<<0xc)+@@(0y000010100)*sizeof(_MMPTE_HARDWARE))
nt!_MMPTE_HARDWARE
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y1
   +0x000 Owner            : 0y0
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y0
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y0
   +0x000 PageFrameNumber  : 0y000000000000000000000100101100001010 (0x4b0a)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y0000
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y0
</code></pre>

Now for the PDE and PTE levels, which are calculated the same way, using the next level's PFN.  

<pre><code class="plaintext">0: kd> dt -p _MMPTE_HARDWARE @@C++((0x4b0a<<0xc)+@@(0y101110001)*sizeof(_MMPTE_HARDWARE))
nt!_MMPTE_HARDWARE
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y0
   +0x000 Owner            : 0y0
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y0
   +0x000 LargePage        : 0y1
   +0x000 Global           : 0y1
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y0
   +0x000 PageFrameNumber  : 0y000000000000000000000010110000000000 (0x2c00)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y1010
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y0
0: kd> dt -p _MMPTE_HARDWARE @@C++((0x2c00<<0xc)+@@(0y1111111110)*sizeof(_MMPTE_HARDWARE))
nt!_MMPTE_HARDWARE
   +0x000 Valid            : 0y0
   +0x000 Dirty1           : 0y0
   +0x000 Owner            : 0y1
   +0x000 WriteThrough     : 0y1
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y0
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y1
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y1
   +0x000 PageFrameNumber  : 0y100001011111011011100000010111011000 (0x85f6e05d8)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y1111
   +0x000 WsleAge          : 0y0000
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y0
</code></pre>

What happened here? The PTE does not seem valid. Pay close attention to the flags in the PDE.  

<pre><code class="plaintext">   +0x000 LargePage        : 0y1</code></pre>

This means that the page is part of a *large page* and the attributes from the PDE apply to every page that it would represent. Large pages on x86 represent a whole PDE worth of pages. The math works out to 1GB of pages represented by a large page:  

<pre><code class="plaintext">0: kd> ? 0n512 * 0n512 * 0x1000 // << number of bytes calculation
Evaluate expression: 1073741824 = 00000000`40000000
0: kd> ? 0n1024 * 0n1024 * 0n1024 // << 1GB calculation
Evaluate expression: 1073741824 = 00000000`40000000
</code></pre>

There are also **huge** pages that work the same way, except at the PDPT level instead.  

To resolve the starting physical address in this situation, you just need to use the remaining bits (20-0) as an offset into the large page PFN. The diagram above (from the `.formats` command) becomes the following:  

<pre><code class="plaintext">                            PML4 idx.   PDPT idx.   PDT idx.    page idx.
Binary:  11111111 11111111 [11111000 0][0000101 00][101110 001][11111 11110000 10010000]
</code></pre>

Now we just need to do the math:  
<pre><code class="plaintext">0: kd> ? (0x2c00<<c)+0y111111111000010010000
Evaluate expression: 48230544 = 00000000`02dff090
</code></pre>

Validate by dumping out what is at the virtual address for `nt!NtCreateFile` and what is at the physical address we calculated above:  

<pre><code class="plaintext">0: kd> !dq (0x2c00<<c)+0y111111111000010010000
# 2dff090 33000000`88ec8148 44c77824`448948c0
# 2dff0a0 44890000`00207024 89602444`89486824
# 2dff0b0 00e02484`8b582444 8b485024`44890000
# 2dff0c0 89480000`00d82484 00d02484`8b482444
# 2dff0d0 848b4024`44890000 24448900`0000c824
# 2dff0e0 000000c0`24848b38 b824848b`30244489
# 2dff0f0 48282444`89000000 48000000`b024848b
# 2dff100 000017e8`20244489 00000088`c4814800
0: kd> dq nt!NtCreateFile
fffff805`2e3ff090  33000000`88ec8148 44c77824`448948c0
fffff805`2e3ff0a0  44890000`00207024 89602444`89486824
fffff805`2e3ff0b0  00e02484`8b582444 8b485024`44890000
fffff805`2e3ff0c0  89480000`00d82484 00d02484`8b482444
fffff805`2e3ff0d0  848b4024`44890000 24448900`0000c824
fffff805`2e3ff0e0  000000c0`24848b38 b824848b`30244489
fffff805`2e3ff0f0  48282444`89000000 48000000`b024848b
fffff805`2e3ff100  000017e8`20244489 00000088`c4814800
</code></pre>

There you have it, validation that the process we followed was correct. If the PDE was not a large page then the PTE would have been valid and bits 11-0 would have been an index into the PFN of the PTE.  

## Windbg Commands
Of course it is very annoying to do that whole process manually, so WinDbg provides two ways to accomplish what we just looked at. The `!pte` command will take what is in `CR3` and walk the page tables with the virtual address you give it. To match up with the same example as above:  

<pre><code class="plaintext">0: kd> !pte nt!NtCreateFile
                                           VA fffff8052e3ff090
PXE at FFFFE5F2F97CBF80    PPE at FFFFE5F2F97F00A0    PDE at FFFFE5F2FE014B88    PTE at FFFFE5FC02971FF8
contains 0000000004B09063  contains 0000000004B0A063  contains 0A00000002C001A1  contains 0000000000000000
pfn 4b09      ---DA--KWEV  pfn 4b0a      ---DA--KWEV  pfn 2c00      -GL-A--KREV  LARGE PAGE pfn 2dff 
</code></pre>

This shows the virtual addresses of each level in the hierarchy as well as a breakdown of what each `_MMPTE_HARDWARE` structure contains. 
There is also the `!vtop` command, which will let you specify what page table base (hardware address) to use as the base of the page tables (PML4). This will become useful to us in investigating KVAS, because we want to be able to look at each page table without having to change `CR3`. Again mirroring the example above to show what data it provides:  

<pre><code class="plaintext">0: kd> r cr3
cr3=00000000001ad000
0: kd> ? nt!NtCreateFile
Evaluate expression: -8773842243440 = fffff805`2e3ff090
0: kd> !vtop 1ad000 fffff8052e3ff090
Amd64VtoP: Virt fffff8052e3ff090, pagedir 00000000001ad000
Amd64VtoP: PML4E 00000000001adf80
Amd64VtoP: PDPE 0000000004b090a0
Amd64VtoP: PDE 0000000004b0ab88
Amd64VtoP: Large page mapped phys 0000000002dff090
Virtual address fffff8052e3ff090 translates to physical address 2dff090.
</code></pre>

You can examine the addresses via dump commands prefixed with `!` (ex. `!dq`, `!dd`, `!dc`) and by using dump type (`dt`) with the `-p` flag for physical addresses.  

Note that `!vtop` doesn't play as nice with symbols or WinDbg numbers, so make sure things are in the right format before passing them in. For example, the following commands are invalid to `!vtop`:  

<pre><code class="plaintext">0: kd> !vtop 1ad000 nt!NtCreateFile
Amd64VtoP: Virt 0000000000000000, pagedir 00000000001ad000
Amd64VtoP: PML4E 00000000001ad000
Amd64VtoP: PDPE 0000000100ee1000
Amd64VtoP: zero PDPE
Virtual address 0 translation fails, error 0xD0000147.
0: kd> !vtop @cr3 fffff8052e3ff090
usage: vtop PFNOfPDE VA
0: kd> !vtop 1ad000 fffff805`2e3ff090
Amd64VtoP: Virt 00000000fffff805, pagedir 00000000001ad000
Amd64VtoP: PML4E 00000000001ad000
Amd64VtoP: PDPE 0000000100ee1018
Amd64VtoP: zero PDPE
Virtual address fffff805 translation fails, error 0xD0000147.
</code></pre>

We will be using these commads to walk the page tables for the rest of the post, but it is good to know how to manually walk them.  

# SMEP
SMEP stands for Supervisor Mode Execution Prevention (or sometimes Protection). The idea here is code in lower privileged memory pages should never be trusted (i.e. executed) by a higher privileged mode. For standard SMAP this means executable pages allocated in user mode should not be executed while in kernel mode. It is enforced by the CPU itself and requires [explicit support](https://www.intel.com/content/dam/www/public/us/en/documents/datasheets/3rd-gen-core-desktop-vol-1-datasheet.pdf). AMD and Intel processors started rolling out support for this feature in around 2012 for Intel (Ivy Bridge) and 2014 for AMD (Family 17h, Family 15h model >60h). SMEP is enabled on a supported processor when bit 20 of the `CR4` register is set. This is consistent between AMD and Intel processors. Do you remember the owner bit (U/K) from the `_MMPTE_HARDWARE` structure? This is the bit that says whether a page belongs to user mode or kernel mode and is how SMEP is enforced. When in kernel mode (supervisor mode), if the owner bit is 1, then the page is owned by user mode and code should not be executed inside of it. This begs the question: well, what if we can flip that bit? Can we execute those pages? The answer there is yes absolutely, until KVAS was introduced. My favorite presentation on this topic is from EKOParty 2015 by Enrique Nissim and Nicolas Economou called [Windows SMEP Bypass U=S](https://github.com/n3k/EKOParty2015_Windows_SMEP_Bypass). We will examine why KVAS mitigates this attack soon.  

Another technology that implements the same sort of trust boundary that SMEP enforces is called Mode-Based Execution Control (MBEC, or just MBE Control), which is enforced between a hypervisor and its guest(s). I'm not going to deep dive into that here, but just know that the high level concept of SMEP applies where the supervisor (hypervisor) does not trust the less privileged pages in user mode (guest) and thus will not execute in them from supervisor mode. Another interesting note about hypervisors: it's also possible to implement software SMEP via Extended Page Table (EPT) permissions. [Here's a post from 2014](https://hypervsir.blogspot.com/2014/11/how-to-implement-software-based.html) detailing how this might be done.  

There is also Supervisor Mode Access Prevention (SMAP), which is a newer control that prevents accesses to user mode while in kernel mode, unless certain conditions are met. This is not entirely relevent to this post, so I'll skip the details on this one for now as well.  

# KVAS Implementation in Brief
To avoid information disclosure from a successful exploit of the Meltdown vulnerability, separate page tables are kept for user mode and kernel mode for each process. The general term for this technology is Kernel Page Table Isolation (KPTI). Kernel Virtual Address Shadow (KVAS) is the Windows specific implementation of KPTI. The user mode version of the page tables does not even contain the mappings for (almost all) kernel addresses, which the kernel mode version contains mappings for both user and kernel address spaces. Some pages exist in both sets, like KUSER_SHARED_DATA and the system call handler, which actually replaces `CR3` on entry and exit into/from the handler, as well as other kernel entry/exit points. We will be looking specifically at the system call handler for this example.  

Check out the [Microsoft blog post describing the implementation](https://msrc-blog.microsoft.com/2018/03/23/kva-shadow-mitigating-meltdown-on-windows/). Fortinet also has a [great post](https://www.fortinet.com/blog/threat-research/a-deep-dive-analysis-of-microsoft-s-kernel-virtual-address-shadow-feature) on the internals of how KVAS is initialized in the kernel.

Your first thought with this implementation may be: "that sounds very memory expensive!". The overhead of having two sets of paging structures (which occupy some memory) is definitely nonzero. However, one optimization that exists relies on the fact that Microsoft does not consider the boundary between an administrator account and the kernel to be a security boundary. Processes that execute in an elevated context do not use KVAS at all! From [Microsoft](https://msrc-blog.microsoft.com/2018/03/23/kva-shadow-mitigating-meltdown-on-windows/)

> Because these applications are fully trusted by the operating system, and already have (or could obtain) the capability to load drivers that could naturally access kernel memory, KVA shadowing is not required for fully-privileged applications.

This includes applications that are run by users in the `BUILTIN\Administrators` group and `processes that execute as a fully-elevated administrator account`. Remember: this is an information disclosure concern, so if that information can already be accessed, disclosing it is not a concern. Low privileged users should not be able to leak kernel memory, so this mitigation will be in full effect for those users.  

** Below this point is not finished yet. **
`_KPROCESS.DirectoryTableBase == _KPCR.Prcb.KernelDirectoryTableBase` and has all mappings (user/kernel). Switched out when a context switch occurs. When returning to user mode `nt!KiKernelSysretExit` loads the user mode base from `_KPROCESS.UserDirectoryTableBase` if and only if `_KPROCESS.AddressPolicy` is 0.  

<center>
![KiKernelSysretExit]({static}/images/windows-10-kvas-and-software-smep/KiKernelSysretExit.png)  
<small>KiKernelSysretExit checks if `CR3` needs to be updated or not</small>
</center>

With KVAS enabled, the hardware address in CR3 has some flags in the bottom bits. 2 for kernel mode page table (kernel/user exposed) and 1 for user mode page table (user ONLY). To use the `!vtop` command with these values, just mask off the bottom bits.  

`_KPCR.Prcb.ShadowFlags` will hold 2 for a privileged process and 1 for an unprivileged process.  

`nt!MiCheckProcessShadow` checks the `AddressPolicy`


# Experiments
Now onto my experiments. For each experiment I will run the same commands on a system with KVAS enabled and also on a system with KVAS disabled and note the differences. Hopefully this will help you understand the implementation a bit better! I know it has helped me.  

## KVAS Implemetation
### KVAS Enabled
```
vertarget
!cpuinfo
!process 0 0 explorer.exe
.process /i /p <eproc>
g
.reload
dt nt!_KPROCESS @$proc DirectoryTableBase
dt nt!_KPROCESS @$proc UserDirectoryTableBase
dt nt!_KPCR @$pcr Prcb.KernelDirectoryTableBase
rdmsr c0000082
u <addr>
? nt!NtCreateFile
!vtop <kernelbase> <nt!NtCreateFile>
dt -p nt!_MMPTE_HARDWARE <addr>
!vtop <userbase> <nt!NtCreateFile>
r cr3
!pte <ntdll!NtCreateFile>
!pte <nt!NtCreateFile>
```
### KVAS Disabled

## Software SMEP
### KVAS Enabled
### KVAS Disabled
```
? ntdll!NtCreateFile
!vtop <userbase> <ntdll!NtCreateFile>
dt -p nt!_MMPTE_HARDWARE <addr>
!vtop <kernelbase> <ntdll!NtCreateFile>
dt -p nt!_MMPTE_HARDWARE <addr>
!!!!!
```
## KVAS Disabled in Privileged Processes
### KVAS Enabled
### KVAS Disabled
```
!process 0 0 cmd.exe
dt nt!_KPROCESS <one> DirectoryTableBase UserDirectoryTableBase AddressPolicy
dt nt!_KPROCESS <two> DirectoryTableBase UserDirectoryTableBase AddressPolicy
// note differences
.process /i /p <nonpriv>
g
dt nt!_KPCR @$pcr Prcb.KernelDirectoryTableBase Prcb.ShadowFlags
.process /i /p <priv>
dt nt!_KPCR @$pcr Prcb.KernelDirectoryTableBase Prcb.ShadowFlags
// note that Shadow Flags is 2 on priv, 1 on non-priv
```

## Faults
For this section I will be testing the existence of software SMEP by running with permutations of not only KVAS enabled/disabled, but also with SMEP enabled/disabled. For each case, I have outlined an expected result for fun, let's see if my assumptions match up with reality!  
### KVAS Enabled, SMEP Enabled
Expected result: fault on user mode page execution in kernel mode  
### KVAS Disabled, SMEP Enabled
Expected result: fault on user mode page execution in kernel mode  
### KVAS Enabled, SMEP Disabled
"Software SMEP"
Expected result: fault on user mode page execution in kernel mode  
### KVAS Disabled, SMEP Enabled
Expected result: successful execution in a user mode page  


Shadow enabled vs. disabled SMEP exceptions
```
!process 0 0 explorer.exe
.process /i /p <eproc>
g
.reload
u kernel32+1000
r rip=kernel32+1000
g
```

# Wrap up
I hope you've learned a thing or two from this. I've been wanting to do this investigation for a while, just to nail down the implementation details here. If you have questions feel free to reach out on Twitter [@jgeigerm](https://twitter.com/jgeigerm). For now and as always ~~h a v e f u n i n s i d e~~.  

## Other resources I didn't find a place for but still wanted to include
* Using KVAS to hide from KPP checks: [https://www.cyfyx.com/2019/01/melting-down-patchguard-leveraging-kpti-to-bypass-kernel-patch-protection/](https://www.cyfyx.com/2019/01/melting-down-patchguard-leveraging-kpti-to-bypass-kernel-patch-protection/)  
* Considerations for exploits: [https://zerosum0x0.blogspot.com/2019/11/fixing-remote-windows-kernel-payloads-meltdown.html](https://zerosum0x0.blogspot.com/2019/11/fixing-remote-windows-kernel-payloads-meltdown.html)  