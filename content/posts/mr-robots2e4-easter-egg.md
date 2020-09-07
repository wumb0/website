Title: Mr. Robot Season 2 Episode 4 Easter Egg
Date: 2016-07-28 9:00
Modified: 2016-07-28 10:40
Category: Misc
Tags: Mr. Robot, easter egg, fsociety
Slug: mr-robots2e4-easter-egg 
Authors: wumb0

After seeing [the last Mr. Robot easter egg](http://imgur.com/gallery/RKRAi) from season 2 episode 1 I have been on the lookout for IP's and domains to try and go after. At the end of season 2 episode 4 (init_1.asec) Elliot logs into an IRC server and the IP address is clearly visible as **192.251.68.53**.
![ip]({static}/images/mrrobotip.png)

I decided to scan that host with nmap and got the following results:
```bash
→ sudo nmap -sS -Pn -sV -n 192.251.68.253
Starting Nmap 7.12 ( https://nmap.org ) at 2016-07-28 08:46 EDT
Nmap scan report for 192.251.68.253
Host is up (0.023s latency).
Not shown: 996 filtered ports
PORT     STATE SERVICE     VERSION
21/tcp   open  ftp?
80/tcp   open  http-proxy  F5 BIG-IP load balancer http proxy
554/tcp  open  rtsp?
7070/tcp open  realserver?
Service Info: Device: load balancer
```

HTTP up, cool. I went to the site and it was a fake IRC server with the hostname irc.colo-solutions.net:
![irc]({static}/images/mrrobotirc.png)

After it logged me in as *D0loresH4ze* I was dropped in a channel called *#th3g3ntl3man* with the all too familiar *samsepi0l* (for the uninformed, Sam Sepiol was the alias Elliot used in season one to gain access to Steel Mountain, a secure datacenter). 

After poking around and trying to get samsepi0l to say something besides "i don't have time for this right now." I played the roll of Darlene and entered what she said in the show:
![input]({static}/images/mrrobotirc2.png)

Here is the respone I got:
![response]({static}/images/mrrobotchat.png)

> they have changed their standard issue. we have a way in.

What does that even mean? At the end of the episode this line of dialogue was not shown. Only *wait for my instructions* was. The scene after shows a news article from Business Insider titled *FBI gives up Blackberry for Android*. I assume that is their "standard issue" and he is going to hack into them via their smartphones. That's a bold move, we'll see how it plays out next week.

After this I investigated a couple of other addresses I found (192.251.68.240, 104.97.14.93, 192.251.68.249, irc.eversible.co) but none of them turned up anything. I looked at the page source too, hoping to find something hidden in the javascript or HTML. Nothing there either... I guess we will just have to wait and see where this goes! I'll probably take a closer look at this after work, but I thought this would be cool to share now.
