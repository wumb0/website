Title: PoliCTF 2015 - Hanoi-as-a-Service - Pwnable 50
Date: 2015-07-12 10:43
Category: Old Posts
Tags: old
Slug: PoliCTF-2015---Hanoi-as-a-Service---Pwnable-50
Authors: wumb0

This challenge gave nothing but a URL: haas.polictf.it 80. For some reason the organizers decided to run a lot of their services on port 80. Netcatting in reveals a simple hanoi solver. Usually when given a service like this with no binary I start inputting values to see what information I can get or if I can cause any errors/crashes. I try a positive, then a negative number.

<a href="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.47.21-PM.png"><img class="uk-align-center" src="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.47.21-PM.png" alt="Connecting" width="475" height="232" /></a>

The program had an error, and it printed out for us. What is prolog?
<blockquote><b>Prolog</b> is a general purpose logic programming <b>language</b> associated with artificial intelligence and computational linguistics. -Wikipedia</blockquote>
With a little bit of Googling around I tried some syntax:

<a href="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.47.58-PM.png"><img class="uk-align-center" src="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.47.58-PM.png" alt="Causing errors" width="475" height="184" /></a>

It looks like it is taking our input and putting it directly between the two parentheses of the hanoi function. This is textbook command injection. To test, I decided to print something simple.
[[more]]
<a href="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.48.32-PM.png"><img class="uk-align-center" src="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.48.32-PM.png" alt="Playing around" width="475" height="130" /></a>

Since the statement ended with a ")." I could leave that off. I did a bit of looking around for ways to execute system commands and I found <strong>exec</strong>. I ran a test with feedback to make sure it worked.

<a href="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.50.22-PM.png"><img class="uk-align-center" src="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.50.22-PM.png" alt="whoami" width="475" height="105" /></a>

Got it, so now all there is left to do is find the flag. Usually the flags are kept in the home directory of the user they are running as so I used <strong>ls</strong> to maneuver my way around. The syntax for adding arguments is strange in prolog.

<a href="/images/old/uploads/2015/07/Finding-flag-1.png"><img class="uk-align-center" src="/images/old/uploads/2015/07/Finding-flag-1.png" alt="Finding flag 1" width="475" height="127" /></a>

<a href="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.59.31-PM.png"><img class="uk-align-center" src="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.59.31-PM.png" alt="Finding flag 2" width="475" height="166" /></a>

Catting the file shows the flag!

<a href="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.59.18-PM.png"><img class="uk-align-center" src="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-10.59.18-PM.png" alt="The Flag" width="475" height="101" /></a>
