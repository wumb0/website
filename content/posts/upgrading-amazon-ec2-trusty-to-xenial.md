Title: Upgrading an Amazon EC2 Instance from Ubuntu Trusty to Xenial
Date: 2017-07-04 16:19
Category: Misc
Tags: sysadmin
Slug: upgrading-amazon-ec2-trusty-to-xenial
Authors: wumb0

I had a bad time.  
I ran a `do-release-upgrade` on one of my Amazon EC2 instances to try and upgrade it from 14.04 (Trusty) to 16.04 (Xenial). After the update and a reboot the box refused to come back up. When I detached the drive and attached it to another to check syslog I found this:
```
/sbin/dhclient -1 -v -pf /run/dhclient.eth0.pid -lf /var/lib/dhcp/dhclient.eth0.leases -I -df /var/lib/dhcp/dhclient6.eth0.leases eth0
Usage: dhclient [-4|-6] [-SNTP1dvrx] [-nw] [-p <port>] [-D LL|LLT]
             [-s server-addr] [-cf config-file] [-lf lease-file]
             [-pf pid-file] [--no-pid] [-e VAR=val]
             [-sf script-file] [interface]
Failed to bring up eth0.
```
Oh good, it forgot how to eth0.  
I spent about four hours figuring out how to fix it:
```
apt update
apt -y upgrade
cat  << EOF > /etc/update-manager/release-upgrades.d/unauth.cfg
[Distro]
AllowUnauthenticated=yes
EOF
apt install -y network-manager
do-release-upgrade
apt update
apt -y upgrade
systemctl enable systemd-networkd
systemctl enable systemd-resolved
dpkg-reconfigure resolvconf
apt-get -y autoremove
rm /etc/update-manager/release-upgrades.d/unauth.cfg
reboot
```
1. Make sure you are up to date first.
2. Some packages (python3) complain that they are unauthenticated. Feel free to skip this if you want.
3. Install the network-manager
4. Leap of faith... do the upgrade
5. Finish the upgrade by installing the rest of the packages. 
6. Enable the systemd network daemon and resolver daemon
7. Reconfigure resolvconf so you can dns
8. Get rid of the unauth.cfg file you created
9. Reboot and pray.

Thanks to these three links for the solutions (I just put them together):  
- <https://askubuntu.com/a/426121>  
- <https://askubuntu.com/a/769239>  
- <http://willhaley.com/blog/resolvconf-dns-issue-after-ubuntu-xenial-upgrade/>  
