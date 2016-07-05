Title: Mass Pwning via SSH with PXSSH
Date: 2014-11-03 00:50
Category: Old Posts
Tags: old
Slug: Mass-Pwning-via-SSH-with-PXSSH
Authors: wumb0

<p>I've been meaning to do something like this for a while. When I red team I find myself writing scripts and then uploading them and running them the dumb way because I've been too lazy to automate with expect. When I finally decided to write a python script to log in and run commands for me I was delighted to find pxssh, a pexpect based python module for connecting and interacting with SSH sessions. I used this and my prior practice with threading in python to create <b>pxpwn</b>: an asynchronous and distributed command launcher. By default it reads commands from a file called "commands.txt", targets from a file called "targets.txt", writes command output to stdout, has a default login username of "root", and a default login password of "changeme". It can be silenced entirely so it shows only connected clients with -q, output can be redirected to a single file with -o <filename> (not recommended for large target lists as it locks the thread when it writes), output can be redirected to a file per host with -d, the username can be set with -u <username>, and the password can be set with -p <password>. </p>
<p>This is FAST. It connected and ran commands on six machines on two different subnets (whole subnets in the targets.txt file, created with a bash for loop, nonexistent clients are reported and ignored) in about 15 seconds. I may need to program in the maximum number of threads to be used at one time so a large targets.txt file does not roast the computer it is running on. I'm also thinking of adding in optional per host usernames and passwords as well as killing the bash history by default (which I'm pretty sure it writes to).</p>

<p>The code can be found on my GitHub: <a href="https://github.com/jgeigerm/pxpwn" target="_blank">https://github.com/jgeigerm/pxpwn</a></p>
