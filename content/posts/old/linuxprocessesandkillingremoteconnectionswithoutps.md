Title: Linux Processes (and killing remote connections) Without ps
Date: 2014-04-09 11:34
Category: Old Posts
Tags: old
Slug: Linux-Processes-and-killing-remote-connections-Without-ps
Authors: wumb0

The other day I was posed with a unique problem: find the PID's of remote connections without the `ps` command. I was in a practice red team/blue team scenario on the blue team side where I was letting the attacker in on purpose and killing their connection from time to time. This exercise was to allow people who don't have much experience on red team the chance to get in and mess with things. We even gave them a head start, which was about 20 minutes on the boxes making them vulnerable before the blue team got to see/touch them. When I sat down a few things had been changed: aliases in bash_profile, cron tasks, web shells (it was a web box), and some other nonsense. I quickly fixed everything and put up my iptables rules. A quick issue of the `w` command assured me that nobody was in.

I ended up getting bored and creating a NOPASSWD sudo account bob:bob for people to own me with. One person decided to log in and try their hand at ruining my box. I made it a point to kill their connection every so often using `w` to figure out the pts they were on, `ps aux | grep pts/x` (x being their session number) to figure out the process ID of their login shell, and then `kill -9 ` to finally kick them off.

The person attacking me saw that I kept killing their connection so they deleted the ps command. I was left helpless in trying to figure out what processes they were running. Of course there are two fairly obvious solutions, one that I thought of and one that I didn't at the time. I thought to reinstall the ps binary with `yum install --reinstall coreutils` but there was no internet in the lab I was in so that wasn't an option. I spent my time trying to figure out one liners to kill remote connections without using ps...

The first method I thought up was using the /proc directory, as all of the processes are in there by process ID. I started exploring all of the options the `find` command had to offer. Since the <em>environ</em> file within processes' directories listed the the variable <em>TTY</em> I had a place to start. Here is what I came up with:
<pre><code>
find /proc -maxdepth 2 -name environ -exec grep /dev/pts {} \; | cut -d/ -f3 | xargs kill -9
</code></pre>
<ul>
	<li><strong>find</strong> - the find command (use `man find` for details, this command is very powerful)</li>
	<li><strong>/proc</strong> - the directory that find looks in</li>
	<li><strong>-maxdepth 2</strong> - Tells find to search at the maximum two directories deep. This is done because the environ file is located deeper in processes' directory but is the same file. We only want one match.</li>
	<li><strong>-name environ</strong> - Specifies the name of the file we are looking for. In this case it is environ.</li>
	<li><strong>-exec grep /dev/pts {} \\;</strong> - Find executes the command `grep /dev/pts` on each file found. The `{} \;` is just part of the syntax</li>
	<li><strong>cut -d/ -f3</strong> - takes the output of the find command and extracts the PID from it (the find command will output "Binary file /proc/&lt;PID&gt;/environ matches" so we are finding the third field (-f3) delimited by / (-d/), which is the PID)</li>
	<li><strong>xargs kill -9</strong> - takes in the PIDs as arguments to kill and force kills the process</li>
</ul>
One problem with this method is that on some distributions (such as CentOS) some sessions that are local are listed as pts sessions, so running the `w` command to check your session is a good idea before you run this. If you are running under a pts the command would look something like this:
<pre><code>
find /proc -maxdepth 2 -name environ -exec sh -c 'grep -v /dev/pts $0 | grep -av /pts/<strong>#</strong> &gt;/dev/null' {} \; -print | cut -d/ -f3 | xargs kill -9
</code></pre>
<ul>
	<li><strong>find</strong> - the find command (use `man find` for details, this command is very powerful)</li>
	<li><strong>/proc</strong> - the directory that find looks in</li>
	<li><strong>-maxdepth 2</strong> - Tells find to search at the maximum two directories deep. This is done because the environ file is located deeper in processes' directory but is the same file. We only want one match.</li>
	<li><strong>-name environ</strong> - Specifies the name of the file we are looking for. In this case it is environ.</li>
	<li><strong>-exec sh -c 'grep -a /dev/pts $0 \| grep -av /pts/<strong>#</strong> &gt;/dev/null' {} \\;</strong> - Find executes the command `grep -a /dev/pts \| grep -av /pts/<strong>#</strong>` on each file found. The `{} \\;` is just part of the syntax. In this case the "<strong>#</strong>" is the pts you are on. It will be grep-ed out of the output, therefore not showing in the -print result.</li>
	<li><strong>-print</strong> - prints any files that have output when run through the -exec portion.</li>
	<li><strong>cut -d/ -f3</strong> - takes the output of the find command and extracts the PID from it (the find command will output "/proc/&lt;PID&gt;/environ" so we are finding the third field (-f3) delimited by / (-d/), which is the PID)</li>
	<li><strong>xargs kill -9</strong> - takes in the PIDs as arguments to kill and force kills the process</li>
