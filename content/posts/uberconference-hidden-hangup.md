Title: Uberconference Hidden Hangup Button
Date: 2019-01-24 18:15
Category: Misc
Tags: web
Slug: uberconference-hidden-hangup
Authors: wumb0

I was on an uberconference call the other day and the leader of the conference mentioned how they had the ability to disconnect anyone on the call with a "Hangup" button next to the mute and profile buttons. Looking at the interface a caller with the icons expanded looks like this:  

![caller interface]({filename}/images/uberconference-caller.png)

Now let's inspect...  Going down to where the profile and mute buttons are located it looks like there's one more, hidden button available:

![hangup hidden html]({filename}/images/uberconference-hangup-hidden.png)

Removing the *style="display: none;"* attribute from the div causes the button to show...  

![hangup enabled]({filename}/images/uberconference-hangup.png)

It's funny because it actually works. If you click it the person gets booted from the call, even if you aren't an admin/call leader. Web is hard.  
Thanks for reading.  
