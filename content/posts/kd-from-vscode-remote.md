Title: Using kd.exe from VSCode Remote
Date: 2021-07-02 22:36
Category: Misc
Tags: windows windows-kernel
Slug: using-kd.exe-from-vscode-remote
Authors: wumb0

I wanted to do a small post here, just because the answer to this issue was sort of scattered on the internet. Bigger post coming soon on some kernel exploit technique stuff.  

It turns out that when running kd.exe for command line kernel debugging from VSCode remote, symbol resolution breaks completely. Why? Looks like when running from a service symsrv.dll uses WINHTTP for making requests instead of WININET. You can replicate this behavior in a normal shell by setting `$env:DBGHELP_WINHTTP=1` in a powershell window and then running kd.exe. For some reason, WINHTTP tries to always use a proxy server, so you have to tell it not to via the following key in the registry:

`HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Symbol Server` -> `NoInternetProxy` -> DWORD = 1

You should also set it in `HKLM\SOFTWARE\WOW6432Node\Microsoft\Symbol Server` too, in case you are using a 32-bit debugger. 

This issue will happen with cdb.exe and kd.exe, so I hope this solution helps someone.  

[https://stackoverflow.com/questions/5095328/cannot-download-microsoft-symbols-when-running-cdb-in-a-windows-service](https://stackoverflow.com/questions/5095328/cannot-download-microsoft-symbols-when-running-cdb-in-a-windows-service)  
[https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/configuring-the-registry](https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/configuring-the-registry)  