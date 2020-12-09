Title: Windows 10 KVAS and Software SMEP  
Date: 2020-11-14 20:32  
Category: System Internals  
Tags: windows windows-internals  
Slug: windows-10-kvas-and-software-smep  
Authors: wumb0  

Kernel Virtual Address Shadow (KVAS) is the Windows implementation of Kernel Page Table Isolation (KPTI). It was introduced to mitigate the [Meltdown](https://meltdownattack.com/meltdown.pdf) vulnerability, which allowed an attacker that could execute code in user mode to leak out data from the kernel by abusing a side channel. While there are plenty of papers and blog posts on Meltdown and KVAS, there isn't much info on an interesting feature that KVAS enables: software SMEP. Unfortunately or fortunately, depending on your interest level in this post and Windows internals, understanding how software SMEP works requires knowledge of x86\_64 paging, regular SMEP, and KVAS, so I'll be getting into those topics enough to give you an understanding of the underlying technology. Near the end I'll be running some experiments to show the internals of what I covered in the technical sections prior.  

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
* **NoExecute** - NX bit. code cannot be executed in these pages.  

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

We will be using these commands to walk the page tables for the rest of the post, but it is good to know how to manually walk them.  

# SMEP
SMEP stands for Supervisor Mode Execution Prevention (or sometimes Protection). The idea here is code in lower privileged memory pages should never be trusted (i.e. executed) by a higher privileged mode. For standard SMEP this means executable pages allocated in user mode should not be executed while in kernel mode. It is enforced by the CPU itself and requires [explicit support](https://www.intel.com/content/dam/www/public/us/en/documents/datasheets/3rd-gen-core-desktop-vol-1-datasheet.pdf). AMD and Intel processors started rolling out support for this feature in around 2012 for Intel (Ivy Bridge) and 2014 for AMD (Family 17h, Family 15h model >60h). SMEP is enabled on a supported processor when bit 20 of the `CR4` register is set. This is consistent between AMD and Intel processors. Do you remember the owner bit (U/K) from the `_MMPTE_HARDWARE` structure? This is the bit that says whether a page belongs to user mode or kernel mode and is how SMEP is enforced. When in kernel mode (supervisor mode), if the owner bit is 1, then the page is owned by user mode and code should not be executed inside of it. This begs the question: well, what if we can flip that bit? Can we execute those pages? The answer there is yes absolutely, until KVAS was introduced. My favorite presentation on this topic is from EKOParty 2015 by Enrique Nissim and Nicolas Economou called [Windows SMEP Bypass U=S](https://github.com/n3k/EKOParty2015_Windows_SMEP_Bypass). We will examine why KVAS mitigates this attack soon.  

Another technology that implements the same sort of trust boundary that SMEP enforces is called Mode-Based Execution Control (MBEC, or just MBE Control), which is enforced between a hypervisor and its guest(s). I'm not going to deep dive into that here, but just know that the high level concept of SMEP applies where the supervisor (hypervisor) does not trust the less privileged pages in user mode (guest) and thus will not execute in them from supervisor mode. Another interesting note about hypervisors: it's also possible to implement software SMEP via Extended Page Table (EPT) permissions. [Here's a post from 2014](https://hypervsir.blogspot.com/2014/11/how-to-implement-software-based.html) detailing how this might be done.  

There is also Supervisor Mode Access Prevention (SMAP), which is a newer control that prevents accesses to user mode while in kernel mode, unless certain conditions are met. It can be turned on via bit 21 of `CR4` on supported processors. This is not entirely relevant to this post, so I'll skip the details on this one for now as well.  

# KVAS Implementation in Brief
To avoid information disclosure from a successful exploit of the Meltdown vulnerability, separate page tables are kept for user mode and kernel mode for each process. The general term for this technology is Kernel Page Table Isolation (KPTI). Kernel Virtual Address Shadow (KVAS) is the Windows specific implementation of KPTI. The user mode version of the page tables does not even contain the mappings for (almost all) kernel addresses, which the kernel mode version contains mappings for both user and kernel address spaces. Some pages exist in both sets, like KUSER_SHARED_DATA and the system call handler, which actually replaces `CR3` on entry and exit into/from the handler, as well as other kernel entry/exit points. We will be looking specifically at the system call handler for this example.  

Check out the [Microsoft blog post describing the implementation](https://msrc-blog.microsoft.com/2018/03/23/kva-shadow-mitigating-meltdown-on-windows/). Fortinet also has a [great post](https://www.fortinet.com/blog/threat-research/a-deep-dive-analysis-of-microsoft-s-kernel-virtual-address-shadow-feature) on the internals of how KVAS is initialized in the kernel.

Your first thought with this implementation may be: "that sounds very memory expensive!". The overhead of having two sets of paging structures (which occupy some memory) per process is definitely nonzero. However, one optimization that exists relies on the fact that Microsoft does not consider the boundary between an administrator account and the kernel to be a security boundary. Processes that execute in an elevated context do not use KVAS at all! From [Microsoft](https://msrc-blog.microsoft.com/2018/03/23/kva-shadow-mitigating-meltdown-on-windows/)

> Because these applications are fully trusted by the operating system, and already have (or could obtain) the capability to load drivers that could naturally access kernel memory, KVA shadowing is not required for fully-privileged applications.

This includes applications that are run by users in the `BUILTIN\Administrators` group and *"processes that execute as a fully-elevated administrator account"*. Remember: this is an information disclosure concern, so if that information can already be accessed, disclosing it is not a concern. Low privileged users should not be able to leak kernel memory, so this mitigation will be in full effect for those users.  

<hr>

To begin to understand the implementation of KVAS in the Windows kernel, we can look at important fields in the `nt!_KPRCB` and `nt!_KPROCESS` structures:    

<pre><code class="plaintext">0: kd> dt _KPROCESS DirectoryTableBase UserDirectoryTableBase AddressPolicy
ntdll!_KPROCESS
   +0x028 DirectoryTableBase     : Uint8B
   +0x388 UserDirectoryTableBase : Uint8B
   +0x390 AddressPolicy          : UChar
0: kd> dt nt!_KPRCB KernelDirectoryTableBase RspBaseShadow UserRspShadow ShadowFlags
   +0x8e80 KernelDirectoryTableBase : Uint8B
   +0x8e88 RspBaseShadow            : Uint8B
   +0x8e90 UserRspShadow            : Uint8B
   +0x8e98 ShadowFlags              : Uint4B
</code></pre>

Before KVAS, `_KPROCESS.DirectoryTableBase` held the base of the page tables for a particular process. Remember, on a system without KVAS or in a process where KVAS is disabled, the user and kernel page tables are not separated, so `_KPROCESS.DirectoryTableBase` is moved into `CR3` on process context switch. When KVAS is enabled, `_KPROCESS.DirectoryTableBase` holds the complete (user and kernel) page table base. The value of `_KPROCESS.DirectoryTableBase` is moved into `_KPRCB.KernelDirectoryTableBase` when a process context switch occurs. The user-only page table base is held in  `_KPROCESS.UserDirectoryTableBase`. The `_KPROCESS.AddressPolicy` field tells the kernel if a process participates in KVAS. If `_KPROCESS.AddressPolicy` is 1, then KVAS is disabled for the process; if it is 0, then KVAS is enabled. `_KPRCB.ShadowFlags` holds flags that tell the kernel if KVAS is enabled for the process (according to `_KPROCESS.AddressPolicy`) and which page table is active. On entry points to the kernel, the value from `_KPRCB.KernelDirectoryTableBase` is loaded into `CR3`. On exit from the kernel `_KPROCESS.UserDirectoryTableBase` is moved into `CR3`. `_KPRCB.RspBaseShadow` and `_KPRCB.UserRspShadow` hold the stack pointer for each mode and are loaded into `RSP` at entry/exit from the kernel, respectively.  
  

In a KVAS participating process, the hardware address in `CR3` has some flags in the bottom bits:  bit 0 is set for a user mode page table and bit 1 is set for a kernel mode page table. This can be seen by examining `_KPROCESS.DirectoryTableBase` and `_KPROCESS.UserDirectoryTableBase` for a KVAS participating process (explorer.exe):  

<pre><code class="plaintext">0: kd> !process 0 0 explorer.exe
PROCESS ffffb68d61dd9080
    SessionId: 1  Cid: 1098    Peb: 00fa4000  ParentCid: 1078
    DirBase: bd6de002  ObjectTable: ffffde87c9020e00  HandleCount: 2120.
    Image: explorer.exe

0: kd> .process /i /p ffffb68d61dd9080
0: kd> dt _KPROCESS @$proc DirectoryTableBase UserDirectoryTableBase
ntdll!_KPROCESS
   +0x028 DirectoryTableBase     : 0xbd6de002
   +0x388 UserDirectoryTableBase : 0xbd6dd001
</code></pre>

To use the `!vtop` command with these values, just mask off the bottom bits.

<hr>

The system call handler is different on systems wth KVAS enabled. The system call handler is located in Model Specific Register (MSR) 0xC0000082 (LSTAR) for x86 systems. On a x86_64 machine with KVAS explicitly disabled, the system call handler is `KiSystemCall64` as shown below:  

<pre><code class="plaintext">0: kd> db nt!KiKvaShadow L1
fffff805`2ec01840  00                                               .
0: kd> rdmsr c0000082
msr[c0000082] = fffff805`2e2066c0
0: kd> ln fffff805`2e2066c0
Browse module
Set bu breakpoint

(fffff805`2e2066c0)   nt!KiSystemCall64   |  (fffff805`2e206900)   nt!KiSystemServiceUser
</code></pre>

At the top of the system call handler you can see that `RSP` is moved into `_KPCR.UserRsp` and `_PRCB.RspBase` is moved into `RSP`. `_KPCR.UserRsp` is then pushed onto the kernel stack for recovery later (at the end of the system call handler).  

<center>
![KiSystemCall64]({static}/images/windows-10-kvas-and-software-smep/KiSystemCall64.png)  
<small>The system call handler when KVAS is disabled for the system</small>
</center>

Next, let's look at the system call handler that is used when KVAS is enabled on the system:  

<pre><code class="plaintext">0: kd> db nt!KiKvaShadow L1
fffff804`75001840  01                                               .
0: kd> rdmsr c0000082
msr[c0000082] = fffff804`74c13180
0: kd> ln fffff804`74c13180
Browse module
Set bu breakpoint

(fffff804`74c13180)   nt!KiSystemCall64Shadow   |  (fffff804`74c14060)   nt!_guard_retpoline_icall_handler
</code></pre>

`KiSystemCall64Shadow` is used. The beginning of this function is similar to `KiSystemCall64`, with a few extra steps. It backs up `RSP` to `_KPRCB.UserRspShadow`, swaps `_KPRCB.KernelDirectoryTableBase` into `CR3` if the second bit of `_KPRCB.ShadowFlags` is set, and restores the kernel stack pointer to `RSP` from `_KPRCB.RspBaseShadow`, before pushing `_KPRCB.UserRspShadow` to the stack (as opposed to `_KPCR.UserRsp`). See the disassembly below:  

<center>
![KiSystemCall64Shadow]({static}/images/windows-10-kvas-and-software-smep/KiSystemCall64Shadow.png)  
<small>The system call handler when KVAS is enabled for the system</small>
</center>

At the end of `KiSystemCall64Shadow` there is a jump to `KiSystemServiceUser` which is partway through `KiSystemCall64`.  

<center>
![KiSystemCall64Shadow_end]({static}/images/windows-10-kvas-and-software-smep/KiSystemCall64Shadow_end.png)  
<small>The end of the Shadow syscall handler jumps to the label `KiSystemServiceUser`, which is in the middle of `KiSystemCall64`</small>
</center>

At the end of `KiSystemCall64` there is a test to see if `KiKvaShadow` is 1 (KVAS enabled) and if it is a jump to `KiKernelSysretExit` is made.  

<center>
![KiSystemCall64_return]({static}/images/windows-10-kvas-and-software-smep/KiSystemCall64_return.png)  
<small>The end of `KiSystemCall64` calls `KiKernelSysretExit` if KVAS is enabled</small>
</center>

`KiKernelSysretExit` checks the 2nd bit of `_KPRCB.ShadowFlags` to see if KVAS is enforced for the process (0 = enforced, 1 = not enforced). If it is enforced, then `_KPROCESS.UserDirectoryTableBase` is loaded into `CR3`. If the low bit of `_KPRCB.UserDirectoryTableBase` is set and the low bit of `_KPRCB.ShadowFlags` is set, then the low bit of `_KPRCB.ShadowFlags` is unset indicating that the user page table is now in use.  

<center>
![KiKernelSysretExit]({static}/images/windows-10-kvas-and-software-smep/KiKernelSysretExit.png)  
<small>KiKernelSysretExit checks if `CR3` needs to be updated or not on exit from the kernel</small>
</center>

`KiKernelSysretExit` is called in a few different places. Unsurprisingly, these places are exit-points from the kernel.   
<center>
![KiKernelSysretExit_xref]({static}/images/windows-10-kvas-and-software-smep/KiKernelSysretExit_xref.png)  
<small>`KiKernelSysretExit` is called in a few kernel exitpoint functions</small>
</center>

<hr>

Next, let's look at cross references of `KiKvaShadow` just to get an idea of what functions are affected by KVAS. 

<center>
![KiKvaShadow_xref]({static}/images/windows-10-kvas-and-software-smep/KiKvaShadow_xref.png)  
<small>The shadow flag is checked in many places</small>
</center>

There are quite a few functions where this flag is checked. Investigating interesting functions is an exercise left up to the reader.

<hr>

Now that we have seen a few places where the kernel switches up `CR3`, let's look at thread context switching to see how it is handled. Thread context switching is performed by the `nt!KiSwapContext` function, which saves the context and then calls `nt!SwapContext`:  

<center>
![KiSwapContext]({static}/images/windows-10-kvas-and-software-smep/KiSwapContext.png)  
<small>`KiSwapContext` is a small function that calls `SwapContext`</small>
</center>

The `RCX` and `RDX` registers hold the destination and source `_KTHREAD` structures, respectively. These values are moved into `RSI` and `RDI` in preparation for a call to `nt!SwapContext`. An overview of `SwapContext` can be seen below:   

<center>
![SwapContext_overview]({static}/images/windows-10-kvas-and-software-smep/SwapContext_overview.png)  
<small>`SwapContext` is a fairly large function</small>
</center>

In `SwapContext`, `RDI` is a pointer to the thread being switched out and `RSI` is a pointer to the thread being switched in. Among other things and especially important to us, `SwapContext` is responsible for switching in the correct page table to `CR3`, checking the destination process's address policy, and setting up `_KPRCB.ShadowFlags` as well as `_KPRCB.KernelDirectoryTableBase`. If the destination process is the same as the source process, this entire process is unnecessary and is skipped. If they are different, then they may have different address policies. The destination process (`RSI.ApcState.Process`) is loaded into `R14` and then if KVAS is enabled on the system, the 2nd bit of `_KPROCESS.DirectoryTableBase` is checked to see if it is a kernel page table. If it is a kernel page table, the high bit of the page table will be set and the low bit of `_KPRCB.ShadowFlags` will be set. The (potentially) modified kernel page table address is then moved int `_KPRCB.KernelDirectoryTableBase`, the page table's high bit is unset, the 2nd bit of `_KPRCB.ShadowFlags` is masked off (unset), and `_KPROCESS.AddressPolicy` is checked. If the address policy is 1 (KVAS not enforced), then `_KPRCB.ShadowFlags` is xor-ed with 3 (0b11) to set the 2nd bit and unset the first resulting in a `_KPRCB.ShadowFlags` value of 2. Then, the page table address is put into `CR3`. Interrupts are disabled (`cli`) and then re-enabled (`sti`) to prevent the system from interrupting this process. If running under Hyper-V, then instead of accessing `CR3` directly, a hypercall will be made to switch address spaces.  

<center>
![SwapContext_AddressPolicy]({static}/images/windows-10-kvas-and-software-smep/SwapContext_AddressPolicy.png)  
<small>The correct `ShadowFlags` are set based on a number of checks, then `CR3` is updated with the new page table base</small>
</center>

A few blocks down, the thread's initial stack (`_KTHREAD.InitialStack`) is saved in `_KPRCB.RspBase` and either `_KPCR.TssBase->Rsp0` or `_KPRCB.RspBaseShadow`; the latter is used on a KVAS enabled system.  

<center>
![SwapContext_tss_or_RspBaseShadow]({static}/images/windows-10-kvas-and-software-smep/SwapContext_tss_or_RspBaseShadow.png)  
<small>The current thread's kernel stack base is kept in different places for KVAS and non-KVAS processes</small>
</center>

On examination of these fields, we can see that on a KVAS enabled system `_KPRCB.RspBase`, `_KPRCB.RspBaseShadow`, and `_KTHREAD.InitialStack` are all the same value.  

<pre><code class="plaintext">0: kd> dt _KPCR @$pcr Prcb.UserRspShadow Prcb.RspBase Prcb.RspBaseShadow TssBase->Rsp0
ntdll!_KPCR
   +0x008 TssBase            : 
      +0x004 Rsp0               : 0xfffff804`78c64200
   +0x180 Prcb               : 
      +0x028 RspBase            : 0xffff828b`d7d02c90
      +0x8e88 RspBaseShadow      : 0xffff828b`d7d02c90
      +0x8e90 UserRspShadow      : 0x555ee68
0: kd> dt _KTHREAD @$thread InitialStack
ntdll!_KTHREAD
   +0x028 InitialStack : 0xffff828b`d7d02c90 Void
</code></pre>

On a KVAS disabled system, `_KPCR.TssBase->Rsp0`, `_KPRCB.RspBase`, and `_KTHREAD.InitialStack` are all the same value.  

<pre><code class="plaintext">0: kd> dt _KPCR @$pcr Prcb.UserRspShadow Prcb.RspBase Prcb.RspBaseShadow TssBase->Rsp0
nt!_KPCR
   +0x008 TssBase            : 
      +0x004 Rsp0               : 0xfffff805`31d3cc90
   +0x180 Prcb               : 
      +0x028 RspBase            : 0xfffff805`31d3cc90
      +0x8e88 RspBaseShadow      : 0
      +0x8e90 UserRspShadow      : 0
0: kd> dt _KTHREAD @$thread InitialStack
nt!_KTHREAD
   +0x028 InitialStack : 0xfffff805`31d3cc90 Void
</code></pre>

<hr>

A final question: What do all of these functions have in common?  
**They are all in the KVASCODE section of the kernel binary.**  

<center>
![KVASCODE]({static}/images/windows-10-kvas-and-software-smep/KVASCODE.png)  
<small>The KVASCODE section is mapped for both sets of page tables</small>
</center>

This section of the kernel binary is mapped in both sets of page tables! To validate this claim, let's use `!vtop` to resolve `nt!KiSystemCall64Shadow` (0xfffff80474c13180) in both sets of page tables.  

<pre><code class="plaintext">0: kd> dt _KPROCESS @$proc DirectoryTableBase UserDirectoryTableBase
ntdll!_KPROCESS
   +0x028 DirectoryTableBase     : 0xbd6de002
   +0x388 UserDirectoryTableBase : 0xbd6dd001
0: kd> !vtop 0xbd6de000 0xfffff80474c13180
Amd64VtoP: Virt fffff80474c13180, pagedir 00000000bd6de000
Amd64VtoP: PML4E 00000000bd6def80
Amd64VtoP: PDPE 0000000004809088
Amd64VtoP: PDE 000000000480ad30
Amd64VtoP: Large page mapped phys 0000000003213180
Virtual address fffff80474c13180 translates to physical address 3213180.
0: kd> !vtop 0xbd6dd000 0xfffff80474c13180
Amd64VtoP: Virt fffff80474c13180, pagedir 00000000bd6dd000
Amd64VtoP: PML4E 00000000bd6ddf80
Amd64VtoP: PDPE 000000013cd21088
Amd64VtoP: PDE 000000013cd20d30
Amd64VtoP: PTE 000000013cd27098
Amd64VtoP: Mapped phys 0000000003213180
Virtual address fffff80474c13180 translates to physical address 3213180.
</code></pre>

The address maps successfully to physical address 3213180 in both sets of page tables for this particular process. This makes sense because if these functions didn't exist in both sets of page tables then the implementation would not be able to do the switch properly. The backing memory would not exist according to the page table at some point during the function (either before or after the `CR3` switch).

# Experiments
Now onto my experiments. For each experiment I will run the same commands on a system with KVAS enabled and also on a system with KVAS disabled and note the differences. Hopefully this will help you understand the implementation a bit better! I know it has helped me.  

## KVAS Implemetation
For the first experiment, I will show the effect of KVAS by showing a function that exists in one page table, but not the other on the KVAS enabled system. I will also show that the system call handler is different between the two systems.  

First, I will switch process contexts to `explorer.exe` then I will look at what is in MSR 0xC0000082 (LSTAR). Next, I will look up the page tables used by the process and try to resolve the physical address of `nt!NtCreateFile` in each page table using `!vtop`.  

### KVAS Enabled

<pre><code class="plaintext">1: kd> !cpuinfo
CP  F/M/S Manufacturer  MHz PRCB Signature    MSR 8B Signature Features
 0  6,158,10 GenuineIntel 2592 000000d600000000                   311b3dff
 1  6,158,10 GenuineIntel 2592 000000d600000000 >000000d600000000<311b3dff
                      Cached Update Signature 000000d600000000
                     Initial Update Signature 000000d600000000
1: kd> !process 0 0 explorer.exe
PROCESS ffffb68d61dd9080
    SessionId: 1  Cid: 1098    Peb: 00fa4000  ParentCid: 1078
    DirBase: bd6de002  ObjectTable: ffffde87c9020e00  HandleCount: 2360.
    Image: explorer.exe

1: kd> .process /i /p ffffb68d61dd9080
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
1: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff804`745fd0b0 cc              int     3
1: kd> .reload
Connected to Windows 10 19041 x64 target at (Fri Nov 27 20:52:29.550 2020 (UTC - 5:00)), ptr64 TRUE
Loading Kernel Symbols
...............................................................
................................................................
Loading User Symbols
.......................................................
Loading unloaded module list
1: kd> dt nt!_KPROCESS @$proc DirectoryTableBase
   +0x028 DirectoryTableBase : 0xbd6de002
1: kd> dt nt!_KPROCESS @$proc UserDirectoryTableBase
   +0x388 UserDirectoryTableBase : 0xbd6dd001
1: kd> dt nt!_KPCR @$pcr Prcb.KernelDirectoryTableBase
   +0x180 Prcb                          : 
      +0x8e80 KernelDirectoryTableBase      : 0x80000000`bd6de002
1: kd> rdmsr c0000082
msr[c0000082] = fffff804`74c13180
1: kd> ln fffff804`74c13180
Browse module
Set bu breakpoint

(fffff804`74c13180)   nt!KiSystemCall64Shadow   |  (fffff804`74c14060)   nt!_guard_retpoline_icall_handler
Exact matches:
1: kd> ? nt!NtCreateFile
Evaluate expression: -8776958611312 = fffff804`747ff090
1: kd> !vtop
usage: vtop PFNOfPDE VA
1: kd> !vtop 0xbd6de000 0xfffff804747ff090
Amd64VtoP: Virt fffff804747ff090, pagedir 00000000bd6de000
Amd64VtoP: PML4E 00000000bd6def80
Amd64VtoP: PDPE 0000000004809088
Amd64VtoP: PDE 000000000480ad18
Amd64VtoP: Large page mapped phys 0000000002dff090
Virtual address fffff804747ff090 translates to physical address 2dff090.
1: kd> !vtop 0xbd6dd000 0xfffff804747ff090
Amd64VtoP: Virt fffff804747ff090, pagedir 00000000bd6dd000
Amd64VtoP: PML4E 00000000bd6ddf80
Amd64VtoP: PDPE 000000013cd21088
Amd64VtoP: PDE 000000013cd20d18
Amd64VtoP: zero PDE
Virtual address fffff804747ff090 translation fails, error 0xD0000147.
1: kd> r cr3
cr3=00000000bd6de002
1: kd> !pte nt!NtCreateFile
                                           VA fffff804747ff090
PXE at FFFF87C3E1F0FF80    PPE at FFFF87C3E1FF0088    PDE at FFFF87C3FE011D18    PTE at FFFF87FC023A3FF8
contains 0000000004809063  contains 000000000480A063  contains 0A00000002C000A1  contains 0000000000000000
pfn 4809      ---DA--KWEV  pfn 480a      ---DA--KWEV  pfn 2c00      --L-A--KREV  LARGE PAGE pfn 2dff        

1: kd> !pte ntdll!NtCreateFile
                                           VA 00007ffe181ec830
PXE at FFFF87C3E1F0F7F8    PPE at FFFF87C3E1EFFFC0    PDE at FFFF87C3DFFF8600    PTE at FFFF87BFFF0C0F60
contains 8A0000003F8EA867  contains 0A0000003DFF0867  contains 0A0000003DFF1867  contains 01000001006B4025
pfn 3f8ea     ---DA--UW-V  pfn 3dff0     ---DA--UWEV  pfn 3dff1     ---DA--UWEV  pfn 1006b4    ----A--UREV
</code></pre>

### KVAS Disabled

<pre><code class="plaintext">0: kd> !cpuinfo
CP  F/M/S Manufacturer  MHz PRCB Signature    MSR 8B Signature Features
 0  6,158,10 GenuineIntel 2592 000000d600000000 >000000d600000000<311b3dff
 1  6,158,10 GenuineIntel 2592 000000d600000000                   311b3dff
0: kd> !process 0 0 explorer.exe
PROCESS ffffc8064497b340
    SessionId: 1  Cid: 1038    Peb: 0090c000  ParentCid: 100c
    DirBase: beb3c000  ObjectTable: ffffa2827c3a1800  HandleCount: 2254.
    Image: explorer.exe

0: kd> .process /i /p ffffc8064497b340
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
0: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff805`2e1fd0b0 cc              int     3
0: kd> .reload
Connected to Windows 10 19041 x64 target at (Fri Nov 27 20:52:32.030 2020 (UTC - 5:00)), ptr64 TRUE
Loading Kernel Symbols
...............................................................
................................................................
...............................................................
Loading User Symbols
.............
Loading unloaded module list
.............
0: kd> dt nt!_KPROCESS @$proc DirectoryTableBase
   +0x028 DirectoryTableBase : 0xbeb3c000
0: kd> dt nt!_KPROCESS @$proc UserDirectoryTableBase
   +0x388 UserDirectoryTableBase : 0
0: kd> dt nt!_KPCR @$pcr Prcb.KernelDirectoryTableBase
   +0x180 Prcb                          : 
      +0x8e80 KernelDirectoryTableBase      : 0
0: kd> rdmsr c0000082
msr[c0000082] = fffff805`2e2066c0
0: kd> ln fffff805`2e2066c0
Browse module
Set bu breakpoint

(fffff805`2e2066c0)   nt!KiSystemCall64   |  (fffff805`2e206900)   nt!KiSystemServiceUser
Exact matches:
0: kd> ? nt!NtCreateFile
Evaluate expression: -8773842243440 = fffff805`2e3ff090
0: kd> !vtop 0xbeb3c000 0xfffff8052e3ff090
Amd64VtoP: Virt fffff8052e3ff090, pagedir 00000000beb3c000
Amd64VtoP: PML4E 00000000beb3cf80
Amd64VtoP: PDPE 0000000004b090a0
Amd64VtoP: PDE 0000000004b0ab88
Amd64VtoP: Large page mapped phys 0000000002dff090
Virtual address fffff8052e3ff090 translates to physical address 2dff090.
0: kd> r cr3
cr3=00000000beb3c000
0: kd> !pte nt!NtCreateFile
                                           VA fffff8052e3ff090
PXE at FFFFE5F2F97CBF80    PPE at FFFFE5F2F97F00A0    PDE at FFFFE5F2FE014B88    PTE at FFFFE5FC02971FF8
contains 0000000004B09063  contains 0000000004B0A063  contains 0A00000002C001A1  contains 0000000000000000
pfn 4b09      ---DA--KWEV  pfn 4b0a      ---DA--KWEV  pfn 2c00      -GL-A--KREV  LARGE PAGE pfn 2dff        

0: kd> !pte ntdll!NtCreateFile
                                           VA 00007ffc3608c830
PXE at FFFFE5F2F97CB7F8    PPE at FFFFE5F2F96FFF80    PDE at FFFFE5F2DFFF0D80    PTE at FFFFE5BFFE1B0460
contains 0A000000BC048867  contains 0A0000000604E867  contains 0A00000005350867  contains 010000006A1EC025
pfn bc048     ---DA--UWEV  pfn 604e      ---DA--UWEV  pfn 5350      ---DA--UWEV  pfn 6a1ec     ----A--UREV
</code></pre>

### Results
The page table lookup for `nt!NtCreateFile` fails for the user page table on the KVAS enabled system! This means KVAS is working just fine.

## Software SMEP
For the next test, I will show that Software SMEP is enforced at the top level of the page tables on a KVAS enabled system.  

I will resolve the address of the PML4 entry for `ntdll!NtCreateFile` for all page tables utilized via `!vtop`, then I will look at the page permissions applied using `dt -p`.  

### KVAS Enabled

<pre><code class="plaintext">1: kd> ? ntdll!NtCreateFile
Evaluate expression: 140729303091248 = 00007ffe`181ec830
1: kd> !vtop 0xbd6dd000 0x00007ffe181ec830
Amd64VtoP: Virt 00007ffe181ec830, pagedir 00000000bd6dd000
Amd64VtoP: PML4E 00000000bd6dd7f8
Amd64VtoP: PDPE 000000003f8eafc0
Amd64VtoP: PDE 000000003dff0600
Amd64VtoP: PTE 000000003dff1f60
Amd64VtoP: Mapped phys 00000001006b4830
Virtual address 7ffe181ec830 translates to physical address 1006b4830.
1: kd> !vtop 0xbd6de000 0x00007ffe181ec830
Amd64VtoP: Virt 00007ffe181ec830, pagedir 00000000bd6de000
Amd64VtoP: PML4E 00000000bd6de7f8
Amd64VtoP: PDPE 000000003f8eafc0
Amd64VtoP: PDE 000000003dff0600
Amd64VtoP: PTE 000000003dff1f60
Amd64VtoP: Mapped phys 00000001006b4830
Virtual address 7ffe181ec830 translates to physical address 1006b4830.
1: kd> dt -p nt!_MMPTE_HARDWARE @@(0x0000000bd6dd7f8)
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y1
   +0x000 Owner            : 0y1
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y0
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y1
   +0x000 PageFrameNumber  : 0y000000000000000000111111100011101010 (0x3f8ea)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y1010
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y0
1: kd> dt -p nt!_MMPTE_HARDWARE @@(0x00000000bd6de7f8)
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y1
   +0x000 Owner            : 0y1
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y0
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y1
   +0x000 PageFrameNumber  : 0y000000000000000000111111100011101010 (0x3f8ea)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y1010
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y1
</code></pre>

### KVAS Disabled

<pre><code class="plaintext">0: kd> ? ntdll!NtCreateFile
Evaluate expression: 140721215031344 = 00007ffc`3608c830
0: kd> !vtop 0xbeb3c000 0x00007ffc3608c830
Amd64VtoP: Virt 00007ffc3608c830, pagedir 00000000beb3c000
Amd64VtoP: PML4E 00000000beb3c7f8
Amd64VtoP: PDPE 00000000bc048f80
Amd64VtoP: PDE 000000000604ed80
Amd64VtoP: PTE 0000000005350460
Amd64VtoP: Mapped phys 000000006a1ec830
Virtual address 7ffc3608c830 translates to physical address 6a1ec830.
0: kd> dt -p nt!_MMPTE_HARDWARE @@(0x0000000beb3c7f8)
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y1
   +0x000 Owner            : 0y1
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y0
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y1
   +0x000 PageFrameNumber  : 0y000000000000000010111100000001001000 (0xbc048)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y1010
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y0
</code></pre>

### Results
The PML4 entry for the kernel page table has the `NoExecute` bit set for user mode addresses. Even if the processor does not support SMEP, an access violation will be thrown on attempted execution from kernel mode if the kernel page table is in `CR3`. The KVAS disabled system does not have separate page tables, so the user code must be executable.  

## KVAS Disabled in Privileged Processes
Next up is showing that KVAS is disabled for privileged/elevated processes.  

I will switch to a non-elevated instance of `cmd.exe` and look at `_KPROCESS.DirectoryTableBase`, `_KPROCESS.UserDirectoryTableBase`, `_KPROCESS.AddressPolicy`, `_KPRCB.KernelDirectoryTableBase`, and `_KPRCB.ShadowFlags` and then I will show the same fields when in the context of an elevated `cmd.exe` instance.

### Non-Elevated Process

<pre><code class="plaintext">0: kd> !process 0 0 cmd.exe
PROCESS ffffb68d5b96f080
    SessionId: 1  Cid: 0dd4    Peb: 100343000  ParentCid: 1098
    DirBase: 0785a002  ObjectTable: ffffde87d25062c0  HandleCount:  68.
    Image: cmd.exe

0: kd> .process /i /p ffffb68d5b96f080
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
0: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff804`745fd0b0 cc              int     3
1: kd> dt nt!_KPROCESS @$proc DirectoryTableBase UserDirectoryTableBase AddressPolicy
   +0x028 DirectoryTableBase     : 0x785a002
   +0x388 UserDirectoryTableBase : 0xbb659001
   +0x390 AddressPolicy          : 0 ''
1: kd> dt nt!_KPRCB @$prcb KernelDirectoryTableBase ShadowFlags
   +0x8e80 KernelDirectoryTableBase : 0x80000000`0785a002
   +0x8e98 ShadowFlags              : 1
</code></pre>

### Elevated Process

<pre><code class="plaintext">0: kd> !process 0 0 cmd.exe
PROCESS ffffb68d63bb7080
    SessionId: 1  Cid: 0a58    Peb: 52134af000  ParentCid: 1098
    DirBase: 8b073002  ObjectTable: ffffde87d250e100  HandleCount:  65.
    Image: cmd.exe

0: kd> .process /i /p ffffb68d63bb7080
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
0: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff804`745fd0b0 cc              int     3
1: kd> dt nt!_KPROCESS @$proc DirectoryTableBase UserDirectoryTableBase AddressPolicy
   +0x028 DirectoryTableBase     : 0x8b073002
   +0x388 UserDirectoryTableBase : 1
   +0x390 AddressPolicy          : 0x1 ''
1: kd> dt nt!_KPRCB @$prcb KernelDirectoryTableBase ShadowFlags
   +0x8e80 KernelDirectoryTableBase : 0x80000000`8b073002
   +0x8e98 ShadowFlags              : 2
</code></pre>

### Results
The non-elevated process has a `_KPROCESS.AddressPolicy` of 0 and the 1st bit of `_KPRCB.ShadowFlags` set. The elevated process does not have a valid `_KPROCESS.UserDirectoryTableBase`, has a `_KPROCESS.AddressPolicy` of 1, and has the 2nd bit set in `_KPRCB.ShadowFlags`.  

## Faults
For this section I will be testing the existence of software SMEP by running with permutations of not only KVAS enabled/disabled, but also with SMEP enabled/disabled. For each case, I have outlined an expected result for fun, let's see if my assumptions match up with reality!  

To test, I'll context switch to a KVAS enabled process (or any process on the KVAS disabled system), set the instruction pointer to executable code in user mode, then I'll single step and see what happens to the system in each case.  

### KVAS Enabled, SMEP Enabled
Expected result: fault on user mode page execution in kernel mode  

<pre><code class="plaintext">0: kd> !process 0 0 explorer.exe
PROCESS ffff848c6c231340
    SessionId: 1  Cid: 10b8    Peb: 00d61000  ParentCid: 1064
    DirBase: b3bd4002  ObjectTable: ffffc40b7e99ec00  HandleCount: 1684.
    Image: explorer.exe

0: kd> .process /i /p ffff848c6c231340
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
0: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff804`445fd0b0 cc              int     3
1: kd> .reload /user
Loading User Symbols
................................................................
................................................................
................................................................
................................................................
..........
1: kd> u kernel32+216e L1
KERNEL32!SortGetSortKey+0xede:
00007fff`a74c216e cc              int     3
1: kd> r rip=kernel32+216e
1: kd> p
KERNEL32!SortGetSortKey+0xedf:
00007fff`a74c216f fc              cld
1: kd> p
KDTARGET: Refreshing KD connection

*** Fatal System Error: 0x000000fc
                       (0x00007FFFA74C216F,0x0200000008782025,0xFFFFFB874D733940,0x0000000080000005)


A fatal system error has occurred.
Debugger entered on first try; Bugcheck callbacks have not been invoked.

A fatal system error has occurred.

nt!DbgBreakPointWithStatus:
fffff804`445fd0b0 cc              int     3
1: kd> g
Break instruction exception - code 80000003 (first chance)

A fatal system error has occurred.
Debugger entered on first try; Bugcheck callbacks have not been invoked.

A fatal system error has occurred.

nt!DbgBreakPointWithStatus:
fffff804`445fd0b0 cc              int     3
1: kd> !analyze -v
Connected to Windows 10 19041 x64 target at (Fri Nov 27 22:45:37.050 2020 (UTC - 5:00)), ptr64 TRUE
Loading Kernel Symbols
...............................................................
................................................................
.............................................................
Loading User Symbols
................................................................
................................................................
................................................................
................................................................
..........
Loading unloaded module list
................
*******************************************************************************
*                                                                             *
*                        Bugcheck Analysis                                    *
*                                                                             *
*******************************************************************************

ATTEMPTED_EXECUTE_OF_NOEXECUTE_MEMORY (fc)
An attempt was made to execute non-executable memory.  The guilty driver
is on the stack trace (and is typically the current instruction pointer).
When possible, the guilty driver's name (Unicode string) is printed on
the bugcheck screen and saved in KiBugCheckDriver.
Arguments:
Arg1: 00007fffa74c216f, Virtual address for the attempted execute.
Arg2: 0200000008782025, PTE contents.
Arg3: fffffb874d733940, (reserved)
Arg4: 0000000080000005, (reserved)
</code></pre>

### KVAS Disabled, SMEP Enabled
Expected result: fault on user mode page execution in kernel mode  

<pre><code class="plaintext">0: kd> !process 0 0 explorer.exe
PROCESS ffff9787d1477080
    SessionId: 1  Cid: 10ac    Peb: 01182000  ParentCid: 1094
    DirBase: b2f75000  ObjectTable: ffff8601a3fc3200  HandleCount: 1911.
    Image: explorer.exe

0: kd> .process /i /p ffff9787d1477080
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
0: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff801`2a9fd0b0 cc              int     3
1: kd> .reload /user
Loading User Symbols
................................................................
................................................................
................................................................
..............................................................
1: kd> u kernel32+216e L1
KERNEL32!SortGetSortKey+0xede:
00007ffb`a752216e cc              int     3
1: kd> r rip=kernel32+216e
1: kd> p
KERNEL32!SortGetSortKey+0xedf:
00007ffb`a752216f fc              cld
1: kd> p
KDTARGET: Refreshing KD connection

*** Fatal System Error: 0x000000fc
                       (0x00007FFBA752216F,0x010000000A8B1025,0xFFFFED060F7F0940,0x0000000080000005)


A fatal system error has occurred.
Debugger entered on first try; Bugcheck callbacks have not been invoked.

A fatal system error has occurred.

nt!DbgBreakPointWithStatus:
fffff801`2a9fd0b0 cc              int     3
1: kd> g
Break instruction exception - code 80000003 (first chance)

A fatal system error has occurred.
Debugger entered on first try; Bugcheck callbacks have not been invoked.

A fatal system error has occurred.

nt!DbgBreakPointWithStatus:
fffff801`2a9fd0b0 cc              int     3
1: kd> !analyze -v
Connected to Windows 10 19041 x64 target at (Fri Nov 27 22:48:37.554 2020 (UTC - 5:00)), ptr64 TRUE
Loading Kernel Symbols
...............................................................
................................................................
.............................................................
Loading User Symbols
................................................................
................................................................
................................................................
..............................................................
Loading unloaded module list
..............
*******************************************************************************
*                                                                             *
*                        Bugcheck Analysis                                    *
*                                                                             *
*******************************************************************************

ATTEMPTED_EXECUTE_OF_NOEXECUTE_MEMORY (fc)
An attempt was made to execute non-executable memory.  The guilty driver
is on the stack trace (and is typically the current instruction pointer).
When possible, the guilty driver's name (Unicode string) is printed on
the bugcheck screen and saved in KiBugCheckDriver.
Arguments:
Arg1: 00007ffba752216f, Virtual address for the attempted execute.
Arg2: 010000000a8b1025, PTE contents.
Arg3: ffffed060f7f0940, (reserved)
Arg4: 0000000080000005, (reserved)
</code></pre>

### KVAS Enabled, SMEP Disabled
Expected result: fault on user mode page execution in kernel mode via Software SMEP  

<pre><code class="plaintext">0: kd> !process 0 0 explorer.exe
PROCESS ffffd18ad3a31340
    SessionId: 1  Cid: 0acc    Peb: 00c3c000  ParentCid: 0d20
    DirBase: 3f159002  ObjectTable: ffffac865a3e3780  HandleCount: 1667.
    Image: explorer.exe

0: kd> .process /i /p ffffd18ad3a31340
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
1: kd> .reload /user
Loading User Symbols
................................................................
................................................................
................................................................
................................................................


************* Symbol Loading Error Summary **************
Module name            Error
SharedUserData         No error - symbol load deferred

You can troubleshoot most symbol related issues by turning on symbol loading diagnostics (!sym noisy) and repeating the command that caused symbols to be loaded.
You should also verify that your symbol search path (.sympath) is correct.
1: kd> u kernel32+216e L1
KERNEL32!SortGetSortKey+0xede:
00007ff9`abfd216e cc              int     3
1: kd> r rip=kernel32+216e
1: kd> r cr4=@@C++(@cr4 & ~(1<<20))
1: kd> p
KERNEL32!SortGetSortKey+0xedf:
00007ff9`abfd216f fc              cld
1: kd> p
KDTARGET: Refreshing KD connection

*** Fatal System Error: 0x000000fc
                       (0x00007FF9ABFD216F,0x030000000F670025,0xFFFF9884AB7F0940,0x0000000080000005)


A fatal system error has occurred.
Debugger entered on first try; Bugcheck callbacks have not been invoked.

A fatal system error has occurred.

nt!DbgBreakPointWithStatus:
fffff803`753fd0b0 cc              int     3
1: kd> !analyze -v
The debuggee is ready to run
1: kd> !analyze -v
The debuggee is ready to run
1: kd> g
Break instruction exception - code 80000003 (first chance)

A fatal system error has occurred.
Debugger entered on first try; Bugcheck callbacks have not been invoked.

A fatal system error has occurred.

nt!DbgBreakPointWithStatus:
fffff803`753fd0b0 cc              int     3
1: kd> !analyze -v
Connected to Windows 10 19041 x64 target at (Fri Nov 27 22:40:28.176 2020 (UTC - 5:00)), ptr64 TRUE
Loading Kernel Symbols
...............................................................
................................................................
.............................................................
Loading User Symbols
................................................................
................................................................
................................................................
................................................................

Loading unloaded module list
.............................

************* Symbol Loading Error Summary **************
Module name            Error
SharedUserData         No error - symbol load deferred

You can troubleshoot most symbol related issues by turning on symbol loading diagnostics (!sym noisy) and repeating the command that caused symbols to be loaded.
You should also verify that your symbol search path (.sympath) is correct.
*******************************************************************************
*                                                                             *
*                        Bugcheck Analysis                                    *
*                                                                             *
*******************************************************************************

ATTEMPTED_EXECUTE_OF_NOEXECUTE_MEMORY (fc)
An attempt was made to execute non-executable memory.  The guilty driver
is on the stack trace (and is typically the current instruction pointer).
When possible, the guilty driver's name (Unicode string) is printed on
the bugcheck screen and saved in KiBugCheckDriver.
Arguments:
Arg1: 00007ff9abfd216f, Virtual address for the attempted execute.
Arg2: 030000000f670025, PTE contents.
Arg3: ffff9884ab7f0940, (reserved)
Arg4: 0000000080000005, (reserved)
</code></pre>

### KVAS Disabled, SMEP Disabled
Expected result: successful execution in a user mode page  

<pre><code class="plaintext">0: kd> !process 0 0 explorer.exe
PROCESS ffff840ec792c340
    SessionId: 1  Cid: 1050    Peb: 00380000  ParentCid: 1024
    DirBase: b2f4f000  ObjectTable: ffff948cdda96d40  HandleCount: 1952.
    Image: explorer.exe

0: kd> .process /i /p ffff840ec792c340
You need to continue execution (press 'g' <enter>) for the context
to be switched. When the debugger breaks in again, you will be in
the new process context.
0: kd> g
Break instruction exception - code 80000003 (first chance)
nt!DbgBreakPointWithStatus:
fffff806`743fd0b0 cc              int     3
1: kd> .reload /user
Loading User Symbols
................................................................
................................................................
................................................................
..............................................................
1: kd> r rip=kernel32+216e
1: kd> u kernel32+216e
KERNEL32!SortGetSortKey+0xede:
00007ff8`b5a0216e cc              int     3
00007ff8`b5a0216f fc              cld
00007ff8`b5a02170 ff              ???
00007ff8`b5a02171 ff418b          inc     dword ptr [rcx-75h]
00007ff8`b5a02174 c24d8d          ret     8D4Dh
00007ff8`b5a02177 3c44            cmp     al,44h
00007ff8`b5a02179 0f1f8000000000  nop     dword ptr [rax]
00007ff8`b5a02180 418d0413        lea     eax,[r11+rdx]
1: kd> u kernel32+216e L1
KERNEL32!SortGetSortKey+0xede:
00007ff8`b5a0216e cc              int     3
1: kd> r cr4=@@C++(@cr4 & ~(1<<20))
1: kd> p
KERNEL32!SortGetSortKey+0xedf:
00007ff8`b5a0216f fc              cld
1: kd> p
00007ff8`b5a02170 ff              ???
</code></pre>

**No crash!!**

### Results
As expected, all tests but the last caused a crash immediately. Interestingly, the CPU executed the breakpoint instruction and crashed on the next instruction on every test that crashed. Instruction caching? Or just how the CPU is designed. Very interesting!  

<center>
![noexecute]({static}/images/windows-10-kvas-and-software-smep/noexecute.png)  
<small>:(</small>
</center>

# Wrap up
I hope you've learned a thing or two from this. I've been wanting to do this investigation for a while, just to nail down the implementation details here. If you have questions feel free to reach out on Twitter [@jgeigerm](https://twitter.com/jgeigerm). For now and as always ~~h a v e f u n i n s i d e~~.  

## Bonus: WinDbg Bug
There's a bug in the `dt` command where it sign extends bit 31 on 64-bit values making it impossible to do `dt -p` on some values:  

<pre><code class="plaintext">1: kd> dt -p nt!_MMPTE_HARDWARE 0x0000000bd6de7f8
   +0x000 Valid            : ??
   +0x000 Dirty1           : ??
   +0x000 Owner            : ??
   +0x000 WriteThrough     : ??
   +0x000 CacheDisable     : ??
   +0x000 Accessed         : ??
   +0x000 Dirty            : ??
   +0x000 LargePage        : ??
   +0x000 Global           : ??
   +0x000 CopyOnWrite      : ??
   +0x000 Unused           : ??
   +0x000 Write            : ??
   +0x000 PageFrameNumber  : ??
   +0x000 ReservedForHardware : ??
   +0x000 ReservedForSoftware : ??
   +0x000 WsleAge          : ??
   +0x000 WsleProtection   : ??
   +0x000 NoExecute        : ??
Memory read error ffffffffbd6de7f8
</code></pre>

Totally bogus! The solution I found was to wrap the value in the MASM or C++ interpreter:  

<pre><code class="plaintext">1: kd> dt -p nt!_MMPTE_HARDWARE @@C++(0x00000000bd6de7f8)
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y1
   +0x000 Owner            : 0y1
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y0
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y1
   +0x000 PageFrameNumber  : 0y000000000000000000111111100011101010 (0x3f8ea)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y1010
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y1
1: kd> dt -p nt!_MMPTE_HARDWARE @@(0x00000000bd6de7f8)
   +0x000 Valid            : 0y1
   +0x000 Dirty1           : 0y1
   +0x000 Owner            : 0y1
   +0x000 WriteThrough     : 0y0
   +0x000 CacheDisable     : 0y0
   +0x000 Accessed         : 0y1
   +0x000 Dirty            : 0y1
   +0x000 LargePage        : 0y0
   +0x000 Global           : 0y0
   +0x000 CopyOnWrite      : 0y0
   +0x000 Unused           : 0y0
   +0x000 Write            : 0y1
   +0x000 PageFrameNumber  : 0y000000000000000000111111100011101010 (0x3f8ea)
   +0x000 ReservedForHardware : 0y0000
   +0x000 ReservedForSoftware : 0y0000
   +0x000 WsleAge          : 0y1010
   +0x000 WsleProtection   : 0y000
   +0x000 NoExecute        : 0y1
</code></pre>

## Other resources I didn't find a place for but still wanted to include
* Using KVAS to hide from KPP checks: [https://www.cyfyx.com/2019/01/melting-down-patchguard-leveraging-kpti-to-bypass-kernel-patch-protection/](https://www.cyfyx.com/2019/01/melting-down-patchguard-leveraging-kpti-to-bypass-kernel-patch-protection/)  
* Considerations for exploits: [https://zerosum0x0.blogspot.com/2019/11/fixing-remote-windows-kernel-payloads-meltdown.html](https://zerosum0x0.blogspot.com/2019/11/fixing-remote-windows-kernel-payloads-meltdown.html)  
