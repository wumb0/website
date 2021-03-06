Title: Autoruns Bypasses
Date: 2019-05-26 18:50
Category: Pentesting
Tags: autoruns sysinternals
Slug: autoruns-bypasses
Authors: wumb0

Autoruns is a tool that is part of the Microsoft [Sysinternals suite](https://docs.microsoft.com/en-us/sysinternals/downloads/sysinternals-suite). It comes in permutations of console/GUI and 32/64 bit versions. Its main purpose is to detect programs, scripts, and other items that run either periodically or at login. It's a fantastic tool for blue teams to find persistent execution, but it is not perfect! By default, autoruns hides entries that are considered "Windows" entries (Options menu -> Hide Windows Entries). There is a checkbox to unhide them, but it introduces a lot of noise. In my preparations to red team for the Information Security Talent Search (ISTS) at RIT and the Mid-Atlantic Collegiate Cyber Defense Comptition (MACCDC) this year I found a few ways to hide myself among the Windows entries reported in Autoruns.  

For some prior work done in this area check out [Huntress Labs's research](https://github.com/huntresslabs/evading-autoruns) and [Conscious Hacker's research](https://blog.conscioushacker.io/index.php/2017/10/25/evading-microsofts-autoruns/).  

[[more]]
## Method 1: Copy a file
This one is as easy as copying powershell or cmd to another name and using that name instead. It looks like autoruns will flag by name on powershell and cmd as shown below:  
<center>![malicious entry found in autoruns]({static}/images/autoruns-badstuff-found.PNG)</center>  
This entry in the infamous run key is running powershell to use Net.Webclient to download and execute a string (DownloadString -> IEX).  
<center>![badstuff registry entry]({static}/images/autoruns-malicious-entry.PNG)</center>  
Clearly malicious! So now let's try copying powershell.exe to badstuff.exe:
```
copy \Windows\system32\WindowsPowerShell\v1.0\powershell.exe \Windows\system32\badstuff.exe
```
Then we need to edit the registry key to use our copied executable:
<center>![regedit copy]({static}/images/autoruns-badstuff-regedit.PNG)</center>  
Now looking at autoruns it appears clean
<center>![clean autoruns]({static}/images/autoruns-badstuff-not-found.PNG)</center>  
Showing windows entries reveals the entry, but this time it is not highlighted red. Autoruns doesn't know what it is, only that it is in system32 and signed by Microsoft.  
<center>![autoruns with windows entries]({static}/images/autoruns-badstuff-windows-entries.PNG)</center>  

**Proposed fix**: check not only the executable name, but the program description to detect cmd and powershell.  

## Method 2: Image File Execution Options
The *Image File Execution Options* (IFEO) registry key located at HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrrentVersion\\Image File Execution Options is used to set a myriad of options such as heap options and setting a program's debugger. For this bypass to work we can pick a lesser-used executable in System32 and set its Debugger in IFEO to cmd.exe or powershell.exe. I chose print.exe for this test, but there may be better options.  
<center>![print ifeo]({static}/images/autoruns-print-ifeo.PNG)</center>  
The technique involves creating a key under the parent IFEO and adding a REG\_SZ value with the executable to execute.  
Then we need to edit our run key to use print.exe instead of powershell.exe. Checking back with autoruns the entry is gone!  
<center>![clean autoruns]({static}/images/autoruns-badstuff-not-found.PNG)</center>  
And again unhiding windows entries results in the entry being shown, but this time we have the added bonus of not appearing as powershell in the description!
<center>![autoruns with windows entries print]({static}/images/autoruns-print-windows-entries.PNG)</center>  

**Proposed fix**: resolve the final executable by checking the Debugger key in Image File Execution Options.  

There's another technique you can also use with IFEO documented on [Oddvar Moe's blog](https://oddvar.moe/2018/04/10/persistence-using-globalflags-in-image-file-execution-options-hidden-from-autoruns-exe/).  

## Wrap-up
A tool is really only as good as the algorithms it uses. Autoruns is no exception. It doesn't go deep enough to figure out what binary is actually executing or if that binary is something that it would normally flag with its original name. Always be skeptical of your tools and know they might not be perfect!  
