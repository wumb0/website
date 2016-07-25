Title: Uninstall all installed windows KB patches in one line of batch
Date: 2015-11-05 23:49
Category: Old Posts
Tags: old
Slug: Uninstall-all-installed-windows-KB-patches-in-one-line-of-batch
Authors: wumb0

<p>I was trying to unpatch something to make it vulnerable and I was getting impatient trying to uninstall the correct patch so I got creative and came up with a one liner to uninstall all of them at once. Or at least all of the ones with working uninstallers and don't have other dependencies... The uninstallers are all called spuninst.exe and are somewhere in \\WINDOWS (under a bunch of sub folders that start with $NtUninstall) so I give you the following command:</p>
 
```batch
for /F %a in ('dir /B /S /A \\WINDOWS ^\| findstr spuninst.exe ^\| findstr NtUninstall') do @(echo %a && %a /quiet /norestart)
```

<p>Keep running this until it does not print anything and then all of the patches will be gone on reboot. Happy unpatching</p>


... bonus

```batch
for /L %b in (0,0,1) do @for /F %a in ('dir /B /S /A \\WINDOWS ^\| findstr spuninst.exe ^\| findstr NtUninstall') do @(echo %a && %a /quiet /norestart)
```
<p>Just keep running that until the screen is blank</p>