</ul>
The other route that was brought to my attention was through netstat to kill remote connections by pid. This is arguably more effective than the one above.
<pre><code>
netstat -apunt | grep STAB | awk '{print $7}' | cut -d/ -f1 | xargs kill -9
</code></pre>
<ul>
	<li><strong>netstat -apunt</strong> - Prints active connections.</li>
	<li><strong>grep STAB</strong> - Picks established connections out of the output of netstat</li>
	<li><strong>awk '{print $7}'</strong> - prints "&lt;PID&gt;/&lt;PTS #&gt;", which is the 7th field in the output of netstat.</li>
	<li><strong>cut -d/ -f1</strong> - takes "&lt;PID&gt;/&lt;PTS #&gt;" and extracts the PID from it</li>
	<li><strong>xargs kill -9</strong> - takes in the PIDs as arguments to kill and force kills the process</li>
</ul>
This got me thinking on how to kill backdoors such as the <a title="Link to the backdoor code" href="http://www.ussrback.com/UNIX/penetration/rootkits/blackhole.c" target="_blank">b(l)ackhole backdoor</a>. Processes that run any type of shell directly are probably malicious. I have found this in my tests. To find active backdoors I tried the following:
<pre><code>
find /proc -maxdepth 2 -name cmdline -exec egrep "/bin/[a-z]+?sh" {} \; | cut -d/ -f3 | xargs kill -9
</code></pre>
<ul>
	<li><strong>find</strong> - the find command (use `man find` for details, this command is very powerful)</li>
	<li><strong>/proc</strong> - the directory that find looks in</li>
	<li><strong>-maxdepth 2</strong> - Tells find to search at the maximum two directories deep. This is done because the cmdline file is located deeper in processes' directory but is the same file. We only want one match.</li>
	<li><strong>-name cmdline</strong> - Specifies the name of the file we are looking for. In this case it is cmdline.</li>
	<li><strong>-exec egrep "/bin/[a-z]+?sh" {} \\;</strong> - Find executes the command `egrep "/bin/[a-z]+?sh"` on each file found. This will find any reference to a shell launched. The `{} \\;` is just part of the syntax.</li>
	<li><strong>cut -d/ -f3</strong> - takes the output of the find command and extracts the PID from it (the find command will output "Binary file /proc/&lt;PID&gt;/environ matches" so we are finding the third field (-f3) delimited by / (-d/), which is the PID)</li>
	<li><strong>xargs kill -9</strong> - takes in the PIDs as arguments to kill and force kills the process</li>
</ul>
Additionally you can use netstat to monitor established connections.

Some other approaches are to use lsof and who to figure out PIDs. The lsof command is used to figure out what programs have what files open. It has a ton of options but with just a few of them it can be very easy to see what is being accessed. The options we care about allow us to see what files are open, who opened them, and what connections are being made. It looks something like this: (thanks Luke!)
<pre><code>
lsof -nPi
</code></pre>
<strong>n</strong> - Ignore host names
<strong>P</strong> - Do not convert port numbers to port names
<strong>i</strong> - see internet connections files are making

What is unique about this is that it will show what files are listening or have established connections. It becomes much easier to see if there is some sort of backdoor listening and what it is called.

For the who command I use the -u option and present another method of killing things:
<pre><code>
who -u | grep pts | awk '{print $6}' | xargs kill
</code></pre>
Again here keep in mind that some operating system's window manager list as the lowest pts, so grep -v that before you go and kill all connections.
