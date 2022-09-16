Title: Finding the Base of the Windows Kernel
Date: 2022-09-15 12:00
Category: System Internals
Tags: windows, windows-kernel, windows-internals, programming
Slug: finding-the-base-of-the-windows-kernel
Authors: wumb0

Recently-ish (~2020), Microsoft changed the way the kernel image is mapped and also some implementation details of hal.dll. The kernel changes have caused existing methods of finding the base of the kernel via shellcode or a leak and arbitrary read to crash. This obviously isn't great, so I decided to figure out a way around the issue to support some code I've been writing in my free time (maybe more on that later).  

Our discussion is going to start at Windows 10 1903 and then move up through Windows 10 21H2. These changes are also still present in Windows 11. 

# What's the point(er)?
Finding the base of the kernel is important for kernel exploits and kernel shellcode. If you can find the base of the kernel you can look up functions inside of it via the export table in its [PE header](https://upload.wikimedia.org/wikipedia/commons/1/1b/Portable_Executable_32_bit_Structure_in_SVG_fixed.svg). Various functions inside of the kernel allow you to [allocate memory](https://docs.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-exallocatepoolwithtag), [start threads](https://docs.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-pscreatesystemthread), and resolve other kernel module bases via the [PsLoadedModuleList](https://m0uk4.gitbook.io/notebooks/mouka/windowsinternal/find-kernel-module-address-todo). Without being able to utilize kernel routines and symbols, you're pretty limited in what you can do if you're executing in kernel. Hopefully this clarifies why this post is even necessary.

[[more]]

# Literature Review: Existing Methods
In order to understand where I am going with all of this, we first need to look at what techniques are already out there. This is split up into three parts: how to get to the base of the kernel, obtaining (*"leaking"*) a kernel address to be used to find the base, and how to do version detection in kernel.  

## Getting to Kernel Base
Two of these methods rely on having some kind of memory leak of a kernel address, one does not. They really all have the same goal: to locate the base of the kernel.  

<div class="uk-alert">
    <i class="fa fa-info-circle fa-lg"></i><span class="alert-text">All of these techniques apply to any PE file, not just the kernel.</span>
</div>

### NtQuerySystemInformation
The easiest and most version independent way to get the base of the kernel and all other kernel modules as via [`NtQuerySystemInformation`](https://docs.microsoft.com/en-us/windows/win32/sysinfo/zwquerysysteminformation) using the `SystemModuleInformation` (0xB) member of the [`SYSTEM_INFORMATION_CLASS`](https://www.geoffchappell.com/studies/windows/km/ntoskrnl/api/ex/sysinfo/class.htm) enumeration. When queried (with an appropriate buffer size), the function will return a filled out [`SYSTEM_MODULE_INFORMATION`](https://undocumented.ntinternals.net/index.html?page=UserMode%2FStructures%2FSYSTEM_MODULE_INFORMATION.html) structure that contains a DWORD for the number of modules present and then an anysize array of [`SYSTEM_MODULE`](http://undocumented.ntinternals.net/index.html?page=UserMode%2FStructures%2FSYSTEM_MODULE.html) structures representing the modules. [Here's some C code](https://github.com/sam-b/windows_kernel_address_leaks/blob/master/NtQuerySysInfo_SystemModuleInformation/NtQuerySysInfo_SystemModuleInformation/NtQuerySysInfo_SystemModuleInformation.cpp) that uses it to query driver names and bases. You can actually get the base addresses and names of every kernel module via some documented APIs too: [`EnumDeviceDrivers`](https://docs.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-enumdevicedrivers) and [`GetDeviceDriverBaseNameA`](https://docs.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getdevicedriverbasenamea) from the [PSAPI](https://docs.microsoft.com/en-us/windows/win32/api/psapi/) can be used together in order to accomplish that. On the backend they use `NtQuerySystemInformation` with the `SystemModuleInformation` class. FYI, psapi is just a small stub around the [API set](https://docs.microsoft.com/en-us/windows/win32/apiindex/windows-apisets) DLL `api-ms-win-core-psapi-l1-1-0.dll`, which ends up forwarding to kernelbase.dll in all versions.  

<center>
![kernelbase!EnumDeviceDrivers]({static}/images/all-your-base-are-belong-to-us/psapi-qsi.png)  
<small>A portion of `kernelbase!EnumDeviceDrivers` showing a call to `NtQuerySystemInformation`</small>
</center>

`GetDeviceDriverBaseNameA` calls the unexported `kernel32!FindDeviceDriver` function, which again calls `NtQuerySystemInformation` with the `SystemModuleInformation` class.  

### Scan Backwards
In the event we cannot get any information from user-mode or we are in a [low-integrity process](https://docs.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control), then the scanback technique can be used. Basically, we need a memory leak or reliable way of getting a kernel address to get in the "ballpark" of the kernel image. See the next section on "leaking" kernel addresses for more details on that. Once we have an address somewhere in the kernel, we can scan backwards one page (0x1000 bytes) at a time until we get to the PE header of the kernel image. This trick relies on two major assumptions:  

1. PE images are page aligned  
2. The memory space between the leaked address and the base of the kernel is contiguously mapped  

We will see later that #2 isn't true on newer versions of Windows.

Every PE file starts with the bytes `MZ` (0x5a4d). To see if we have reached the beginning of the PE file, we can check to see if the page starts with `MZ`. If it does not, continue scanning back, if it does, then you have (probably) found the base of the image. I recommend doing a little bit more validation than that, such as seeing if the suspected base address + [`IMAGE_DOS_HEADER.e_lfanew`](https://www.nirsoft.net/kernel_struct/vista/IMAGE_DOS_HEADER.html) contains the bytes `PE` (0x4550).  

If you're interested in a code implementation of this technique, here's [some code](https://github.com/wumb0/zerosum0x0_SassyKitdi/blob/master/src/common/resolver/src/lib.rs#L45) from [zerosum0x0](https://twitter.com/zerosum0x0).  

### Relative Virtual Address (RVA)
The lamest of the kernel base finding methods is just to hard code the Relative Virtual Address (RVA) of the leaked symbol into your shellcode or exploit. This requires knowing the exact version(s) your code will be running on ahead of time and also requires version detection to support multiple versions of the kernel.  

A slight variation on this method is to use an exported symbol from the leaked module to calculate its base. You can open the image file in user-mode and then look up the exported symbol to get its offset from the base address. This can be accomplished with [`LoadLibraryA`](https://docs.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibrarya) and [`GetProcAddress`](https://docs.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getprocaddress). You can also do manual PE parsing. However, loading something like the kernel image into a user-mode process is pretty suspicious. You'll also need a way to pass the calculated RVA into your exploit or shellcode.  

## "Leaking" Kernel Addresses
To get a kernel address from an exploit you usually have to have a memory leak (information disclosure). When you're already executing via shellcode you have more options, but you still need to find a pointer into the kernel or another module to utilize the techniques above.  

### KPCR
Each logical processor on a Windows system has an associated structure called the Kernel Processor Control Region (KPCR). The KPCR is a **massive** structure, coming in at 0xC000 bytes as of the Windows 11 Beta. The first 0x180 bytes are [almost](https://www.vergiliusproject.com/kernels/x64/Windows%20XP%20|%202003/SP2/_KPCR) [entirely](https://www.vergiliusproject.com/kernels/x64/Windows%207%20|%202008R2/SP1/_KPCR) [consistent](https://www.vergiliusproject.com/kernels/x64/Windows%208.1%20|%202012R2/Update%201/_KPCR) [across](https://www.vergiliusproject.com/kernels/x64/Windows%2010%20|%202016/1809%20Redstone%205%20(October%20Update)/_KPCR) [versions](https://www.vergiliusproject.com/kernels/x64/Windows%2011/Insider%20Preview%20(Jun%202021)/_KPCR). At offset 0x180 lies the nested Kernel Processor Region Control Block (KPRCB) structure, which is very large and the reason that the KPCR is as large as it is. Members are added when major features (like [KVAS]({filename}/posts/windows-10-kvas-and-software-smep.md)) are added to the OS.  

On 64-bit Windows, the GS segment register points to the KPCR for that processor. The `swapgs` instruction at kernel entry points (such as the system call handler, `KiSystemCall64\[Shadow\]`, and Interrupt Service Routines (ISRs)) causes the processor to swap the contents of Model Specific Register (MSR) 0xC0000101 (GSBASE) with MSR 0xC0000102 (KERNEL_GSBASE). GSBASE is also the contents of the GS segment register. On 32-bit, 0x30 is explicitly loaded into FS at kernel entry points, and the GDT entry at offset 0x30 defines the base as the address of the KPCR for that processor.  

<div class="uk-grid">
    <div class="uk-width-medium-1-2 uk-width-small-1-1">
        <center><img style="width: 75%;" alt="nt!KiKernelSysretExit" src="{static}/images/all-your-base-are-belong-to-us/gs-swap.png" /></center>
        <center><small><code>swapgs</code> at the 64-bit kernel entrypoint</small></center>
    </div>
    <div class="uk-width-medium-1-2 uk-width-small-1-1">
        <center><img style="width: 75%;" alt="nt!KiKernelSysretExit" src="{static}/images/all-your-base-are-belong-to-us/fs-swap.png" /></center>
        <center><small>Moving 0x30 into FS at the 32-bit kernel entrypoint</small></center>
    </div>
</div>

Both the upper members of the KPCR and the KPRCB have pointers into the kernel and other modules that might be of use to use while trying to calculate where exactly the kernel is located. The issue with the KPRCB is that fields change frequently, so the offset to a particular field of interest would be very version dependent.  

#### Interrupt Descriptor Table
One classic and consistent place to find reliable pointers into the kernel in the KPCR is in the [Interrupt Descriptor Table](https://wiki.osdev.org/Interrupt_Descriptor_Table) (IDT). The KPCR has a pointer to the IDT at offset 0x38, the `IdtBase` field. Dumping out quad words (with symbols) at that address gives some pointers into the kernel!  

<pre><code class="plaintext">0: kd> dqs poi(@$pcr+38)+4
fffff802`35d8b004  fffff802`39448e00 nt!KiDebugServiceTrap+0x40
fffff802`35d8b00c  00102a40`00000000
fffff802`35d8b014  fffff802`39448e04 nt!KiDebugServiceTrap+0x44
fffff802`35d8b01c  00103040`00000000
fffff802`35d8b024  fffff802`39448e03 nt!KiDebugServiceTrap+0x43
fffff802`35d8b02c  001035c0`00000000
fffff802`35d8b034  fffff802`3944ee00 nt! ?? ::FNODOBFM::`string'+0x10
fffff802`35d8b03c  00103900`00000000
fffff802`35d8b044  fffff802`3944ee00 nt! ?? ::FNODOBFM::`string'+0x10
fffff802`35d8b04c  00103c40`00000000
fffff802`35d8b054  fffff802`39448e00 nt!KiDebugServiceTrap+0x40
fffff802`35d8b05c  00104180`00000000
fffff802`35d8b064  fffff802`39448e00 nt!KiDebugServiceTrap+0x40
fffff802`35d8b06c  00104680`00000000
fffff802`35d8b074  fffff802`39448e00 nt!KiDebugServiceTrap+0x40
fffff802`35d8b07c  00104a40`00000000
</code></pre>

If you look a bit lower in the code from zerosum0x0 that I linked earlier you can see this is [exactly the method being used](https://github.com/wumb0/zerosum0x0_SassyKitdi/blob/master/src/common/resolver/src/lib.rs#L65) to get a kernel address.  

#### KTHREAD Pointers
One of the fields in the KPRCB that is consistent across versions of the kernel is the `CurrentThread` field at offset 8. This would be at the KPCR at offset 0x188 (x64). In fact, you'll see this offset repeatedly in the kernel, as this is what the kernel uses to get a pointer to the current thread running on the processor.  

<center>
![nt!KiKernelSysretExit]({static}/images/all-your-base-are-belong-to-us/gs188.png)  
<small>Here's an example from `KiKernelSysretExit`, which might look [familiar]({static}/images/windows-10-kvas-and-software-smep/KiKernelSysretExit.png) from my [KVAS post]({filename}/posts/windows-10-kvas-and-software-smep.md)</small>
</center>

If we dump pointers with symbols (`dps`) at the current thread over the size of KTHREAD, we can see many pointers into the kernel!

<details open>
<summary>Pointers in KTHREAD (system thread)</summary>
<pre><code class="plaintext">0: kd> dps @$thread L@@C++(sizeof(nt!_KTHREAD)/8)
fffff802`39d4abc0  00000000`00200006
fffff802`39d4abc8  fffff802`39d4abc8 nt!KiInitialThread+0x8
fffff802`39d4abd0  fffff802`39d4abc8 nt!KiInitialThread+0x8
fffff802`39d4abd8  00000000`00000000
fffff802`39d4abe0  00000000`0791ddc0
fffff802`39d4abe8  fffff802`35d97c70
fffff802`39d4abf0  fffff802`35d92000
fffff802`39d4abf8  fffff802`35d98000
fffff802`39d4ac00  00000000`00000000
fffff802`39d4ac08  000000d2`4507715b
fffff802`39d4ac10  00000000`ffffffff
fffff802`39d4ac18  fffff802`35d97c00
fffff802`39d4ac20  fffff802`35d97cc0
fffff802`39d4ac28  00000000`00000000
fffff802`39d4ac30  00000409`00000100
fffff802`39d4ac38  00080000`00020044
fffff802`39d4ac40  00000000`00000000
fffff802`39d4ac48  00000000`00000000
fffff802`39d4ac50  00000000`00000000
fffff802`39d4ac58  fffff802`39d4ac58 nt!KiInitialThread+0x98
fffff802`39d4ac60  fffff802`39d4ac58 nt!KiInitialThread+0x98
fffff802`39d4ac68  fffff802`39d4ac68 nt!KiInitialThread+0xa8
fffff802`39d4ac70  fffff802`39d4ac68 nt!KiInitialThread+0xa8
fffff802`39d4ac78  ffffe70e`4e4a5040
fffff802`39d4ac80  00000000`00000000
fffff802`39d4ac88  00000000`00000000
fffff802`39d4ac90  00000000`00000000
fffff802`39d4ac98  00000000`00000000
fffff802`39d4aca0  00000000`00000000
fffff802`39d4aca8  00000000`00000000
fffff802`39d4acb0  00000000`00000000
fffff802`39d4acb8  00000000`00000000
fffff802`39d4acc0  00000000`00000008
fffff802`39d4acc8  fffff802`39d4ad90 nt!KiInitialThread+0x1d0
fffff802`39d4acd0  fffff802`39d4ad90 nt!KiInitialThread+0x1d0
fffff802`39d4acd8  00000000`00000000
fffff802`39d4ace0  00000000`00000000
fffff802`39d4ace8  00000000`00000000
fffff802`39d4acf0  6851f04c`965c27f1
fffff802`39d4acf8  00000000`00000000
fffff802`39d4ad00  00000000`00000000
fffff802`39d4ad08  00000000`00000000
fffff802`39d4ad10  00038a7a`00000401
fffff802`39d4ad18  fffff802`39d4abc0 nt!KiInitialThread
fffff802`39d4ad20  ffffe70e`506fcd88
fffff802`39d4ad28  00000000`00000000
fffff802`39d4ad30  00000000`00000000
fffff802`39d4ad38  00000000`00000000
fffff802`39d4ad40  00020002`00000000
fffff802`39d4ad48  fffff802`39d4abc0 nt!KiInitialThread
fffff802`39d4ad50  00000000`00000000
fffff802`39d4ad58  00000000`00000000
fffff802`39d4ad60  00000000`00000000
fffff802`39d4ad68  00000000`00000000
fffff802`39d4ad70  00014f81`00000000
fffff802`39d4ad78  fffff802`39d4abc0 nt!KiInitialThread
fffff802`39d4ad80  00000000`00000000
fffff802`39d4ad88  00000000`00000000
fffff802`39d4ad90  fffff802`39d4acc8 nt!KiInitialThread+0x108
fffff802`39d4ad98  fffff802`39d4acc8 nt!KiInitialThread+0x108
fffff802`39d4ada0  00000000`01020401
fffff802`39d4ada8  fffff802`39d4abc0 nt!KiInitialThread
fffff802`39d4adb0  00000000`00000000
fffff802`39d4adb8  00000000`00000000
fffff802`39d4adc0  00000000`00000000
fffff802`39d4adc8  00000000`00000000
fffff802`39d4add0  00000000`00000000
fffff802`39d4add8  00000000`00000000
fffff802`39d4ade0  fffff802`39d47ac0 nt!KiInitialProcess
fffff802`39d4ade8  fffff802`39d1db90 nt!KiBootProcessorIdleThreadUserAffinity
fffff802`39d4adf0  00000000`00000000
fffff802`39d4adf8  00000000`00000014
fffff802`39d4ae00  fffff802`39d21cc0 nt!KiBootProcessorIdleThreadAffinity
fffff802`39d4ae08  00000000`00010000
fffff802`39d4ae10  00000000`00000004
fffff802`39d4ae18  fffff802`39d4ae18 nt!KiInitialThread+0x258
fffff802`39d4ae20  fffff802`39d4ae18 nt!KiInitialThread+0x258
fffff802`39d4ae28  fffff802`39d4ae28 nt!KiInitialThread+0x268
fffff802`39d4ae30  fffff802`39d4ae28 nt!KiInitialThread+0x268
fffff802`39d4ae38  fffff802`39d47ac0 nt!KiInitialProcess
fffff802`39d4ae40  00000000`19000000
fffff802`39d4ae48  00006804`7f580012
fffff802`39d4ae50  fffff802`39d4abc0 nt!KiInitialThread
fffff802`39d4ae58  00000000`00000000
fffff802`39d4ae60  00000000`00000000
fffff802`39d4ae68  fffff802`393b2170 nt!EmpCheckErrataList
fffff802`39d4ae70  fffff802`393b2170 nt!EmpCheckErrataList
fffff802`39d4ae78  fffff802`39337ac0 nt!KiSchedulerApc
fffff802`39d4ae80  fffff802`39d4abc0 nt!KiInitialThread
fffff802`39d4ae88  00000000`00000000
fffff802`39d4ae90  00000000`00000000
fffff802`39d4ae98  00000000`00000000
fffff802`39d4aea0  00000001`00060000
fffff802`39d4aea8  fffff802`39d4aea8 nt!KiInitialThread+0x2e8
fffff802`39d4aeb0  fffff802`39d4aea8 nt!KiInitialThread+0x2e8
fffff802`39d4aeb8  ffffe70e`4e535378
fffff802`39d4aec0  fffff802`39d47af0 nt!KiInitialProcess+0x30
fffff802`39d4aec8  fffff802`39d4aec8 nt!KiInitialThread+0x308
fffff802`39d4aed0  fffff802`39d4aec8 nt!KiInitialThread+0x308
fffff802`39d4aed8  00000000`0000003f
...
</code></pre>
</details>

Now for consistency's sake, I'm going to explicitly dump out the same information from a user-mode thread, cmd.exe in this case.  

<details open>
<summary>Pointers in KTHREAD (user thread)</summary>
<pre><code class="plaintext">0:kd> dps ffffe70e57dee0c0 L@@C++(sizeof(nt!_KTHREAD)/8)
ffffe70e`57dee0c0  00000000`00a00006
ffffe70e`57dee0c8  ffffe70e`57dee0c8
ffffe70e`57dee0d0  ffffe70e`57dee0c8
...
ffffe70e`57dee350  ffffe70e`57dee0c0
ffffe70e`57dee358  ffffe70e`552eaf50
ffffe70e`57dee360  ffffe70e`57dee158
ffffe70e`57dee368  fffff802`393b2170 nt!EmpCheckErrataList
ffffe70e`57dee370  fffff802`393b2170 nt!EmpCheckErrataList
ffffe70e`57dee378  fffff802`39337ac0 nt!KiSchedulerApc
ffffe70e`57dee380  ffffe70e`57dee0c0
ffffe70e`57dee388  00000000`00000000
...
</code></pre>
</details>

The output was shortened in places that did not have kernel pointers. Notice there are only three kernel pointers in this thread! The two different functions and their offsets into KTHREAD are consistent between the system thread and the user thread. If you check any thread, you will find that these pointers are present. What are these three fields? The offset into KTHREAD to the first `nt!EmpCheckErrataList` pointer is 0x2a8 (0xffffe70e57dee368-0xffffe70e57dee0c0). Dumping out KTHREAD gives the answer!  

<pre><code class="plaintext">0: kd> dt -v -r1 _KTHREAD @$thread
nt!_KTHREAD
struct _KTHREAD, 225 elements, 0x480 bytes
   +0x000 Header           : struct _DISPATCHER_HEADER, 59 elements, 0x18 bytes
...
   +0x288 SchedulerApc     : struct _KAPC, 19 elements, 0x58 bytes
      +0x000 Type             : 0x12 ''
      +0x001 AllFlags         : 0 ''
      +0x001 CallbackDataContext : Bitfield 0y0
      +0x001 Unused           : Bitfield 0y0000000 (0)
      +0x002 Size             : 0x58 'X'
      +0x003 SpareByte1       : 0x7f ''
      +0x004 SpareLong0       : 0x6804
      +0x008 Thread           : 0xfffff802`39d4abc0 struct _KTHREAD, 225 elements, 0x480 bytes
      +0x010 ApcListEntry     : struct _LIST_ENTRY, 2 elements, 0x10 bytes
 [ 0x00000000`00000000 - 0x00000000`00000000 ]
      +0x020 KernelRoutine    : 0xfffff802`393b2170        void  nt!EmpCheckErrataList+0
      +0x028 RundownRoutine   : 0xfffff802`393b2170        void  nt!EmpCheckErrataList+0
      +0x030 NormalRoutine    : 0xfffff802`39337ac0        void  nt!KiSchedulerApc+0
      +0x020 Reserved         : [3] 0xfffff802`393b2170 Void
      +0x038 NormalContext    : 0xfffff802`39d4abc0 Void
      +0x040 SystemArgument1  : (null) 
      +0x048 SystemArgument2  : (null) 
      +0x050 ApcStateIndex    : 0 ''
      +0x051 ApcMode          : 0 ''
      +0x052 Inserted         : 0 ''
   +0x288 SchedulerApcFill1 : [3]  "???"
   +0x28b QuantumReset     : 0x7f ''
   +0x288 SchedulerApcFill2 : [4]  "???"
   +0x28c KernelTime       : 0x6804
   +0x288 SchedulerApcFill3 : [64]  "???"
   +0x2c8 WaitPrcb         : (null) 
   +0x288 SchedulerApcFill4 : [72]  "???"
...
</code></pre>

<div class="uk-alert">
    <i class="fa fa-info-circle fa-lg"></i><span class="alert-text">The <code>dt</code> WinDbg command has a lot of useful options. <code>-v</code> and <code>-r</code> (used above) show sizes for fields and recurse through nested structures, respectively. Check out the <a href="https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/dt--display-type-">docs</a> for more options and info!</span>
</div>

The fields are the `KernelRoutine`, `RundownRoutine`, and `NormalRoutine` function pointers in the `SchedulerApc` member of KTHREAD. These offsets have been consistent since [Windows 8 RTM](https://www.vergiliusproject.com/kernels/x64/Windows%208%20|%202012/RTM/_KTHREAD) where the name of the field was changed from `SuspendApc` to `SchedulerApc`. Unfortunately, these function pointers seem to have been removed from Windows 21H1, probably to prevent this kind of disclosure. Of course you can just go back to the old versions to get the true use, since they are still present in newer Windows versions.  

It's worth noting that I'm not the first one to discover this. Pages 20 and 21 of [Morten Schenk's 2017 BlackHat briefing paper](https://www.blackhat.com/docs/us-17/wednesday/us-17-Schenk-Taking-Windows-10-Kernel-Exploitation-To-The-Next-Level%E2%80%93Leveraging-Write-What-Where-Vulnerabilities-In-Creators-Update-wp.pdf) show that if you have a pointer to KTHREAD, then you can reliably get pointers into the kernel (hence why this is in the literature review section).    

### LSTAR MSR
When a [`syscall`](https://www.felixcloutier.com/x86/syscall.html) instruction is executed, the processor jumps to the address contained in the LSTAR Model Specific Register (MSR) (0xC0000082) after transitioning into kernel mode. This is not Windows specific behavior, as it is defined in the Intel Manual (Volume 2B, Chapter 4.3, SYSCALL). The system call handlers are unsurprisingly located in the kernel image, so if you can execute a [`rdmsr`](https://www.felixcloutier.com/x86/rdmsr), you can get a pointer into the kernel. Of course this technique is only useful for shellcode or if you are somehow already executing in kernel.  

With the introduction of KVAS, all of the kernel entry points were moved into a section in the kernel called `KVASCODE`. This section is present in both the user-mode and kernel-mode copies of the page tables. In kernels that have KVAS support up to Windows 10 19H2 the `KVASCODE` section directly borders the `.text` section, so if you are able to get an address of a kernel entry point (such as the one in the LSTAR MSR), then you can use it as a starting point for a scanback.  

### Passing in from Userland
Of course, one foolproof technique you can use to get the base of the kernel into your kernel mode payload is pass the address in from user-mode. This is assuming medium integrity execution in user-mode and will not help when you're dealing with a fully remote exploit.  

### Other Leaks
Talking about how more specific kernel memory leaks work is outside the scope of this post, but I will say that Microsoft very frequently patches kernel information disclosure bugs, so perhaps you can use my post about [patch extraction and patch diffing]({filename}/posts/extracting-and-diffing-ms-patches-in-2020.md) to find and play with one :). 

## Version Detection in Kernel
Version detection can be accomplished by looking at the `NtMajorVersion`, `NtMinorVersion`, `NtBuildNumber`, and `NtProductType` fields of [KUSER_SHARED_DATA](https://docs.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-kuser_shared_data), which is always located in the kernel at 0xFFDF0000 (32-bit) or 0xFFFFF78000000000 (64-bit). Microsoft recently randomized the writable version of this structure and a read-only mapping is located at the old static address. Information on that can be found on the [MSRC blog](https://msrc-blog.microsoft.com/2022/04/05/randomizing-the-kuser_shared_data-structure-on-windows/) and in [this post by Connor McGarr](https://connormcgarr.github.io/kuser-shared-data-changes-win-11/).  

<div class="uk-alert">
    <i class="fa fa-info-circle fa-lg"></i><span class="alert-text">Funny enough the <code>NtMajorVersion</code> is still 10 on Windows 11</span>
</div>

# What Has Changed?
Now that we are all up to speed on what techniques are already out there, we need to take a look at what Microsoft has changed in the most recent versions of Windows that get in the way of some of these techniques and then how to work around these changes to make sure exploitation and/or execution can keep working on 20H1 and higher.  

## Kernel Mapping and Fake Headers
In kernel versions prior to 20H1, the `.text` section of the kernel binary bordered the top of the image. This means that it also bordered the PE header for the image. This fact is why it is possible to use the scanback technique from a pointer into the `.text` section. In kernel versions 20H1 and up, the `.text` section no longer borders the PE header. In fact, no code sections at all border the PE header. The `.rdata` (read-only data), `.pdata` (exception data), and `.idata` (import data) sections now border the PE header. Between `.idata` and the next readable section, `PROTDATA` lies a few unmapped pages and then the text section at 0x200000 bytes offset from the base of the PE. Fortunately, `.text` and `KVASCODE` are contiguous with the sections in between them.   

<div class="uk-grid">
    <div class="uk-width-1-1">
        <div class="uk-vertical-align">
            <div class="uk-width-medium-1-2 uk-width-small-1-1 uk-vertical-align-bottom">
                <center><img style="width: 75%;" alt="19H2 kernel memory segments" src="{static}/images/all-your-base-are-belong-to-us/19H2-segments.png" /></center>
                <center><small>The image starts with <em>.text</em> and it borders the top of the image</small></center>
            </div>
            <div class="uk-width-medium-1-2 uk-width-small-1-1 uk-vertical-align-bottom">
                <center><img style="width: 75%;" alt="20H2 kernel memory segments" src="{static}/images/all-your-base-are-belong-to-us/20H2-segments.png" /></center>
                <center><small>The <em>.text</em> section and the base of the image are now non-contiguous</small></center>
            </div>
        </div>
    </div>
</div>

For the sake of validation, let's see if those pages are actually unmapped or if something is there. To do so, let's load up our trusty kernel debugger.  

I'm just going to go back by a few thousand bytes fromt the kernel's text section into that gap and look over what is there, if anything. 

```
0: kd> dc nt+200000-5000 L500
fffff806`6e3fb000  00000000 00000000 00002b00 72657355  .........+..User
fffff806`6e3fb010  68636143 746e4565 78457972 65726970  CacheEntryExpire
fffff806`6e3fb020  65754464 6f4c6f54 64656b63 73736553  dDueToLockedSess
fffff806`6e3fb030  006e6f69 00030b06 00000000 00000000  ion.............
fffff806`6e3fb040  55000032 43726573 65686361 72746e45  2..UserCacheEntr
fffff806`6e3fb050  70784579 64657269 54657544 536f4e6f  yExpiredDueToNoS
fffff806`6e3fb060  69737365 73416e6f 69636f73 6f697461  essionAssociatio
fffff806`6e3fb070  0b06006e 00000005 00000000 00720000  n.............r.
fffff806`6e3fb080  65735500 63614372 6e456568 53797274  .UserCacheEntryS
fffff806`6e3fb090  65746174 65706f00 69746172 6f436e6f  tate.operationCo
... boring, boring
fffff806`6e3fc000  00905a4d 00000003 00000004 0000ffff  MZ..............
fffff806`6e3fc010  000000b8 00000000 00000040 00000000  ........@.......
fffff806`6e3fc020  00000000 00000000 00000000 00000000  ................
fffff806`6e3fc030  00000000 00000000 00000000 000000e8  ................
fffff806`6e3fc040  0eba1f0e cd09b400 4c01b821 685421cd  ........!..L.!Th
fffff806`6e3fc050  70207369 72676f72 63206d61 6f6e6e61  is program canno
fffff806`6e3fc060  65622074 6e757220 206e6920 20534f44  t be run in DOS 
fffff806`6e3fc070  65646f6d 0a0d0d2e 00000024 00000000  mode....$.......
```

Well that looks interesting. It's a PE header... but to what?

```
0: kd> !dh fffff806`6e3fc000

File Type: DLL
FILE HEADER VALUES
     14C machine (i386)
       6 number of sections
2AB009D1 time date stamp Thu Sep 10 22:52:01 1992

       0 file pointer to symbol table
       0 number of symbols
      E0 size of optional header
    2102 characteristics
            Executable
            32 bit word machine
            DLL

OPTIONAL HEADER VALUES
     10B magic #
   14.20 linker version
   1A800 size of code
    4600 size of initialized data
       0 size of uninitialized data
    7370 address of entry point
    1000 base of code
         ----- new -----
0000000076570000 image base
    1000 section alignment
     200 file alignment
       3 subsystem (Windows CUI)
   10.00 operating system version
   10.00 image version
   10.00 subsystem version
   23000 size of image
     400 size of headers
   233EC checksum
0000000000040000 size of stack reserve
0000000000001000 size of stack commit
0000000000100000 size of heap reserve
0000000000001000 size of heap commit
    4540  DLL characteristics
            Dynamic base
            NX compatible
            No structured exception handler
            Guard
   11D80 [    99D3] address [size] of Export Directory
   1D364 [     154] address [size] of Import Directory
   20000 [     3D8] address [size] of Resource Directory
       0 [       0] address [size] of Exception Directory
   1EE00 [    2690] address [size] of Security Directory
   21000 [    1304] address [size] of Base Relocation Directory
    28E0 [      54] address [size] of Debug Directory
       0 [       0] address [size] of Description Directory
       0 [       0] address [size] of Special Directory
       0 [       0] address [size] of Thread Storage Directory
    1000 [      AC] address [size] of Load Configuration Directory
       0 [       0] address [size] of Bound Import Directory
   1D000 [     360] address [size] of Import Address Table Directory
    E0AC [     320] address [size] of Delay Import Directory
       0 [       0] address [size] of COR20 Header Directory
       0 [       0] address [size] of Reserved Directory


SECTION HEADER #1
   .text name
   1A753 virtual size
    1000 virtual address
   1A800 size of raw data
     400 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read


Debug Directories(3)
	Type       Size     Address  Pointer
	(   96)   60f01       d640f    a340f
	(1342988301)    300b       c1d01    b741d
	(4028183069)c015e017       a2619  10f0114

SECTION HEADER #2
   .data name
     4F4 virtual size
   1C000 virtual address
     200 size of raw data
   1AC00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C0000040 flags
         Initialized Data
         (no align specified)
         Read Write

SECTION HEADER #3
  .idata name
    1D9A virtual size
   1D000 virtual address
    1E00 size of raw data
   1AE00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
40000040 flags
         Initialized Data
         (no align specified)
         Read Only

SECTION HEADER #4
  .didat name
     8C4 virtual size
   1F000 virtual address
     A00 size of raw data
   1CC00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C0000040 flags
         Initialized Data
         (no align specified)
         Read Write

SECTION HEADER #5
   .rsrc name
     3D8 virtual size
   20000 virtual address
     400 size of raw data
   1D600 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
40000040 flags
         Initialized Data
         (no align specified)
         Read Only

SECTION HEADER #6
  .reloc name
    1304 virtual size
   21000 virtual address
    1400 size of raw data
   1DA00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
42000040 flags
         Initialized Data
         Discardable
         (no align specified)
         Read Only
```

Everything seems to parse out OK, but there is some minor issues...
For starters the machine type for this "DLL" is i386, which seems unlikely to be true since this is a 64-bit kernel. Another discrepancy is the debug directory, which seems to be completely bogus. It seems like there are a bunch of fake, mostly complete DOS/PE headers in that gap for some reason. The following command will find them all and dump their headers for closer inspection: 

```
0: kd> .foreach (addr { s -[1]b nt L200000 4d 5a 90 00 03 }) { .echo ${addr}; dc ${addr} L20; !dh ${addr}; .echo }
```


<details>
<summary>NT header scan output</summary>
```
0xfffff806`6e200000
fffff806`6e200000  00905a4d 00000003 00000004 0000ffff  MZ..............
fffff806`6e200010  000000b8 00000000 00000040 00000000  ........@.......
fffff806`6e200020  00000000 00000000 00000000 00000000  ................
fffff806`6e200030  00000000 00000000 00000000 00000118  ................
fffff806`6e200040  0eba1f0e cd09b400 4c01b821 685421cd  ........!..L.!Th
fffff806`6e200050  70207369 72676f72 63206d61 6f6e6e61  is program canno
fffff806`6e200060  65622074 6e757220 206e6920 20534f44  t be run in DOS 
fffff806`6e200070  65646f6d 0a0d0d2e 00000024 00000000  mode....$.......

File Type: EXECUTABLE IMAGE
FILE HEADER VALUES
    8664 machine (X64)
      21 number of sections
73F1C0C4 time date stamp Fri Aug 22 23:49:24 2031

       0 file pointer to symbol table
       0 number of symbols
      F0 size of optional header
      22 characteristics
            Executable
            App can handle >2gb addresses

OPTIONAL HEADER VALUES
     20B magic #
   14.20 linker version
  8B5600 size of code
  1B7E00 size of initialized data
  495000 size of uninitialized data
  98D010 address of entry point
    1000 base of code
         ----- new -----
fffff8066e200000 image base
    1000 section alignment
     200 file alignment
       1 subsystem (Native)
   10.00 operating system version
   10.00 image version
   10.00 subsystem version
 1046000 size of image
     800 size of headers
  A65799 checksum
0000000000080000 size of stack reserve
0000000000002000 size of stack commit
0000000000100000 size of heap reserve
0000000000001000 size of heap commit
    4160  DLL characteristics
            High entropy VA supported
            Dynamic base
            NX compatible
            Guard
  134000 [   18C86] address [size] of Export Directory
  131630 [     168] address [size] of Import Directory
 1000000 [   3B23C] address [size] of Resource Directory
   C9000 [   67A7C] address [size] of Exception Directory
  A56600 [    2540] address [size] of Security Directory
 103C000 [    50B4] address [size] of Base Relocation Directory
   108E0 [      54] address [size] of Debug Directory
       0 [       0] address [size] of Description Directory
       0 [       0] address [size] of Special Directory
       0 [       0] address [size] of Thread Storage Directory
    5B30 [     118] address [size] of Load Configuration Directory
       0 [       0] address [size] of Bound Import Directory
  131000 [     620] address [size] of Import Address Table Directory
       0 [       0] address [size] of Delay Import Directory
       0 [       0] address [size] of COR20 Header Directory
       0 [       0] address [size] of Reserved Directory


SECTION HEADER #1
  .rdata name
   C7940 virtual size
    1000 virtual address
   C7A00 size of raw data
     800 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
48000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Only


Debug Directories(3)
	Type       Size     Address  Pointer
	cv           25       406e0    3fee0	Format: RSDS, guid, 1, ntkrnlmp.pdb
	(   13)    1568       40708    3ff08
	(   16)      24       41cc4    414c4

SECTION HEADER #2
  .pdata name
   67A7C virtual size
   C9000 virtual address
   67C00 size of raw data
   C8200 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
48000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Only

SECTION HEADER #3
  .idata name
    20C2 virtual size
  131000 virtual address
    2200 size of raw data
  12FE00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
48000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Only

SECTION HEADER #4
  .edata name
   18C86 virtual size
  134000 virtual address
   18E00 size of raw data
  132000 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
40000040 flags
         Initialized Data
         (no align specified)
         Read Only

SECTION HEADER #5
PROTDATA name
       1 virtual size
  14D000 virtual address
     200 size of raw data
  14AE00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
48000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Only

SECTION HEADER #6
   GFIDS name
    8BFC virtual size
  14E000 virtual address
    8C00 size of raw data
  14B000 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
42000040 flags
         Initialized Data
         Discardable
         (no align specified)
         Read Only

SECTION HEADER #7
    Pad1 name
   A9000 virtual size
  157000 virtual address
       0 size of raw data
       0 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
42000080 flags
         Uninitialized Data
         Discardable
         (no align specified)
         Read Only

SECTION HEADER #8
   .text name
  3C6F59 virtual size
  200000 virtual address
  3C7000 size of raw data
  153C00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
68000020 flags
         Code
         Not Paged
         (no align specified)
         Execute Read

SECTION HEADER #9
    PAGE name
  3C5716 virtual size
  5C7000 virtual address
  3C5800 size of raw data
  51AC00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read

SECTION HEADER #A
  PAGELK name
   24E74 virtual size
  98D000 virtual address
   25000 size of raw data
  8E0400 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read

SECTION HEADER #B
POOLCODE name
     48B virtual size
  9B2000 virtual address
     600 size of raw data
  905400 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
68000020 flags
         Code
         Not Paged
         (no align specified)
         Execute Read

SECTION HEADER #C
  PAGEKD name
    5B92 virtual size
  9B3000 virtual address
    5C00 size of raw data
  905A00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read

SECTION HEADER #D
PAGEVRFY name
   320EC virtual size
  9B9000 virtual address
   32200 size of raw data
  90B600 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read

SECTION HEADER #E
PAGEHDLS name
    25D6 virtual size
  9EC000 virtual address
    2600 size of raw data
  93D800 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read

SECTION HEADER #F
PAGEBGFX name
    69EA virtual size
  9EF000 virtual address
    6A00 size of raw data
  93FE00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read

SECTION HEADER #10
INITKDBG name
   195BA virtual size
  9F6000 virtual address
   19600 size of raw data
  946800 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
68000020 flags
         Code
         Not Paged
         (no align specified)
         Execute Read

SECTION HEADER #11
TRACESUP name
    175B virtual size
  A10000 virtual address
    1800 size of raw data
  95FE00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
68000020 flags
         Code
         Not Paged
         (no align specified)
         Execute Read

SECTION HEADER #12
KVASCODE name
    23DE virtual size
  A12000 virtual address
    2400 size of raw data
  961600 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
68000020 flags
         Code
         Not Paged
         (no align specified)
         Execute Read

SECTION HEADER #13
  RETPOL name
     740 virtual size
  A15000 virtual address
     800 size of raw data
  963A00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
68000020 flags
         Code
         Not Paged
         (no align specified)
         Execute Read

SECTION HEADER #14
  MINIEX name
    25AE virtual size
  A16000 virtual address
    2600 size of raw data
  964200 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
62000020 flags
         Code
         Discardable
         (no align specified)
         Execute Read

SECTION HEADER #15
    INIT name
   8AA98 virtual size
  A19000 virtual address
   8AC00 size of raw data
  966800 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
62000020 flags
         Code
         Discardable
         (no align specified)
         Execute Read

SECTION HEADER #16
    Pad2 name
  15C000 virtual size
  AA4000 virtual address
       0 size of raw data
       0 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
62000080 flags
         Uninitialized Data
         Discardable
         (no align specified)
         Execute Read

SECTION HEADER #17
   .data name
   FA018 virtual size
  C00000 virtual address
   13000 size of raw data
  9F1400 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C8000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Write

SECTION HEADER #18
ALMOSTRO name
   272E0 virtual size
  CFB000 virtual address
    1400 size of raw data
  A04400 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C8000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Write

SECTION HEADER #19
CACHEALI name
    92C0 virtual size
  D23000 virtual address
     200 size of raw data
  A05800 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C8000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Write

SECTION HEADER #1A
PAGEDATA name
   12150 virtual size
  D2D000 virtual address
    1800 size of raw data
  A05A00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C0000040 flags
         Initialized Data
         (no align specified)
         Read Write

SECTION HEADER #1B
PAGEVRFD name
   15D00 virtual size
  D40000 virtual address
    8000 size of raw data
  A07200 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C0000040 flags
         Initialized Data
         (no align specified)
         Read Write

SECTION HEADER #1C
INITDATA name
   17C44 virtual size
  D56000 virtual address
     800 size of raw data
  A0F200 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C2000020 flags
         Code
         Discardable
         (no align specified)
         Read Write

SECTION HEADER #1D
    Pad3 name
   92000 virtual size
  D6E000 virtual address
       0 size of raw data
       0 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C2000080 flags
         Uninitialized Data
         Discardable
         (no align specified)
         Read Write

SECTION HEADER #1E
   CFGRO name
    1CC8 virtual size
  E00000 virtual address
    1E00 size of raw data
  A0FA00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C8000040 flags
         Initialized Data
         Not Paged
         (no align specified)
         Read Write

SECTION HEADER #1F
    Pad4 name
  1FE000 virtual size
  E02000 virtual address
       0 size of raw data
       0 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
CA000080 flags
         Uninitialized Data
         Discardable
         Not Paged
         (no align specified)
         Read Write

SECTION HEADER #20
   .rsrc name
   3B23C virtual size
 1000000 virtual address
   3B400 size of raw data
  A11800 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
42000040 flags
         Initialized Data
         Discardable
         (no align specified)
         Read Only

SECTION HEADER #21
  .reloc name
    9964 virtual size
 103C000 virtual address
    9A00 size of raw data
  A4CC00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
42000040 flags
         Initialized Data
         Discardable
         (no align specified)
         Read Only

... many more headers

0xfffff806`6e3fc000
fffff806`6e3fc000  00905a4d 00000003 00000004 0000ffff  MZ..............
fffff806`6e3fc010  000000b8 00000000 00000040 00000000  ........@.......
fffff806`6e3fc020  00000000 00000000 00000000 00000000  ................
fffff806`6e3fc030  00000000 00000000 00000000 000000e8  ................
fffff806`6e3fc040  0eba1f0e cd09b400 4c01b821 685421cd  ........!..L.!Th
fffff806`6e3fc050  70207369 72676f72 63206d61 6f6e6e61  is program canno
fffff806`6e3fc060  65622074 6e757220 206e6920 20534f44  t be run in DOS 
fffff806`6e3fc070  65646f6d 0a0d0d2e 00000024 00000000  mode....$.......

File Type: DLL
FILE HEADER VALUES
     14C machine (i386)
       6 number of sections
2AB009D1 time date stamp Thu Sep 10 22:52:01 1992

       0 file pointer to symbol table
       0 number of symbols
      E0 size of optional header
    2102 characteristics
            Executable
            32 bit word machine
            DLL

OPTIONAL HEADER VALUES
     10B magic #
   14.20 linker version
   1A800 size of code
    4600 size of initialized data
       0 size of uninitialized data
    7370 address of entry point
    1000 base of code
         ----- new -----
0000000076570000 image base
    1000 section alignment
     200 file alignment
       3 subsystem (Windows CUI)
   10.00 operating system version
   10.00 image version
   10.00 subsystem version
   23000 size of image
     400 size of headers
   233EC checksum
0000000000040000 size of stack reserve
0000000000001000 size of stack commit
0000000000100000 size of heap reserve
0000000000001000 size of heap commit
    4540  DLL characteristics
            Dynamic base
            NX compatible
            No structured exception handler
            Guard
   11D80 [    99D3] address [size] of Export Directory
   1D364 [     154] address [size] of Import Directory
   20000 [     3D8] address [size] of Resource Directory
       0 [       0] address [size] of Exception Directory
   1EE00 [    2690] address [size] of Security Directory
   21000 [    1304] address [size] of Base Relocation Directory
    28E0 [      54] address [size] of Debug Directory
       0 [       0] address [size] of Description Directory
       0 [       0] address [size] of Special Directory
       0 [       0] address [size] of Thread Storage Directory
    1000 [      AC] address [size] of Load Configuration Directory
       0 [       0] address [size] of Bound Import Directory
   1D000 [     360] address [size] of Import Address Table Directory
    E0AC [     320] address [size] of Delay Import Directory
       0 [       0] address [size] of COR20 Header Directory
       0 [       0] address [size] of Reserved Directory


SECTION HEADER #1
   .text name
   1A753 virtual size
    1000 virtual address
   1A800 size of raw data
     400 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
60000020 flags
         Code
         (no align specified)
         Execute Read


Debug Directories(3)
	Type       Size     Address  Pointer
	(   96)   60f01       d640f    a340f
	(1342988301)    300b       c1d01    b741d
	(4028183069)c015e017       a2619  10f0114

SECTION HEADER #2
   .data name
     4F4 virtual size
   1C000 virtual address
     200 size of raw data
   1AC00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C0000040 flags
         Initialized Data
         (no align specified)
         Read Write

SECTION HEADER #3
  .idata name
    1D9A virtual size
   1D000 virtual address
    1E00 size of raw data
   1AE00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
40000040 flags
         Initialized Data
         (no align specified)
         Read Only

SECTION HEADER #4
  .didat name
     8C4 virtual size
   1F000 virtual address
     A00 size of raw data
   1CC00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
C0000040 flags
         Initialized Data
         (no align specified)
         Read Write

SECTION HEADER #5
   .rsrc name
     3D8 virtual size
   20000 virtual address
     400 size of raw data
   1D600 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
40000040 flags
         Initialized Data
         (no align specified)
         Read Only

SECTION HEADER #6
  .reloc name
    1304 virtual size
   21000 virtual address
    1400 size of raw data
   1DA00 file pointer to raw data
       0 file pointer to relocation table
       0 file pointer to line numbers
       0 number of relocations
       0 number of line numbers
42000040 flags
         Initialized Data
         Discardable
         (no align specified)
         Read Only
```
</details>

The first one is the header dump for kernel. Note the valid debug directory. If you want the full output you can get that [here]({attach}/files/kernel-headers-kd-full-output.txt).

Some of these headers are less valid than they appear. The last header tells us that the code section starts at an offset of 0x1000 bytes. Investigating that memory location yields not code, but ASCII data. 

```
0: kd> db fffff806`6e3f0000+1000
fffff806`6e3f1000  29 0a 2d 2d 0a 0a 50 6f-73 74 20 61 20 6d 65 73  ).--..Post a mes
fffff806`6e3f1010  73 61 67 65 20 74 6f 20-63 6f 6d 70 6c 65 74 69  sage to completi
fffff806`6e3f1020  6f 6e 20 70 6f 72 74 2e-00 00 00 00 00 00 00 00  on port.........
fffff806`6e3f1030  52 65 61 64 46 69 6c 65-28 24 73 65 6c 66 2c 20  ReadFile($self, 
fffff806`6e3f1040  68 61 6e 64 6c 65 2c 20-73 69 7a 65 2c 20 2f 29  handle, size, /)
fffff806`6e3f1050  0a 2d 2d 0a 0a 53 74 61-72 74 20 6f 76 65 72 6c  .--..Start overl
fffff806`6e3f1060  61 70 70 65 64 20 72 65-61 64 2e 00 00 00 00 00  apped read......
fffff806`6e3f1070  4f 76 65 72 6c 61 70 70-65 64 28 65 76 65 6e 74  Overlapped(event
```

It is possible that these DLLs/drivers were really here at *some point* but they are gone now and what is left will mess up our page-at-a-time scanback technique to find the base of the kernel. 

## hal.dll
Another interesting change in the kernel in 20H1+ is that the Hardware Abstraction Layer (HAL) has moved into the kernel image itself and no longer lives inside of hal.dll. If you open up hal.dll in a disassembler, you will notice that it actually does not even have a `.text` section. It is just a forwarding DLL that [forwards exports](https://docs.microsoft.com/en-us/archive/msdn-magazine/2002/march/inside-windows-an-in-depth-look-into-the-win32-portable-executable-file-format-part-2#export-forwarding) into the kernel. The forwarding is done to not break backwards compatibility with drivers and components that expect to import HAL functionality from hal.dll and not ntoskrnl.exe.  

<center>
![hal.dll]({static}/images/all-your-base-are-belong-to-us/hal-segments.png)  
<small>hal.dll has no code! It does still have the Hal* exports.</small>
</center>

# Fixing Scanback
Since the new version of the kernel has the `.text` section starting at 0x200000 we can adjust our scanback to the following algorithm:

```rust
const KUSER_SHARED_DATA: usize = 0xFFFFF78000000000;
const KUSER_NT_MAJOR_VERSION_OFFSET: usize = 0x26C;
const KUSER_NT_BUILD_NUMBER_OFFSET: usize = 0x260;
let major_version: *const u32 = (KUSER_SHARED_DATA + KUSER_NT_MAJOR_VERSION_OFFSET) as _;
let build_number: *const u32 = (KUSER_SHARED_DATA + KUSER_NT_BUILD_NUMBER_OFFSET) as _;
let step = if unsafe { *major_version >= 10 && *build_number > 19000 } {
    0x200000
} else {
    0x1000
}
let mut cursor = (leaked_addr as usize & !(step-1)) as *const u16;
unsafe {
    while *cursor != 0x5a4d {
        cursor = cursor.sub(step);
    }
}
let kernel_base = cursor as usize;
```
Obviously, this code has to be version dependent so we can still use the `KUSER_SHARED_DATA` version detection method to decide which step amount to use. The algorithm is the same as before, but instead of rounding down to the nearest page and then scanning backward by page size, we use 0x200000.  

Another alternative is to parse each header and try to figure out which one is ntoskrnl.exe. I've tried two alternatives that work: checking the number of sections or looking up the PDB path via the DEBUG data directory.  

If Microsoft decides to change the `.text` section offset or puts unmapped regions between sections this will need to be re-written. 

# Wrap Up
I hope that this post has been informative! I thought there was going to be more in the solutions section than literature review, but I think this ended up being a good round up of info regardless. It's been something I've wanted to post for a while but finally took the time to write it up properly. 

Anyway, have a good day and remember to ask yourself... ~~did you set it to wumbo?~~