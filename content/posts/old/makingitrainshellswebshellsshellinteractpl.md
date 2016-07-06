Title: Making it Rain Shells, Web Shells - shell_interact.pl
Date: 2014-03-24 18:54
Category: Old Posts
Tags: old
Slug: Making-it-Rain-Shells,-Web-Shells---shell_interact.pl
Authors: wumb0

shell_interact is a project I have been working on since the new year and it is just finally starting to shape up into a nice little tool. PHP backdoor shells can be fun, especially when the permissions on the box have been messed with (i.e. www-data is allowed sudo with no password, /etc/shadow has wide open permissions, etc.). The downside is that you have to type each command into the URL bar of the browser. Kind of annoying. So I started on a solution.

Perl is one of my stronger languages. I love regex and all of the built in functions it has. So I decided to use it for this project, having just come out of the perl class at RIT (with the notorious Dan Kennedy).

The script utilizes curl to search for the shell and allow the user to enter commands in a bash like environment if one is found. All of the input is URL encoded so the activity from the program doesn't look as suspicious on the target server. If you enter a command that expects more input (such as vim) and curl hangs, using control-c will terminate curl and return you to the web shell prompt. Stderr is redirected to stdin for every command to allow you to see errors without having to do it manually. It also enables the cd command by changing directories before each user entered command is run. It's pretty nifty, and the code is mostly commented.

You can find the code on my GitHub, you can read more about the features/bugs there: <a title="here it is!" href="https://github.com/jgeigerm/web_shell" target="_blank">https://github.com/jgeigerm/web_shell</a>

<a href="/images/old/uploads/2014/03/Screen-Shot-2014-03-24-at-8.01.03-PM.png"><img class="uk-align-center" alt="shell_interact.pl" src="/images/old/uploads/2014/03/Screen-Shot-2014-03-24-at-8.01.03-PM.png" width="864" height="425" /></a>
