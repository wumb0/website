Title: Some Metasploit Annoyances
Date: 2015-03-27 14:58
Category: Old Posts
Tags: old
Slug: Some-Metasploit-Annoyances
Authors: wumb0

I don't know how I broke metasploit, but I did. It reported an incorrect password for the msf3 postgres user. Here's how I fixed it after some digging.

<pre><code class="bash">
su - postgres
psql
postgres=# alter user msf3 with encrypted password 'mypasswordhere';
postgres=# \q
vim /opt/metasploit/apps/pro/ui/config/database.yml
</code></pre>

Replace database password with whatever password you just set and enjoy msfconsole and related tools again. 
