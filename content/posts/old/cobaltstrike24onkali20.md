Title: Cobalt Strike 2.4 on Kali 2.0
Date: 2015-10-21 02:38
Category: Old Posts
Tags: old
Slug: Cobalt-Strike-2.4-on-Kali-2.0
Authors: wumb0

Cobalt Strike 3.0 came out lacking metasploit integration. Also, Cobalt Strike 2.4 (<a href="http://finishyour.beer/cobaltstrike-trial.tgz">grab that here if you need it</a>) doesn't work with the version of Metasploit that is built into Kali 2.0. That's okay, because you can still compile the metasploit framework to work with Cobalt Strike 2.4.
<pre><code class="bash">
curl -sSL https://get.rvm.io \| bash -s stable
source /usr/local/rvm/scripts/rvm
apt-get install libpq-dev libpcap-dev
service postgresql start
msfconsole
exit (this was to make sure the msf database was created)
rvm install 1.9.3
cd /usr/share
git clone https://github.com/rapid7/metasploit-framework cs-msf
cd cs-msf
git checkout dc48987
rvm use 1.9.3
bundle install
for i in msf*;do update-alternatives --install /usr/bin/$i $i $PWD/$i 1;done
cd ../metasploit-framework
for i in msf*;do update-alternatives --install /usr/bin/$i $i $PWD/$i 2;done
rm -rf $(dirname $(which msfconsole))/msf*
update-alternatives --config msfrpcd < <(echo 1)
cp /usr/share/metasploit-framework/config/database.yml /usr/share/cs-msf/config
export MSF_DATABASE_CONFIG=/usr/share/cs-msf/config/database.yml
</code></pre>
Then, edit the database.yml file @ /usr/share/cs-msf/config/database.yml:
<ul>
	<li>Delete the &pgsql after development</li>
	<li>Delete all profiles after development (after first line with nothing on it)</li>
	<li>Change development to production (1st line)</li>
	<li>Save the file</li>
</ul>
You should now be able to run cobalt strike 2.4 just fine.

To switch back just open a new terminal OR:
<pre><code class="bash">
update-alternatives --config msfrpcd < <(echo 0)
rvm use system
</code></pre>
And the next time you want to use 2.4 (put this in a script):
<pre><code class="bash">
\#!/bin/bash
source /usr/local/rvm/scripts/rvm
rvm use 1.9.3
update-alternatives --config msfrpcd < <(echo 1)
export MSF_DATABASE_CONFIG=/usr/share/cs-msf/config/database.yml 
./cobaltstrike &>/dev/null &disown
read -p "Press enter once the RPC server has started up..." i
update-alternatives --config msfrpcd < <(echo 0)
</code></pre>
I'm pretty sure there is a more elegant way to do this rather than using update-alternatives... but this works for now.
As a side note... tracking down the exact revision where ruby 2.1 became a dependency was terrible. Yes, this is the absolute LAST commit you can get and compile without ruby 2.1. I might update this with a solution for later versions of metasploit before the MsgPack library update (which breaks cobaltstrike much more than I'm willing to fix!).
