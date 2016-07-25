Title: Virtualizing a Physical (Kali) Linux Partition on Mac
Date: 2014-06-08 14:26
Modified: 2016-07-24 23:16
Category: Old Posts
Tags: old
Slug: Virtualizing-a-Physical-(Kali)-Linux-Partition-on-Mac
Authors: wumb0

Let me start by saying that I'm a fan of doing sort of obscure things. Things like installing Kali Linux onto a partition on my Mac so I could boot into it separately. So I did that with the help of a blog post at <a href="https://web.archive.org/web/20141025231230/http://cr0ss.org/blog/?p=31" target="_blank">http://cr0ss.org/blog/?p=31</a>. My drive is actually laid out as follows with disk0 being my internal SSD and disk0s1 representing partition 1, disk0s2 representing partition 2, etc.


My partition layout is a bit weird now and Disk Utility doesn't even read it right.

<div class="uk-clearfix"><a href="/images/old/uploads/2014/06/Screen-Shot-2014-06-08-at-2.42.28-PM.png"><img class="uk-align-right " src="/images/old/uploads/2014/06/Screen-Shot-2014-06-08-at-2.42.28-PM.png" alt="Partition Table" width="133" height="504" /></a>
<p>[disk0s1 - EFI Boot for OSX partition]</p>
<p>[disk0s2 - Solid, my OSX partition, ~350GB]</p>
<p>[disk0s3 - OSX Recovery Partition]</p>
<p>[<strong>disk0s6 </strong>- Kali, my Linux partition, ~47GB]</p>
<p>[disk0s4 - Linux (EFI) /boot partition]</p>
<p>[disk0s5 - Linux Swap space, ~2GB]</p>
This is good to know moving forward.
So I was happy with my Kali install and was booting into it fine but I was still missing a luxury I had when I was running Windows in Bootcamp:  the ability to virtualize the physical partition. So I set out on a quest to solve this problem.</br>
First, I tried looking for what was already attempted before and I came across another blog post <a href="http://zefixblog.blogspot.com/2012/04/use-natively-installed-ubuntu-in-vmware.html" target="_blank">here</a> that detailed how to get a physical linux partition booting in VMWare Fusion.</br>
My first attempts at this did not work because I only followed the first few steps and did not really understand the GRUB part because I had already installed GRUB. But not really... I had installed and configured GRUB on the physical /boot partition (disk0s4) so it wasn't on the main one (disk0s6) that I was actually mounting and trying to boot after creating the raw disk with the vmware-rawdiskCreator.</br>
So last night I tried again, this time booting from a live CD and installing grub from that. I figured that it would work now because it had a bootloader, but no such luck.
When VMWare was trying to boot up the VM with the raw disk vmdk of my Kali partition it would try to unmount the entirety of disk0--the disk that contains the booted up host OS (OSX), so there was really no way it was getting unmounted.
</div>
[[more]]

So I hit a roadblock... A bit more Googling led me to a way to use VirtualBox to do the same thing so I decided to give it a shot. That post can be found at <a href="https://forums.virtualbox.org/viewtopic.php?t=9223#p66028" target="_blank">https://forums.virtualbox.org/viewtopic.php?t=9223#p66028</a>.

To get it working I did the following:

1. Gave VBox access to the drive: <strong>chmod 777 /dev/disk0s6</strong>

2. Ran the command: <strong>VBoxManage internalcommands createrawvmdk -filename /Users/Cheddar/Kali.vmdk -rawdisk /dev/disk0s6</strong>

3. Created a new VM and used that as the existing virtual disk

But it still wouldn't boot! I came to find out that I had installed GRUB incorrectly and the vmlinuz.img and initrd.img files weren't even on the Kali partition (disk0s6). So I booted into my Backtrack 5 live CD once again to fix things:
	First I copied the vmlinuz.img and initrd.img files from the physical boot partition on to a flash drive (in the host machine)
        Then I ran the following commands (sdb was the usb drive, sda was the Kali partition)

```bash
mount -t msdos /dev/sdb /mnt
cp vmlinuz* initrd* ~
umount /mnt
mount /dev/sda /mnt
cd /mnt
cp ~/vmlinuz* ~/initrd* boot
mount --bind /dev dev
mount -t sysfs sys sys
mount -t proc proc proc
chroot .
grub-install /dev/sda
grub-mkconfig > /boot/grub/grub.cfg
```
Now... <strong>BOOT IT UP!</strong> It works! Nice! Just had to use VirtualBox's raw disk creator and install and configure GRUB.  After that I was wondering if I could just load the raw disk back into VMWare Fusion because it was just a VMDK file. So I tried the following:

Create a new custom virtual machine
<div class="uk-clearfix">
<a href="/images/old/uploads/2014/06/Screen-Shot-2014-06-08-at-3.11.39-PM.png"><img class="uk-align-center" src="/images/old/uploads/2014/06/Screen-Shot-2014-06-08-at-3.11.39-PM.png" alt="New VM" width="392" height="340" /></a><img class="uk-align-center" src="/images/old/uploads/2014/06/Screen-Shot-2014-06-08-at-3.11.50-PM.png" alt="Custom VM" width="395" height="341" />
</div>

Pick the OS and create a NEW virtual disk because VMWare won't accept the raw disk vmdk as an option when you go to select an existing disk. Then customize options to your liking. Next, quit VMWare Fusion and go to where your VM is stored and open the .VMX file in a text editor. Add the following lines:
```
ide0:0.present = "TRUE"
ide0:0.fileName = "Kali.vmdk"
ide0:0.deviceType = "rawDisk"
```
And delete every line in the file starting with scsi0:0 (the old virtual disk that you needed to create).  Then save the file and double click on it to start it up. It should work!  Now you have a Kali Linux partition that you can boot via the Mac EFI bootloader AND via VMWare when booted into OSX.

All of this took me about 20 hours to do and figure out, hopefully it takes less time for you with this post!

<strong>Update:</strong> The VMWare virtual disk creator works now... 
```bash
/Applications/VMware\ Fusion.app/Contents/Library/vmware-rawdiskCreator create /dev/disk0 5,6 ~/Documents/Virtual\ Machines.localized/PhysicalKali.vmdk ide
```
