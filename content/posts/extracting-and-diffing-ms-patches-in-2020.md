Title: Extracting and Diffing Windows Patches in 2020  
Date: 2020-08-23 11:51  
Category: Vuln. Research  
Tags: patch-diff, VR, bindiff, patch-delta  
Slug: extracting-and-diffing-ms-patches-in-2020 
Authors: wumb0  

It's been a while since I've posted anything here! After all, what are personal blogs for but ignoring for years at a time ;)  
Anyhow, I've been running through this demo when teaching [SANS SEC760](https://www.sans.org/cyber-security-courses/advanced-exploit-development-penetration-testers/) and I thought I'd write it up so that researchers can come back to it later when they need it. It's also useful to document all of this stuff in one place, since the information about it seems scattered throughout the internet, as many Windows topics are.  



So why should you care about extracting and analyzing Windows patches? Doesn't the patch mean the bugs being fixed are now useless?  

[[more]]

To start thinking about how to answer those questions, think about how long it takes for even a well running organization with proper patch management to roll out patches to devices. If you, the security researcher, can weaponize a bug within a few weeks of a patch being released, then you may be able to sell it or use it in engagements. Finding bugs is hard, but n-day research tells you pretty much exactly where the bugs are! This is good news. Looking at how patches are implemented and where bugs are fixed can also be useful in discovering 0-days. Over the years, Microsoft has had to fix the same (or very similar) bugs in multiple places. A classic example is the old [MS07-017](https://docs.microsoft.com/en-us/security-updates/securitybulletins/2007/ms07-017) animated cursor bug that was actually a repeat of the same exact bug from two years prior ([MS05-002](https://docs.microsoft.com/en-us/security-updates/securitybulletins/2005/ms05-002)), just one function cross-reference away. Additionally, Microsoft may not fix the vulnerability at all, or the fix may not be complete, as was the case with the Print Spooler bugs that were found this year, dubbed [PrintDemon](https://windows-internals.com/printdemon-cve-2020-1048/) by Ionescu and Shafir. The original CVE is [CVE-2020-1048](https://portal.msrc.microsoft.com/en-us/security-guidance/advisory/CVE-2020-1048) and is credited to Peleg Hadar and Tomer Bar over at [SafeBreach Labs](https://safebreach.com/safebreach-labs). After the fix, Ionescu was credited with [CVE-2020-1337](https://portal.msrc.microsoft.com/en-US/security-guidance/advisory/CVE-2020-1337) which still allowed the creation of malicious ports through a Time Of Check Time Of Use (TOC/TOU) bug, slightly detailed [here](https://twitter.com/aionescu/status/1293283013715951622). All of this just to say: **yes** it is worth looking at patches. Looking at patches can also help you find new features that have yet to be thouroughly torn apart by researchers, which are [prime targets for vulnerability research](https://twitter.com/aionescu/status/1271098369788674051).  

# Obtaining Patches and the Windows Patch Packaging Formats
To be able to rip apart a patch you'll first need to understand what format patches come in and how to get them. You might actually be vaguely familiar with the file formats used to package a patch: .MSU (Microsoft Standalone Update) and .CAB (Cabinet). All patches are distributed as part of Windows Update on your device, but you can also still download standalone patches from the [Microsoft Update Catolog](https://www.catalog.update.microsoft.com/Home.aspx). For this post I'm going to be tearing apart patches for Windows 10 1903 x64. A long time ago Microsoft established the second Tuesday of every month as Patch Tuesday, so that patch managers could always know when to expect fixes. For the most part they stick to releasing updates on Patch Tuesday, with the occasional emergency patch for [very severe bugs](https://docs.microsoft.com/en-us/security-updates/SecurityBulletins/2015/ms15-078). Microsoft used to provide sequential update packages that had to be installed in order. These days, updates are provided as **cumulative**, meaning that all of the required updates from the base version (.1) are included in the package. This can make for some pretty large updates! To make things a bit more complicated, many of the updates are distributed as *deltas*, which we will talk about in depth later in this post.  

## Effectively Browsing the Microsoft Update Catalog
Luckily, the Microsoft Update Catalog has a pretty good search feature. The most effective way to search for the update you want is to search in the following format:

<pre>YYYY-MM release-number (x86|x64|ARM64) cumulative</pre>

So for example, if I am looking for the July 2020 patch set for Windows 10 1903 x64 I would search `2020-07 1903 x64 cumulative` and one of the top hits should be the result I'm looking for.

<center>
![Searching for an update]({static}/images/extracting-and-diffing-ms-patches-in-2020/msupdate-search.png)  
<small>Relevant results are easy to get with the right search!</small>
</center>

As you can see, results were returned for a few different release numbers (1903, 1909, and 2004) and both Windows 10 and Windows Server. The keen observer should note that the Windows Server and Windows 10 updates are the exact same size. In fact, if you click download, both links direct to the same place. Additionally, updates for 1903 and 1909 are also the same. The latter case reason is explained on the [OS build page](https://support.microsoft.com/en-us/help/4565483): 

> Windows 10, versions 1903 and 1909 share a common core operating system and an identical set of system files. As a result, the new features in Windows 10, version 1909 were included in the recent monthly quality update for Windows 10, version 1903 (released October 8, 2019), but are currently in a dormant state. These new features will remain dormant until they are turned on using an enablement package, which is a small, quick-to-install “master switch” that simply activates the Windows 10, version 1909 features.


## Dynamic and Servicing Stack Updates
Microsoft also distributes a few other kinds of updates via the Microsoft Update Catalog. If you leave off the word *cumulative* from the search above, then you get some more results, including *Dynamic* and *Servicing Stack* updates that are considerably smaller than the cumulative updates.  

<center>
![Update variations]({static}/images/extracting-and-diffing-ms-patches-in-2020/msupdate-variations.png)  
<small>Different Kinds of Updates</small>
</center>

[According to Microsoft documentation](https://docs.microsoft.com/en-us/windows/deployment/update/servicing-stack-updates) servicing stack updates are updates to the Windows Update process itself. Servicing stack updates are packaged like cumulative updates and only include components related to Windows Update.  

[Microsoft documentation](https://techcommunity.microsoft.com/t5/windows-it-pro-blog/the-benefits-of-windows-10-dynamic-update/ba-p/467847) saves the day again for dynamic updates, which apparently can also update Windows Update components, as well as setup components like installation media, Windows Recovery Environment (WinRE), and some drivers. Dynamic updates are packaged slightly differently than cumulative and servicing stack updates; they are downloadable as a single CAB file and have various language packs and other setup components.  

# Extracting a Patch
Patches are packed tightly into an MSU file, which can contain tens of thousands of files, only some of which matter to us as security researchers. I wanted to walk through manual extraction first and then provide an update to an existing script (PatchExtract.ps1) to automatically extract and sort a given patch.  

## Manual Extraction
To get started, you'll need to download a cumulative update MSU file from the update catalog. For this example I'm using the Windows 10 1903 x64 August 2020 cumulative update package. I usually make a few folders before I start: I name the top-level folder with the patch year and month and then create two sub-folders called `patch` and `ext`. The actual patch files inside of the nested CAB file will go in the `patch` folder, and the contents of the extracted MSU will go in the `ext` folder.  

<pre><code class="powershell">mkdir 2020-08
mv ".\windows10.0-kb4565351-x64_e4f46f54ab78b4dd2dcef193ed573737661e5a10.msu" .\2020-08\
cd .\2020-08\
mkdir ext
mkdir patch
</code></pre>

Next, I'm going to expand the MSU using the `expand.exe` command. The arguments for `expand` can be detailed using the `/?` flag. For our purposes we will be extracting every file so we will use `-F:*`. If you only want certain kinds of files (CABs, DLLs, EXEs, etc.) then you can use the `-F` flag make it so. The next two arguments are the MSU to extract and then the destination folder for the expanded files.  

<pre><code class="powershell">expand.exe -F:* ".\windows10.0-kb4565351-x64_e4f46f54ab78b4dd2dcef193ed573737661e5a10.msu" .\ext\
</code></pre>

Finally, I'm going to extract the patch files from the PSFX cab file by using the `expand` command again, this time expanding to the `patch` directory.  

<pre><code class="powershell">expand.exe -F:* ".\ext\Windows10.0-KB4565351-x64_PSFX.cab" .\patch\ | Out-Null
</code></pre>

At this point I recommend walking away, starting a load of laundry, getting a sandwich, and petting the cat, because this part takes a while (10-20mins). The `Out-Null` is optional, I only use it because I don't care for it printing every file it is about to extract. This particular extraction took about 15 minutes (via `Measure-Command`) and resulted in a total of 78898 files and folders under the *patch* folder!  

If you're following along at home:  
Once the extraction is complete, give yourself a high-five, and then take it back, because unfortunately that was the easy part!  

Next, you'll have to make sense of the extracted files and find the patched files you are looking for.  

## Making Sense of the Extracted Files
To find what you are looking for it helps to know the structure of the patch and the types of files you will encounter.  

To begin to understand these details take a look at this hirearchical view of a patch starting with the MSU (output abbreviated to save space):

<pre>
windows10.0-kb4565351-x64_e4f46f54ab78b4dd2dcef193ed573737661e5a10.msu
├── WSUSSCAN.cab
├── Windows10.0-KB4565351-x64-pkgProperties_PSFX.txt
├── Windows10.0-KB4565351-x64_PSFX.xml
└── Windows10.0-KB4565351-x64_PSFX.cab
    ├── amd64_microsoft.windows.gdiplus_6595b64144ccf1df_1.0.18362.1016_none_e013babca5ee7b0b
    │   └── gdiplus.dll
    ├── amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.18362.1016_none_79ea293316ee3bad
    │   ├── f
    │   │   └── ntoskrnl.exe
    │   └── r
    │       └── ntoskrnl.exe
    ├── msil_microsoft.hyperv.powershell.cmdlets_31bf3856ad364e35_10.0.18362.959_none_a7668eee2055cacf
    │   ├── f
    │   │   └── microsoft.hyperv.powershell.cmdlets.dll
    │   └── r
    │       └── microsoft.hyperv.powershell.cmdlets.dll
    ├── wow64_microsoft-windows-p..ting-spooler-client_31bf3856ad364e35_10.0.18362.693_none_f3229700ded2ae02
    │   ├── f
    │   │   └── winspool.drv
    │   └── r
    │       └── winspool.drv
    ├── x86_microsoft-windows-win32calc.resources_31bf3856ad364e35_10.0.18362.387_ar-sa_38566bf3d86fbe5c
    │   ├── f
    │   │   └── win32calc.exe.mui
    │   └── r
    │       └── win32calc.exe.mui
    ├── amd64_windows-shield-provider_31bf3856ad364e35_10.0.18362.900_none_fbf40d7d5ed8b490
    │   ├── f
    │   │   ├── featuretoastbulldogimg.png
    │   │   ├── securityhealthagent.dll
    │   │   ├── securityhealthhost.exe
    │   │   ├── securityhealthproxystub.dll
    │   │   ├── securityhealthservice.exe
    │   │   ├── windowsdefendersecuritycenter.admx
    │   │   └── windowssecurityicon.png
    │   ├── n
    │   │   └── featuretoastdlpimg.png
    │   └── r
    │       ├── featuretoastbulldogimg.png
    │       ├── securityhealthagent.dll
    │       ├── securityhealthhost.exe
    │       ├── securityhealthproxystub.dll
    │       ├── securityhealthservice.exe
    │       ├── windowsdefendersecuritycenter.admx
    │       └── windowssecurityicon.png
    ├── microsoft-windows-kernel-feature-package~31bf3856ad364e35~amd64~~10.0.18362.1016.cat
    ├── microsoft-windows-kernel-feature-package~31bf3856ad364e35~amd64~~10.0.18362.1016.mum
    ├── amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.18362.1016_none_79ea293316ee3bad.manifest
    ├── amd64_microsoft.windows.gdiplus_6595b64144ccf1df_1.0.18362.1016_none_e013babca5ee7b0b.manifest
    ├── msil_microsoft.hyperv.powershell.cmdlets_31bf3856ad364e35_10.0.18362.959_none_a7668eee2055cacf.manifest
    ├── wow64_microsoft-windows-p..ting-spooler-client_31bf3856ad364e35_10.0.18362.693_none_f3229700ded2ae02.manifest
    ├── amd64_windows-shield-provider_31bf3856ad364e35_10.0.18362.900_none_fbf40d7d5ed8b490.manifest
    └── x86_microsoft-windows-win32calc.resources_31bf3856ad364e35_10.0.18362.387_ar-sa_38566bf3d86fbe5c.manifest
</pre>

As you can see above there are a number of different file formats and folder types:  

- Folder Types  
    - Platforms - all folders in the upate will be prefixed with one of these  
        - **amd64** - 64-bit x86  
        - **x86** - 32-bit x86  
        - **wow64** - Windows (32-bit) On Windows 64-bit  
        - **msil** - Microsoft Intermediate Language (.NET)  
    - Differential Folders  
        - **n** - Null differentials  
        - **r** - Reverse differentials  
        - **f** - Forward differentials  
- File Types  
    - **manifest** - (*nearly*) 1-1 paired with a platform folder, these are [Windows Side-by-Side (WinSxS) manifests](https://docs.microsoft.com/en-us/windows/win32/sbscs/manifest-files-reference)
    - **cat** - security catalog  
    - **mum** - 1-1 paired with a .cat file and conatins metadata about the part of the update package that the security catalog applies to  

The platform folders and manifests actually have to do with WinSxS, as the system may store multiple versions of a binary in the `C:\Windows\WinSxS` folder, along with differential files. Take note of the fact that there are more than just EXEs and DLLs in these folders. There are PNG and MUI files as well. Any kind of file can be updated via Windows Update and WinSxS. Some folder names have been truncated; it seems that the maximum folder name length is 100 characters, with extra characters in the middle being replaced with `..`.   

For purposes of this post, I'm going to leave .mum and .cat files alone, since they are essentially just metadata and signature validation information.  

### WinSxS Manifests
The .manifest files in the patch describe how the patch is to be applied, the files that are part of the patch, the expected result of the patch in the form of file hashes, permissions of the resulting files, registry keys to set, and more. They define the effects that happen to the system other than replacing the file that is being updated.  

Here is an example manifest for the *Windows-Gaming-XboxLive-Storage-Service-Component*, whatever that is.  

<details open>
<summary>amd64_windows-gaming-xbox..e-service-component_31bf3856ad364e35_10.0.18362.836_none_a949879e457dbcd4.manifest</summary>

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v3" manifestVersion="1.0" copyright="Copyright (c) Microsoft Corporation. All Rights Reserved.">
  <assemblyIdentity name="Windows-Gaming-XboxLive-Storage-Service-Component" version="10.0.18362.836" processorArchitecture="amd64" language="neutral" buildType="release" publicKeyToken="31bf3856ad364e35" versionScope="nonSxS" />
  <dependency discoverable="no" resourceType="resources">
    <dependentAssembly>
      <assemblyIdentity name="Windows-Gaming-XboxLive-Storage-Service-Component.Resources" version="10.0.18362.836" processorArchitecture="amd64" language="*" buildType="release" publicKeyToken="31bf3856ad364e35" />
    </dependentAssembly>
  </dependency>
  <file name="XblGameSave.dll" destinationPath="$(runtime.system32)\" sourceName="XblGameSave.dll" importPath="$(build.nttree)\" sourcePath=".\">
    <securityDescriptor name="WRP_FILE_DEFAULT_SDDL" />
    <asmv2:hash xmlns:asmv2="urn:schemas-microsoft-com:asm.v2" xmlns:dsig="http://www.w3.org/2000/09/xmldsig#">
      <dsig:Transforms>
        <dsig:Transform Algorithm="urn:schemas-microsoft-com:HashTransforms.Identity" />
      </dsig:Transforms>
      <dsig:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha256" />
      <dsig:DigestValue>VjbzeELS2YXIwIhHo5f2hQm+pWTzHY8wo7dFxzfkbtA=</dsig:DigestValue>
    </asmv2:hash>
  </file>
  <file name="XblGameSaveTask.exe" destinationPath="$(runtime.system32)\" sourceName="" importPath="$(build.nttree)\">
    <securityDescriptor name="WRP_FILE_DEFAULT_SDDL" />
    <asmv2:hash xmlns:asmv2="urn:schemas-microsoft-com:asm.v2" xmlns:dsig="http://www.w3.org/2000/09/xmldsig#">
      <dsig:Transforms>
        <dsig:Transform Algorithm="urn:schemas-microsoft-com:HashTransforms.Identity" />
      </dsig:Transforms>
      <dsig:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha256" />
      <dsig:DigestValue>Ez9Rg7QMg26whoQcakH4i15oeH1NOZgbybxRdPMoi8Q=</dsig:DigestValue>
    </asmv2:hash>
  </file>
  <memberships>
    <categoryMembership>
      <id name="Microsoft.Windows.Categories.Services" version="10.0.18362.836" publicKeyToken="31bf3856ad364e35" typeName="Service" />
      <categoryInstance subcategory="XblGameSave">
        <serviceData name="XblGameSave" displayName="@%systemroot%\system32\XblGameSave.dll,-100" errorControl="normal" start="demand" type="win32ShareProcess" description="@%systemroot%\system32\XblGameSave.dll,-101" dependOnService="UserManager,XblAuthManager" imagePath="%SystemRoot%\system32\svchost.exe -k netsvcs -p" objectName="LocalSystem">
          <failureActions resetPeriod="86400">
            <actions>
              <action delay="10000" type="restartService" />
              <action delay="10000" type="restartService" />
              <action delay="10000" type="restartService" />
              <action delay="0" type="none" />
            </actions>
          </failureActions>
          <serviceTrigger action="start" subtype="RPC_INTERFACE_EVENT" type="NetworkEndpointEvent">
            <triggerData type="string" value="F6C98708-C7B8-4919-887C-2CE66E78B9A0" />
          </serviceTrigger>
        </serviceData>
      </categoryInstance>
    </categoryMembership>
    <categoryMembership>
      <id name="Microsoft.Windows.Categories" version="1.0.0.0" publicKeyToken="365143bb27e7ac8b" typeName="BootRecovery" />
    </categoryMembership>
    <categoryMembership>
      <id name="Microsoft.Windows.Categories" version="1.0.0.0" publicKeyToken="365143bb27e7ac8b" typeName="SvcHost" />
      <categoryInstance subcategory="netsvcs">
        <serviceGroup position="last" serviceName="XblGameSave" />
      </categoryInstance>
    </categoryMembership>
  </memberships>
  <taskScheduler>
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <RegistrationInfo>
        <Author>Microsoft</Author>
        <Description>XblGameSave Standby Task</Description>
        <URI>\Microsoft\XblGameSave\XblGameSaveTask</URI>
      </RegistrationInfo>
      <Principals>
        <Principal id="LocalSystem">
          <UserId>S-1-5-18</UserId>
        </Principal>
      </Principals>
      <Triggers>
        <IdleTrigger id="XblGameSave Check on CS Entry">
          <Enabled>false</Enabled>
        </IdleTrigger>
      </Triggers>
      <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>false</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <Hidden>false</Hidden>
        <RunOnlyIfIdle>true</RunOnlyIfIdle>
        <WakeToRun>false</WakeToRun>
        <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
        <Priority>7</Priority>
      </Settings>
      <Actions Context="LocalSystem">
        <Exec>
          <Command>%windir%\System32\XblGameSaveTask.exe</Command>
          <Arguments>standby</Arguments>
        </Exec>
      </Actions>
    </Task>
  </taskScheduler>
  <registryKeys>
    <registryKey keyName="HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Ubpm">
      <registryValue name="CriticalTask_XblGameSaveTask" valueType="REG_SZ" value="NT TASK\Microsoft\XblGameSave\XblGameSaveTask" />
      <registryValue name="CriticalTask_XblGameSaveTaskLogon" valueType="REG_SZ" value="NT TASK\Microsoft\XblGameSave\XblGameSaveTaskLogon" />
      <securityDescriptor name="WRP_REGKEY_DEFAULT_SDDL" />
    </registryKey>
    <registryKey keyName="HKEY_CLASSES_ROOT\AppId\{C5D3C0E1-DC41-4F83-8BA8-CC0D46BCCDE3}">
      <registryValue name="" valueType="REG_SZ" value="Xbox Live Game Saves" />
      <registryValue name="LocalService" valueType="REG_SZ" value="XblGameSave" />
      <registryValue name="AccessPermission" valueType="REG_BINARY" value="010014806400000070000000140000003000000002001c000100000011001400040000000101000000000010001000000200340002000000000018001f000000010200000000000f0200000001000000000014001f00000001010000000000010000000001010000000000050a00000001020000000000052000000021020000" />
      <registryValue name="LaunchPermission" valueType="REG_BINARY" value="010014806400000070000000140000003000000002001c000100000011001400040000000101000000000010001000000200340002000000000018001f000000010200000000000f0200000001000000000014001f00000001010000000000010000000001010000000000050a00000001020000000000052000000021020000" />
      <securityDescriptor name="WRP_REGKEY_DEFAULT_SDDL" />
    </registryKey>
    <registryKey keyName="HKEY_LOCAL_MACHINE\System\CurrentControlSet\Services\XblGameSave\Parameters">
      <registryValue name="ServiceDll" valueType="REG_EXPAND_SZ" value="%SystemRoot%\System32\XblGameSave.dll" />
      <registryValue name="ServiceDllUnloadOnStop" valueType="REG_DWORD" value="0x00000001" />
      <registryValue name="ServiceIdleTimeout" valueType="REG_DWORD" value="0x00000258" />
    </registryKey>
    <registryKey keyName="HKEY_CLASSES_ROOT\CLSID\{F7FD3FD6-9994-452D-8DA7-9A8FD87AEEF4}\">
      <registryValue name="AppId" valueType="REG_SZ" value="{C5D3C0E1-DC41-4F83-8BA8-CC0D46BCCDE3}" />
      <securityDescriptor name="WRP_REGKEY_DEFAULT_SDDL" />
    </registryKey>
    <registryKey keyName="HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\WindowsRuntime\AllowedCOMCLSIDs\{F7FD3FD6-9994-452D-8DA7-9A8FD87AEEF4}\" />
    <registryKey keyName="HKEY_CLASSES_ROOT\CLSID\{5B3E6773-3A99-4A3D-8096-7765DD11785C}\">
      <registryValue name="AppId" valueType="REG_SZ" value="{C5D3C0E1-DC41-4F83-8BA8-CC0D46BCCDE3}" />
      <securityDescriptor name="WRP_REGKEY_DEFAULT_SDDL" />
    </registryKey>
    <registryKey keyName="HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\WindowsRuntime\AllowedCOMCLSIDs\{5B3E6773-3A99-4A3D-8096-7765DD11785C}\" />
  </registryKeys>
  <localization>
    <resources culture="en-US">
      <stringTable>
        <string id="displayName" value="XblGameSave" />
        <string id="description" value="XblGameSave service" />
      </stringTable>
    </resources>
  </localization>
  <trustInfo>
    <security>
      <accessControl>
        <securityDescriptorDefinitions>
          <securityDescriptorDefinition name="WRP_REGKEY_DEFAULT_SDDL" sddl="O:S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464G:S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464D:P(A;CI;GA;;;S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464)(A;CI;GR;;;SY)(A;CI;GR;;;BA)(A;CI;GR;;;BU)(A;CI;GR;;;S-1-15-2-1)(A;CI;GR;;;S-1-15-3-1024-1065365936-1281604716-3511738428-1654721687-432734479-3232135806-4053264122-3456934681)" operationHint="replace" />
          <securityDescriptorDefinition name="WRP_FILE_DEFAULT_SDDL" sddl="O:S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464G:S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464D:P(A;;FA;;;S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464)(A;;GRGX;;;BA)(A;;GRGX;;;SY)(A;;GRGX;;;BU)(A;;GRGX;;;S-1-15-2-1)(A;;GRGX;;;S-1-15-2-2)S:(AU;FASA;0x000D0116;;;WD)" operationHint="replace" />
        </securityDescriptorDefinitions>
      </accessControl>
    </security>
  </trustInfo>
</assembly>
```
</details>

Notice all of the different fields. There are fields to modify registry keys, change file permissions, the files to patch and their resulting hashes, services to modify or change the state of, scheduled tasks to add or change, and more!

If you look inside the corresponding platform folder that this manifest describes, you will find the files that it is referring to, either as full files or (in this case) differentials:  

<pre><code class="powershell">PS > ls -Recurse amd64_windows-gaming-xbox..e-service-component_31bf3856ad364e35_10.0.18362.836_none_a949879e457dbcd4</code>
<code class="plaintext">

    Directory: C:\Users\wumb0\Desktop\patches\2020-08\patch\amd64_windows-gaming-xbox..e-service-component_31bf3856ad36
    4e35_10.0.18362.836_none_a949879e457dbcd4


Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
d-----         8/23/2020   6:50 PM                f
d-----         8/23/2020   6:50 PM                r


    Directory: C:\Users\wumb0\Desktop\patches\2020-08\patch\amd64_windows-gaming-xbox..e-service-component_31bf3856ad36
    4e35_10.0.18362.836_none_a949879e457dbcd4\f


Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----          8/6/2020   5:10 AM          35111 xblgamesave.dll
-a----          8/6/2020   5:10 AM            237 xblgamesavetask.exe


    Directory: C:\Users\wumb0\Desktop\patches\2020-08\patch\amd64_windows-gaming-xbox..e-service-component_31bf3856ad36
    4e35_10.0.18362.836_none_a949879e457dbcd4\r


Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----          8/6/2020   5:10 AM          35200 xblgamesave.dll
-a----          8/6/2020   5:10 AM            237 xblgamesavetask.exe
</code></pre>

## Automating Patch Extraction
Now that you know a bit about the structure of a patch and how to extract the files from one, it's time to introduce some automation into the mix. Greg Linares ([@laughing_mantis](https://twitter.com/laughing_mantis)) is the author of [Patch Extract](https://twitter.com/laughing_mantis/status/842100719385698305), a tool to automagically extract and organize a Microsoft Patch. He also created a tool called [Patch Clean](https://twitter.com/Laughing_Mantis/status/789346238122426368), but I am unsure if it still works with modern patches, so use at your own peril! I have slightly modified PatchExtract to fix some [powershell issues](https://github.com/PowerShell/PowerShell/issues/5576) and to quiet the output of the script. Be aware that it uses `IEX` on a user input string now, so be careful :).  

<details>
    <summary>PatchExtract.ps1</summary>
    <script src="https://gist.github.com/wumb0/306f97dc8376c6f53b9f9865f60b4fb5.js"></script>
</details>

To use, specify the path to the `PATCH` and the output `PATH` for the resulting files. PatchClean will extract the MSU, find the PSFX CAB, extract its contents, and sort the extracted patch into various folders:  

```
PS > ls X:\Patches\x64\1903\2019\9


    Directory: X:\Patches\x64\1903\2019\9


Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
da----         11/9/2019   6:30 PM                JUNK
da----         11/9/2019   6:30 PM                MSIL
da----         11/9/2019   6:32 PM                PATCH
da----         11/9/2019   6:31 PM                WOW64
da----         11/9/2019   7:06 PM                x64
da----         11/9/2019   6:31 PM                x86
-a----          9/8/2019  12:28 PM            517 Windows10.0-KB4515384-x64-pkgProperties_PSFX.txt
```

The MSIL, WOW64, x86, and x64 folders will contain all of the different platform folders with their prefixes removed. The PATCH folder will contain the patch MSU and it's contents, except for the patch PSFX metadata text file, which is left in the root of the top level folder. Finally the JUNK folder is populated with the .manifest files and also the .mum and .cat files we don't really care about. Use this tool to speed up the patch extraction process!  

## Handling Extracted Patches
A word of caution when extracting patches: always do it on your local machine, zip up the results, and then transfer to another machine for storage. An uncompressed, extracted patch is about 1.5 GB and a compressed, extracted patch is about 1 GB. This can fill up your disk space fast! Since there are tens of thousands of files in each patch, a transfer of the uncompressed directory structure will take a very long time. If you need to search through a compressed patch you can just use `unzip -l` to list the contents and then extract only the files you need.  

# Types of Patch Files
## Full Files
Platform folders without an n, f, or r directory in them contain the full file to be installed. The patch process is as simple as copying the file(s) in that folder to the place(s) specified in the corresponding .manifest file.

How would you get ahold of another copy of this file to diff against? This can be difficult, but you may be able to look in previous patches for a different version. It turns out that differentials are actually the more convenient case here!  

## Patch Deltas
When a platform folder has an n, f, or r directory in it the patch is a delta that is either applied to the existing file (r/f) or to an empty buffer to create a new file (n). Microsoft published a [whitepaper](https://docs.microsoft.com/en-us/windows/deployment/update/psfxwhitepaper) on differentials at the beginning of this year (2020). It contains some details about the technology, but not enough to be useful in manually applying the deltas, other than knowing what f, r, and n mean.  

### Types of Deltas
As mentioned previously, there are three types of deltas:

- **Forward differentials (f)** - brings the base binary (.1) up to that particular patch level  
- **Reverse differentials (r)** - reverts the applied patch back to the base binary (.1)  
- **Null differentials (n)** - a completely new file, just compressed; apply to an empty buffer to get the full file  

You will always see r and f folders together inside of a patch because you need to be able to revert the patch later on to apply a newer update.  

### Delta APIs
Before I start diving into the format of deltas and applying them to files, it is worth noting that Microsoft provides (slightly outdated, but still relevant) [developer documentation](https://docs.microsoft.com/en-us/previous-versions/bb417345(v=msdn.10)) on the Delta Compression APIs. There are actually two completely different APIs for creating and applying patch deltas: [PatchAPI](https://docs.microsoft.com/en-us/previous-versions/bb417345(v=msdn.10)#patchapi) and [MSDELTA](https://docs.microsoft.com/en-us/previous-versions/bb417345(v=msdn.10)#msdelta). For this post I will be focusing on the MSDELTA API since it is newer and soley used in new patches that are being published. Besides, if you call into the MSDELTA API and provide a PatchAPI patch file it will recognize that and apply the patch anyway by calling into `mspatcha.dll`.  

Functions in the MSDELTA API are contained inside of `msdelta.dll`.  

- **CreateDelta(A|W|B)** - create a delta from a file (A|W) or buffer (B)  
- **ApplyDelta(A|W|B)** - apply a delta from a file to a file (A|W) or from a buffer (B) to a buffer (B)  
- **ApplyDeltaProvidedB** - apply a delta from a buffer to a provided buffer that is callee allocated (no need to call `DeltaFree`)  
- **GetDeltaInfo(A|W|B)** - get metadata about the patch and calculate the signature of a delta file (A|W) or buffer (B)  
- **GetDeltaSignature(A|W|B)** - calculate the signature of a delta file (A|W) or buffer (B).  
- **DeltaNormalizeProvidedB** - puts a delta buffer in a standard state in order to be hashed by an algorithm not supported by MSDELTA  
- **DeltaFree** - free a delta buffer created by `CreateDeltaB` or `ApplyDeltaB`  

I'll be using `ApplyDeltaB` to apply multiple patch delta files to a file buffer and then `DeltaFree` to free the generated buffer(s). Looking more closely at `GetDeltaInfo*` and `DeltaNormalizeProvidedB` are on my TODO list, but aren't all that important for the purposes of this post.    

Other interesting features of the MSDELTA API is the ablility to apply the delta to specific binary sections via [file type sets](https://docs.microsoft.com/en-us/previous-versions/bb417345(v=msdn.10)#file-type-sets). There's more research to be done behind those as well!  

### Delta Formats
At first glance, you'd be convinced that the files in the delta folders inside of the patch are the full binaries because of their extensions. The first clue that they are not is the size of them, as they are considerably smaller than you'd expect a full binary to be. The other is that the file format is something completely different! Opening up a few of the extracted files in a hex editor shows this quickly:

<pre><code class="plaintext">wumb0 in patches$ xxd 2020-08/patch/amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.18362.1016_none_79ea293316ee3bad/f/ntoskrnl.exe | head
00000000: e45a 9bd5 5041 3330 6e2b 8720 fa6a d601  .Z..PA30n+. .j..
00000010: b05e 10d0 c7c4 0cc4 69bc c401 4021 00b4  .^......i...@!..
00000020: ab4f 2159 0f6a 2ab4 7848 f5df d9cd 2fb8  .O!Y.j*.xH..../.
00000030: b30b 0400 0000 0a00 0000 0000 0000 9836  ...............6
00000040: 86a9 cb02 f05b dddd dddd dddd dddd dddd  .....[..........
00000050: dd2d 4dd2 333d d143 3dd4 ddd3 0128 c6c4  .-M.3=.C=....(..
00000060: cccc cccc cccc cccc c31c 22c2 cccc 3c2c  .........."...<,
00000070: cccc ccc3 7280 3000 d07f 0700 a8ff 1700  ....r.0.........
00000080: fc7f 00a0 ff03 80fc 5f00 90ff 0c00 ecfc  ........_.......
00000090: 8701 60e5 ff19 1100 7cff 5f00 f8ff 0080  ..`.....|._.....

wumb0 in patches$ xxd 2020-08/patch/amd64_microsoft-onecore-reverseforwarders_31bf3856ad364e35_10.0.18362.997_none_f7e8eb88fe7a4f39/r/gdi32.dll | head
00000000: db07 a73a 5041 3330 f494 3566 d8dd d401  ...:PA30..5f....
00000010: b05e 10d0 c7c4 0c02 6006 0e00 0a01 5d41  .^......`.....]A
00000020: 1606 6042 f2b4 03a7 1295 36ee fbe7 2e01  ..`B......6.....
00000030: 0100 0000 0c00 0000 0000 0000 b0b4 5e9e  ..............^.
00000040: 0802 402d aaaa aaaa aaaa aaaa aaaa aa0a  ..@-............
00000050: aaaa 2aa2 0117 dba2 aaaa aaaa aaaa aaaa  ..*.............
00000060: a2a2 111a c900 f87f 03c0 fd17 00e4 ff00  ................
00000070: f8ff 00d0 3f00 fa1f 00ff 0fd6 00b3 0340  ....?..........@
00000080: 20ee ea69 7500 00d8 1069 a703 f54e 5d0f   ..iu....i...N].
00000090: d301 2557 07ec 681d 9a0f caa7 03b5 c81a  ..%W..h.........

wumb0 in patches$ xxd 2020-08/patch/amd64_microsoft-windows-f..ysafety-refreshtask_31bf3856ad364e35_10.0.18362.997_none_b453df19f80f8d5b/f/wpcmon.png | head
00000000: 400b 0a1a 5041 3330 008b e980 ac49 d601  @...PA30.....I..
00000010: b07e 4000 00c3 2709 1c00 1402 c30c 6217  .~@...'.......b.
00000020: 48c6 6ce7 51b1 9b27 8855 9a3e 010b b103  H.l.Q..'.U.>....
00000030: 003c 12                                  .<.
</code></pre>

These are not PE or PNG files and one clear pattern emerges! `PA30` starting at offset 4 in every file, no matter what the type is. But what are those first four bytes? In my initial attempts at working with deltas I was getting frustrated because using any of the `ApplyDelta*` functions from `msdelta.dll` resulted in errors. Reasearch on the file format (`PA30`) eventually led me to [the patent](https://patents.google.com/patent/US20070260653) for the technology, which is interesting if you want to take a look, but provided no answer to my issue. In a true [FILDI](https://www.urbandictionary.com/define.php?term=FILDI) moment I just cut off the first four bytes, since file magic is usually at the start of the file (right?) and to my surprise the delta applied! Excellent, so what is that 4 bytes? And is that format documented anywhere? After a bit of thinking about seemingly useless bytes on files I'd encountered before, a checksum came to mind, specifically the most common 4 byte checksum I could think of: **CRC32**! So I hopped into `ipython` to try it out:

<pre><code>
In [1]: import zlib

In [2]: data = open("2020-08/patch/amd64_microsoft-windows-f..ysafety-refreshtask_31bf3856ad364e35_10.0.18362.997_none_
   ...: b453df19f80f8d5b/f/wpcmon.png", "rb").read()

In [3]: hex(zlib.crc32(data[4:]))
Out[3]: '0x1a0a0b40'

In [4]: hex(int.from_bytes(data[:4], 'little'))
Out[4]: '0x1a0a0b40'
</code></pre>

My suspicion was confirmed! Totally a lucky guess and it isn't documented anywhere that I can find.  

After going through this discovery, I thought it would make an interesting CTF challenge. So I designed a CTF challenge for the yearly [RITSEC](http://sparsa.rip/) CTF. It was supposed to be called *patch-tuesday* but I accidentally uploaded the original .sys file with the flag in it. The challenge ended up being called *patch-2sday* and involved invoking the MSDELTA API to patch a file after stripping off a prepended CRC32. Greetz to [layle](https://twitter.com/layle_ctf) and yuana for being the only two to solve it! You can find a write-up of the solution to the challenge on the [RITSEC Github](https://github.com/ritsec/RITSEC-CTF-2019/tree/master/Misc/patch-tuesday); the repo also has the [script I used to create the delta](https://github.com/ritsec/RITSEC-CTF-2019/blob/master/Misc/patch-tuesday/make_delta.py), if you are interested in that.  

### Generating Useful Binaries Out of Deltas
Let's say that I have a Windows 10 1903 x64 machine and I want to look at the differences between ntoskrnl.exe from [July](https://support.microsoft.com/en-us/help/4565483) to [August](https://support.microsoft.com/en-us/help/4565351_) 2020. The machine has the [October 2019](https://support.microsoft.com/en-us/help/4524147/windows-10-update-kb4524147_) patches installed currently. I am going to copy the ntoskrnl.exe binary out of `C:\windows\system32` and use the MSDELTA API to apply deltas to the binary to get the versions I want.  

#### Reverse, then Forward
The version of the kernel binary that I have is 10.0.18362.388. I will need the reverse differential for this particular version to roll it back to version 10.0.18362.1 before I start patching up. I could download and extract the October 2019 update, but that would take a long time. Recall that when patches are installed, Windows Update will place binaries and differentials in the `C:\Windows\WinSxS` directory. You can run some powershell to find the delta you need already on the system:  

<pre><code class="powershell">PS > Get-ChildItem -Recurse C:\windows\WinSxS\ | ? {$_.Name -eq "ntoskrnl.exe"}</code>
<code class="plaintext">    Directory:
    C:\windows\WinSxS\amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.18362.388_none_c1e023dc45da9936


Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-a---l        10/4/2019   6:06 AM        9928720 ntoskrnl.exe


    Directory:
    C:\windows\WinSxS\amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.18362.388_none_c1e023dc45da9936\f


Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-a----        9/30/2019   6:39 PM         479646 ntoskrnl.exe


    Directory:
    C:\windows\WinSxS\amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.18362.388_none_c1e023dc45da9936\r


Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-a----        9/30/2019   6:39 PM         476929 ntoskrnl.exe
</code></pre>

The full version as well as both the forward and reverse differentials are present. Now I have all of the files I need to perform the deltas and get the two versions of the kernel that I want to diff!  

#### Applying a Patch Delta with the MSDELTA API
I decided to write a python program to interact with `msdelta.dll` and invoke the `ApplyDelta` family of functions. If you have never used python `ctypes` before then the script might seem a little strange at first, but I promise it is a very powerful tool to have in your utility belt. Among other things, `ctypes` can act as a [Foreign Function Interface](https://en.wikipedia.org/wiki/Foreign_function_interface) to C; it allows you to call functions inside of DLLs, create structures and unions, raw buffers, and has a number of primitive types implemented such as `c_uint64`, `c_char_p`, and Windows types like `DWORD`, `HANDLE`, and `LPVOID`.  

If you're interested in more uses of `ctypes` check out my post on [making efficient use of ctypes structures](|filename|a-better-way-to-work-with-raw-data-types-in-python.md), though keep in mind that it is written for python 2.7 and some things may have to change from the examples to support python 3. I'd like to do an addendum post sometime that ports the code to python 3.

Below is the final patch delta applying script written for python 3 (click the filename to expand). It uses all python builtins, and you'll need to be on a Windows system to run it, as it imports `msdelta.dll` and uses `ApplyDeltaB` to apply patches. It even supports legacy PatchAPI patches (`PA19`).  

<details>
    <summary>delta_patch.py</summary>
    <script src="https://gist.github.com/wumb0/9542469e3915953f7ae02d63998d2553.js"></script>
</details>

Here's a printout of the program's usage, so you can get a feel for what it provides and how to use it.  

```
PS > python X:\Patches\tools\delta_patch.py -h
usage: delta_patch.py [-h] (-i INPUT_FILE | -n) (-o OUTPUT_FILE | -d) [-l] patches [patches ...]

positional arguments:
  patches               Patches to apply

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT_FILE, --input-file INPUT_FILE
                        File to patch (forward or reverse)
  -n, --null            Create the output file from a null diff (null diff must be the first one specified)
  -o OUTPUT_FILE, --output-file OUTPUT_FILE
                        Destination to write patched file to
  -d, --dry-run         Don't write patch, just see if it would patchcorrectly and get the resulting hash
  -l, --legacy          Let the API use the PA19 legacy API (if required)
```  

To generate the binaries I want I'm going to apply the reverse delta and then each forward delta, creating two output files:  

<pre><code class="powershell">PS > python X:\Patches\tools\delta_patch.py -i ntoskrnl.exe -o ntoskrnl.2020-07.exe .\r\ntoskrnl.exe X:\Patches\x64\1903\2020\2020-07\x64\os-kernel_10.0.18362.959\f\ntoskrnl.exe
</code><code class="plaintext">Applied 2 patches successfully
Final hash: zZC/JZ+y5ZLrqTvhRVNf1/79C4ZYwXgmZ+DZBMoq8ek=
</code><code class="powershell">PS > python X:\Patches\tools\delta_patch.py -i ntoskrnl.exe -o ntoskrnl.2020-08.exe .\r\ntoskrnl.exe X:\Patches\x64\1903\2020\2020-08\x64\os-kernel_10.0.18362.1016\f\ntoskrnl.exe
</code><code class="plaintext">Applied 2 patches successfully
Final hash: UZw7bE231NL2R0S4yBNT1nmDW8PQ83u9rjp91AiCrUQ=
</code></pre>  

The patches applied successfully and now I have two full binaries, one from August 2020's patchset and another from July 2020. The hashes that are generated should match up with the ones in the corresponding manifest files!  

#### What About Null Diffs?
Before I move on to diffing the two kernel versions, I wanted to explain how to use the delta_patch tool to generate a full file out of a null (n) differential. There is a built in option for it! Use the `-n` flag and specify an output file (but no input file) and delta_patch will apply the delta to an empty buffer. The result is the full file!  

For example: 

```powershell
PS > python X:\Patches\tools\delta_patch.py -n -o vmcomputeagent.exe  2020-08\patch\amd64_hyperv-compute-guestcomputeservice_31bf3856ad364e35_10.0.18362.329_none_e3769ae1a46d95f1\n\vmcomputeagent.exe
Applied 1 patch successfully
Final hash: B5mZQ8i4OU22UQXOaDhLHNtLNhos6exfTHlsPzTmXGo=
PS > wsl -e file vmcomputeagent.exe
vmcomputeagent.exe: PE32+ executable (GUI) x86-64, for MS Windows
```

As you can see from the output of `file`, the null differential has been expanded into a full executable. You can also apply a forward differential, but only after the null one, of course, otherwise you wouldn't have a file to patch!  

# Patch Diffing
There are [plenty](https://googleprojectzero.blogspot.com/2017/10/using-binary-diffing-to-discover.html) [of](https://beistlab.files.wordpress.com/2012/10/isec_2012_beist_slides.pdf) [resources]() [available](https://www.slideshare.net/cisoplatform7/bruh-do-you-even-diffdiffing-microsoft-patches-to-find-vulnerabilities) [on](https://apprize.best/security/ethical_1/20.html) [binary](http://joxeankoret.com/blog/2015/03/13/diaphora-a-program-diffing-plugin-for-ida-pro/) [diffing](https://deadlisting.com/files/Sims_Patch_Diff_BSides_Baltimore.pdf) and [comparing diffing tools](https://malware.news/t/comparative-analysis-between-bindiff-and-diaphora-patched-smokeloader-study-case/40996), so I won't be diving into how to use them, but for completeness sake, I'm going to diff the two kernels I just created!  

I am going to open both versions of `ntoskrnl.exe` in IDA Pro 7.5, accept the symbol download prompt, and let the auto-analysis finish. Then, I'm going to close the newer of the two versions (2020-08) and call up [BinDiff](https://www.zynamics.com/bindiff.html) to diff the new version (secondary) against the older one (primary).  

<center>
![Matched Functions]({static}/images/extracting-and-diffing-ms-patches-in-2020/patchdiff-matched-functions.png)  
<small>There are only a few changed functions between the two versions</small>
</center>

I'm going to look at `MmDuplicateMemory` because changes in functions related to memory always catch my eye! Below is an overview of the combined call graph in BinDiff. Green blocks are unchanged, yellow blocks have differences, red blocks were removed by the patch, and gray blocks were added by the patch.  

<center>
![Overview graph]({static}/images/extracting-and-diffing-ms-patches-in-2020/bindiff-overview.png)  
<small>Graph overview with BinDiff in combined mode</small>
</center>

There are many changes, but I wanted to highlight one block in particular right near the top of the function (indicated by the red arrow):  

<center>
![Changed block]({static}/images/extracting-and-diffing-ms-patches-in-2020/bindiff-changed-block.png)  
<small>Can you spot the important change?</small>
</center>

It looks like the return value from the function `KeWaitForSingleObject` was not checked in the unpatched version and the patch added a check to make sure that the function returns a value of 0 (`WAIT_OBJECT_0`). In terms of judging the severity of this bug, more work needs to be done to investigate what waitable object is being passed to `KeWaitForSingleObject` (cs:[0x1404681D0]), if there is any way to get the wait to fail reliably, and what behavior that failure would cause. This is an exercise left up to the reader.  

# Wrap Up
Thanks for sticking around to the end. I hope you learned a thing or two. If you have questions, comments, concerns, complaints, or corrections please feel free to reach out to me. I'm on twitter at [@jgeigerm](https://twitter.com/jgeigerm). Also reach out if the scripts break, they shouldn't do that. I'm going to try and post more Windows related content in the future, so stay tuned. I hope to see you in [SEC760](https://www.sans.org/cyber-security-courses/advanced-exploit-development-penetration-testers/) someday! I recently re-wrote the kernel exploitation day and it's been a blast to teach!  

That's all for now, ~~have fun inside~~!  

